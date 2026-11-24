"""Ingestion: load a month of deliveries into the raw layer, then build the clean layer.

Every load of a period replaces that period inside one transaction (D-049): either the
whole month is replaced or nothing changes. ``ops.ingest_log`` records every load. The
same delivery loaded again (same SHA-256) is a no-op recorded as ``unchanged``.

SQL lives in ``credit_risk/sql/*.sql`` (D-047); table and column names are composed
with ``psycopg.sql.Identifier`` and values always travel as parameters.
"""

import argparse
import csv
import gzip
import hashlib
import io
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from functools import cache
from importlib.resources import files
from pathlib import Path
from typing import Any, Final

import polars as pl
import psycopg
from psycopg import sql

from credit_risk.cleaning import CLEANERS, CleaningError
from credit_risk.contracts import LISTING_COLUMNS, LISTINGS, OUTCOME_COLUMNS, STREAMS, delivery_path
from credit_risk.settings import Settings
from credit_risk.validation.contract import (
    BAD_STATUSES,
    CHARGE_OFF_LAG_MONTHS,
    SNAPSHOT,
    Contract,
    contract_at,
)
from credit_risk.validation.report import (
    Report,
    ValidationFailed,
    cleaning_findings,
    null_findings,
    profile,
    sql_findings,
    volume_findings,
)
from credit_risk.validation.rules import Finding, validate_month

log = logging.getLogger(__name__)

Connection = psycopg.Connection[tuple[Any, ...]]

LAYERS: Final = ("raw", "clean")
COLUMNS: Final = {"listings": LISTING_COLUMNS, "outcomes": OUTCOME_COLUMNS}
LOG_TABLE: Final = sql.Identifier("ops", "ingest_log")
WARNINGS_TABLE: Final = sql.Identifier("ops", "validation_warnings")
PROFILE_TABLE: Final = sql.Identifier("ops", "column_profile")
#: Where each validation run writes its report (D-053).
REPORTS: Final = Path("data/validation")
_CHUNK: Final = 1 << 20


@cache
def _query(name: str) -> sql.SQL:
    text = files("credit_risk.sql").joinpath(f"{name}.sql").read_text()
    # Trusted text: the files ship inside the package; values never go into them.
    return sql.SQL(text)


def _table(layer: str, stream: str) -> sql.Identifier:
    if layer not in LAYERS or stream not in STREAMS:
        raise ValueError(f"unknown table {layer}.{stream}")
    return sql.Identifier(layer, stream)


def _columns(names: tuple[str, ...]) -> sql.Composable:
    return sql.SQL(", ").join(sql.Identifier(c) for c in names)


def file_sha256(path: Path) -> str:
    """SHA-256 of a delivery file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


class DeliveryError(ValueError):
    """A delivery file does not follow the CSV contract."""


def read_delivery(path: Path, stream: str) -> pl.DataFrame:
    """Read a delivery strictly: exact header, every row with exactly that many fields.

    polars fills a row with too few fields with nulls instead of failing (E-018), which
    would turn a truncated row into a loan with missing values. The standard ``csv``
    module, in strict mode, parses here; an empty field is a missing value.
    """
    columns = COLUMNS[stream]
    with gzip.open(path, "rt", newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle, strict=True)
        header = tuple(next(reader, ()))
        if header != columns:
            raise DeliveryError(f"{path}: columns do not match the {stream} contract")
        rows = []
        for number, row in enumerate(reader, start=2):
            if len(row) != len(columns):
                raise DeliveryError(
                    f"{path}: record {number} has {len(row)} fields, expected {len(columns)}"
                )
            rows.append([value if value != "" else None for value in row])
    return pl.DataFrame(rows, schema=dict.fromkeys(columns, pl.String), orient="row")


@dataclass(frozen=True)
class LoadResult:
    """What a load did: its log row, its status and the rows written."""

    load_id: int | None
    status: str
    rows: int


@dataclass(frozen=True)
class LiveLoad:
    """The load whose rows a table holds now for a period."""

    load_id: int
    sha: str | None
    source_load_id: int | None


def _live(conn: Connection, stream: str, layer: str, period: date) -> LiveLoad | None:
    q = _query("live_load").format(log=LOG_TABLE)
    row = conn.execute(q, {"stream": stream, "layer": layer, "period": period}).fetchone()
    if row is None or row[3] == "deleted":
        return None
    return LiveLoad(int(row[0]), row[1], None if row[2] is None else int(row[2]))


def _log_event(conn: Connection, **values: Any) -> None:
    defaults = {"sha": None, "source": None, "rows_in_file": None, "error": None}
    with conn.transaction():
        conn.execute(_query("log_event").format(log=LOG_TABLE), {**defaults, **values})


def _count(conn: Connection, table: sql.Identifier, period: date) -> int:
    row = conn.execute(_query("count_period").format(table=table), {"period": period}).fetchone()
    assert row is not None  # noqa: S101 - count(*) always returns a row
    return int(row[0])


def _replace_period(
    conn: Connection,
    *,
    stream: str,
    layer: str,
    period: date,
    frame: pl.DataFrame,
    sha: str | None,
    source: int | None,
    replacing: bool,
) -> LoadResult:
    """Delete the period and COPY the frame in one transaction (D-049)."""
    table = _table(layer, stream)
    with conn.transaction():
        row = conn.execute(
            _query("start_load").format(log=LOG_TABLE),
            {
                "stream": stream,
                "layer": layer,
                "period": period,
                "status": "replaced" if replacing else "loaded",
                "sha": sha,
                "source": source,
                "rows_in_file": frame.height,
            },
        ).fetchone()
        assert row is not None  # noqa: S101 - INSERT ... RETURNING always returns a row
        load_id = int(row[0])
        conn.execute(_query("delete_period").format(table=table), {"period": period})
        body = io.BytesIO()
        frame.select(
            pl.lit(period).alias("period"), pl.lit(load_id).alias("load_id"), pl.all()
        ).write_csv(body)
        names = ("period", "load_id", *frame.columns)
        copy_sql = _query("copy_in").format(table=table, columns=_columns(names))
        with conn.cursor().copy(copy_sql) as copy:
            copy.write(body.getvalue())
        loaded = _count(conn, table, period)
        if loaded != frame.height:
            raise RuntimeError(
                f"{layer}.{stream} {period}: {loaded} rows loaded, {frame.height} in file"
            )
        conn.execute(
            _query("finish_load").format(log=LOG_TABLE), {"rows_loaded": loaded, "load_id": load_id}
        )
    status = "replaced" if replacing else "loaded"
    log.info("%s.%s %s: %s, %d rows", layer, stream, period, status, loaded)
    return LoadResult(load_id, status, loaded)


def _guarded(
    conn: Connection,
    stream: str,
    layer: str,
    period: date,
    sha: str | None,
    run: Callable[[], LoadResult],
) -> LoadResult:
    """Run a load; on failure record it in its own transaction and re-raise."""
    try:
        result = run()
    except Exception as exc:
        _log_event(
            conn,
            stream=stream,
            layer=layer,
            period=period,
            status="failed",
            sha=sha,
            error=repr(exc),
        )
        raise
    return result


def _require_autocommit(conn: Connection) -> None:
    """Each load must be its own transaction, committed or rolled back at its end.

    Without autocommit, psycopg opens an implicit transaction at the first query and
    ``conn.transaction()`` becomes a savepoint inside it: a failure record would then be
    rolled back with everything else when the connection closes.
    """
    if not conn.autocommit:
        raise ValueError("ingestion needs a connection with autocommit=True")


def load_raw(conn: Connection, landing: Path, period: date, stream: str) -> LoadResult:
    """Load one delivery into the raw layer, as text (D-044)."""
    _require_autocommit(conn)
    path = delivery_path(landing, period, stream)
    if not path.exists():
        raise FileNotFoundError(f"no {stream} delivery for {period:%Y-%m}: expected {path}")
    sha = file_sha256(path)
    live = _live(conn, stream, "raw", period)
    if live is not None and live.sha == sha:
        _log_event(
            conn,
            stream=stream,
            layer="raw",
            period=period,
            status="unchanged",
            sha=sha,
            source=live.load_id,
        )
        log.info("raw.%s %s: unchanged", stream, period)
        return LoadResult(None, "unchanged", 0)

    def run() -> LoadResult:
        frame = read_delivery(path, stream)
        return _replace_period(
            conn,
            stream=stream,
            layer="raw",
            period=period,
            frame=frame,
            sha=sha,
            source=None,
            replacing=live is not None,
        )

    return _guarded(conn, stream, "raw", period, sha, run)


def _raw_frame(conn: Connection, stream: str, period: date) -> pl.DataFrame:
    """One period of a raw table, as text, in contract and id order."""
    q = _query("copy_out").format(
        table=_table("raw", stream), columns=_columns(COLUMNS[stream]), period=sql.Literal(period)
    )
    out = io.BytesIO()
    with conn.cursor().copy(q) as copy:
        for chunk in copy:
            out.write(chunk)
    return pl.read_csv(out.getvalue(), infer_schema=False)


def _stage(stream: str) -> sql.Identifier:
    return sql.Identifier(f"stage_{stream}")


def _copy_frame(
    conn: Connection, table: sql.Composable, frame: pl.DataFrame, period: date, load_id: int
) -> None:
    body = io.BytesIO()
    frame.select(
        pl.lit(period).alias("period"), pl.lit(load_id).alias("load_id"), pl.all()
    ).write_csv(body)
    names = ("period", "load_id", *frame.columns)
    copy_sql = _query("copy_in").format(table=table, columns=_columns(names))
    with conn.cursor().copy(copy_sql) as copy:
        copy.write(body.getvalue())


Profiles = dict[str, dict[str, tuple[int, int]]]


def _history_findings(
    conn: Connection, period: date, frames: dict[str, pl.DataFrame], contract: Contract
) -> tuple[list[Finding], list[str], Profiles]:
    """R4.6 and R5: the rules that compare the month with the months before it."""
    findings: list[Finding] = []
    notes: list[str] = []
    profiles: Profiles = {}
    for stream, frame in frames.items():
        profiles[stream] = profile(frame)
        rows = conn.execute(_query("previous_profile"), {"stream": stream, "period": period})
        previous = {str(c): (int(t), int(n)) for c, t, n in rows.fetchall()}
        findings += null_findings(stream, profiles[stream], previous)
        history = conn.execute(_query("volume_history"), {"stream": stream, "period": period})
        volumes = [int(r[1]) for r in history.fetchall()]
        expected = contract.listings_expected or stream != LISTINGS
        found, note = volume_findings(stream, frame.height, volumes, expected=expected)
        findings += found
        notes += note
    return findings, notes, profiles


def _sql_rules(conn: Connection, period: date) -> list[Finding]:
    params = {
        "period": period,
        "bad": sorted(BAD_STATUSES),
        "lag": CHARGE_OFF_LAG_MONTHS,
        "snapshot": SNAPSHOT,
    }
    return sql_findings(conn.execute(_query("validate_month"), params).fetchall())


def _store_month(
    conn: Connection, period: date, load_ids: dict[str, int], report: Report, profiles: Profiles
) -> None:
    """Replace the month's warnings and missing-value profile (inside the load transaction)."""
    for stream, load_id in load_ids.items():
        for table in (WARNINGS_TABLE, PROFILE_TABLE):
            conn.execute(
                _query("delete_period_stream").format(table=table),
                {"period": period, "stream": stream},
            )
        for f in report.of_level("warning"):
            if f.stream == stream:
                conn.execute(
                    _query("insert_warning"),
                    {
                        "period": period,
                        "stream": stream,
                        "rule": f.rule,
                        "column": f.column,
                        "rows": f.count,
                        "load_id": load_id,
                        "examples": json.dumps(f.examples),
                    },
                )
        with conn.cursor() as cur:
            cur.executemany(
                _query("insert_profile"),
                [
                    {
                        "period": period,
                        "stream": stream,
                        "column": column,
                        "rows": total,
                        "nulls": nulls,
                        "load_id": load_id,
                    }
                    for column, (total, nulls) in profiles[stream].items()
                ],
            )


class _Rollback(Exception):  # noqa: N818 - control flow, never leaves this module
    """A critical SQL rule failed inside the load transaction."""


def _write_month(
    conn: Connection,
    period: date,
    frames: dict[str, pl.DataFrame],
    raws: dict[str, LiveLoad],
    lives: dict[str, LiveLoad | None],
    report: Report,
    profiles: Profiles,
) -> dict[str, LoadResult]:
    """Stage both streams, run the SQL rules, and replace the clean month if all pass.

    Returns no results when a critical SQL rule failed: the transaction was rolled back.
    """
    load_ids: dict[str, int] = {}
    statuses = {s: "replaced" if lives[s] is not None else "loaded" for s in STREAMS}
    try:
        with conn.transaction():
            for stream in STREAMS:
                row = conn.execute(
                    _query("start_load").format(log=LOG_TABLE),
                    {
                        "stream": stream,
                        "layer": "clean",
                        "period": period,
                        "status": statuses[stream],
                        "sha": raws[stream].sha,
                        "source": raws[stream].load_id,
                        "rows_in_file": frames[stream].height,
                    },
                ).fetchone()
                assert row is not None  # noqa: S101 - INSERT ... RETURNING always returns a row
                load_ids[stream] = int(row[0])
                table = _table("clean", stream)
                conn.execute(_query("create_stage").format(stage=_stage(stream), table=table))
                _copy_frame(conn, _stage(stream), frames[stream], period, load_ids[stream])
            report.findings += _sql_rules(conn, period)
            if not report.passed:
                raise _Rollback
            _store_month(conn, period, load_ids, report, profiles)
            for stream in STREAMS:
                table = _table("clean", stream)
                conn.execute(_query("delete_period").format(table=table), {"period": period})
                conn.execute(_query("publish_stage").format(table=table, stage=_stage(stream)))
                loaded = _count(conn, table, period)
                if loaded != frames[stream].height:
                    raise RuntimeError(
                        f"clean.{stream} {period}: {loaded} rows loaded, "
                        f"{frames[stream].height} cleaned"
                    )
                conn.execute(
                    _query("finish_load").format(log=LOG_TABLE),
                    {"rows_loaded": loaded, "load_id": load_ids[stream]},
                )
    except _Rollback:
        return {}
    results = {}
    for stream in STREAMS:
        rows = frames[stream].height
        log.info("clean.%s %s: %s, %d rows", stream, period, statuses[stream], rows)
        results[stream] = LoadResult(load_ids[stream], statuses[stream], rows)
    return results


def _validate(
    conn: Connection, period: date, contract: Contract, report: Report
) -> tuple[dict[str, pl.DataFrame], Profiles]:
    """Clean both streams and run every rule that does not need the load transaction."""
    frames: dict[str, pl.DataFrame] = {}
    for stream in STREAMS:
        raw_frame = _raw_frame(conn, stream, period)
        report.rows[stream] = raw_frame.height
        try:
            frames[stream] = CLEANERS[stream](raw_frame)
        except CleaningError as exc:
            report.findings += cleaning_findings(stream, exc)
    if not report.passed:
        return frames, {}
    for stream, frame in frames.items():
        report.findings += validate_month(frame, stream, period, contract)
    found, notes, profiles = _history_findings(conn, period, frames, contract)
    report.findings += found
    report.notes += notes
    return frames, profiles


def _log_failed(conn: Connection, period: date, raws: dict[str, LiveLoad], error: str) -> None:
    for stream in STREAMS:
        _log_event(
            conn,
            stream=stream,
            layer="clean",
            period=period,
            status="failed",
            sha=raws[stream].sha,
            error=error,
        )


def build_clean(
    conn: Connection, period: date, *, reports: Path = REPORTS
) -> dict[str, LoadResult]:
    """Validate a month and rebuild it in the clean layer from raw (D-044), never from files.

    The month is the unit (D-055): both streams are cleaned, validated and written in one
    transaction. A critical failure writes nothing of the month, records the failure in
    ``ops.ingest_log`` and raises ``ValidationFailed``; the report names every finding.
    """
    _require_autocommit(conn)
    raws: dict[str, LiveLoad] = {}
    for stream in STREAMS:
        raw = _live(conn, stream, "raw", period)
        if raw is None:
            raise LookupError(f"raw.{stream} has no data for {period:%Y-%m}")
        raws[stream] = raw
    lives = {stream: _live(conn, stream, "clean", period) for stream in STREAMS}
    if all((live := lives[s]) and live.source_load_id == raws[s].load_id for s in STREAMS):
        for stream in STREAMS:
            _log_event(
                conn,
                stream=stream,
                layer="clean",
                period=period,
                status="unchanged",
                sha=raws[stream].sha,
                source=raws[stream].load_id,
            )
            log.info("clean.%s %s: unchanged", stream, period)
        return {stream: LoadResult(None, "unchanged", 0) for stream in STREAMS}

    contract = contract_at(period)
    report = Report(period, contract.changes, {})
    try:
        frames, profiles = _validate(conn, period, contract, report)
        results = (
            _write_month(conn, period, frames, raws, lives, report, profiles)
            if report.passed
            else {}
        )
    except Exception as exc:
        _log_failed(conn, period, raws, repr(exc))
        raise
    path = report.write(reports)
    if not report.passed:
        failure = ValidationFailed(report, path)
        _log_failed(conn, period, raws, str(failure))
        log.error("%s", failure)
        raise failure
    warnings = len(report.of_level("warning"))
    log.info("validation %s: passed, %d warning(s), report %s", period, warnings, path)
    return results


def ingest(
    conn: Connection, landing: Path, period: date, *, reports: Path | None = None
) -> dict[str, list[LoadResult]]:
    """Load both streams of a month into raw, then validate and build the clean month.

    Reports go to ``reports``, by default ``validation`` next to the landing folder
    (``data/validation`` for ``data/landing``).
    """
    raw = {stream: load_raw(conn, landing, period, stream) for stream in STREAMS}
    clean = build_clean(conn, period, reports=reports or landing.parent / "validation")
    return {stream: [raw[stream], clean[stream]] for stream in STREAMS}


def published_periods(landing: Path, until: date) -> list[date]:
    """The months with a delivery folder in ``landing`` up to ``until``, oldest first."""
    months = []
    for folder in landing.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9]"):
        period = date.fromisoformat(f"{folder.name}-01")
        if period <= until and folder.is_dir():
            months.append(period)
    return sorted(months)


def catch_up(
    conn: Connection, landing: Path, until: date, *, reports: Path | None = None
) -> dict[date, dict[str, list[LoadResult]]]:
    """Ingest every published month up to ``until``, oldest first (D-104).

    A month already loaded from the same files is skipped by its hash (D-049); a
    corrected delivery is loaded again, and a month that failed before is retried. The
    first failure stops the catch-up, so nothing later is loaded over a gap.
    """
    months = published_periods(landing, until)
    if not months or months[-1] != until:
        raise FileNotFoundError(f"no delivery for {until:%Y-%m} in {landing}")
    return {period: ingest(conn, landing, period, reports=reports) for period in months}


def delete_period(conn: Connection, period: date, streams: tuple[str, ...] = STREAMS) -> None:
    """Remove a period from clean and raw; other periods are untouched."""
    _require_autocommit(conn)
    for stream in streams:
        with conn.transaction():
            for table in (WARNINGS_TABLE, PROFILE_TABLE):
                conn.execute(
                    _query("delete_period_stream").format(table=table),
                    {"period": period, "stream": stream},
                )
            for layer in ("clean", "raw"):
                conn.execute(
                    _query("delete_period").format(table=_table(layer, stream)), {"period": period}
                )
                conn.execute(
                    _query("log_event").format(log=LOG_TABLE),
                    {
                        "stream": stream,
                        "layer": layer,
                        "period": period,
                        "status": "deleted",
                        "sha": None,
                        "source": None,
                        "rows_in_file": None,
                        "error": None,
                    },
                )


def _month(text: str) -> date:
    return date.fromisoformat(f"{text}-01")


def main(argv: list[str] | None = None) -> None:
    """Command line: ``python -m credit_risk.ingest load 2015-03`` or ``delete 2015-03``."""
    parser = argparse.ArgumentParser(description="Load or delete a month of deliveries.")
    parser.add_argument("action", choices=["load", "delete"])
    parser.add_argument("period", type=_month, help="YYYY-MM")
    parser.add_argument("--landing", type=Path, default=Path("data/landing"))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    with psycopg.connect(Settings().postgres_conninfo(), autocommit=True) as conn:
        if args.action == "load":
            ingest(conn, args.landing, args.period)
        else:
            delete_period(conn, args.period)


if __name__ == "__main__":
    main()
