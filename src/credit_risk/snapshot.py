"""Training set versions (step 2.3, D-058 to D-061).

A version is the training set at a cutoff month T, built once in SQL from the clean layer
and saved as two immutable Parquet files (D-060):

- ``features.parquet``: what training may see. Every listing column, the label and the
  split (train or validation).
- ``evaluation.parquet``: what only evaluation may see. The outcome columns of the same
  loans and the month each was resolved.

Its name is the hash of its content (D-061), and its manifest in ``ops.training_sets``
records the cutoff, the code commit, the counts, the checksum of each file and every
clean load it was built from (D-058, D-059). Training reads the saved copy, never the
live query, and every read checks the file against its checksum.
"""

import argparse
import hashlib
import io
import logging
import os
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import date
from functools import cache
from importlib.resources import files
from pathlib import Path
from typing import Any, Final

import polars as pl
import psycopg
from psycopg import sql

from credit_risk.cleaning import DTYPES, LISTING_RULES, OUTCOME_RULES
from credit_risk.contracts import LISTING_COLUMNS, OUTCOME_COLUMNS
from credit_risk.ingest import file_sha256
from credit_risk.settings import Settings
from credit_risk.storage import LocalStore, Store
from credit_risk.validation.contract import (
    BAD_STATUSES,
    CHARGE_OFF_LAG_MONTHS,
    FIRST_PERIOD,
    GOOD_STATUSES,
)

log = logging.getLogger(__name__)

Connection = psycopg.Connection[tuple[Any, ...]]

FEATURES: Final = "features.parquet"
EVALUATION: Final = "evaluation.parquet"
LABEL: Final = "label"
SPLIT: Final = "split"
RESOLVED: Final = "resolved_period"
#: Where versions are stored locally (D-059); out of git with the rest of data/.
ROOT: Final = Path("data/training_sets")

#: PD label (D-013). The statuses of the old credit policy are left out.
GOOD: Final = ("Fully Paid",)
BAD: Final = ("Charged Off", "Default")
OLD_POLICY: Final = tuple(sorted((GOOD_STATUSES | BAD_STATUSES) - {*GOOD, *BAD}))

FEATURE_SCHEMA: Final[Mapping[str, pl.DataType]] = {
    **{c: DTYPES[LISTING_RULES[c]] for c in LISTING_COLUMNS},
    LABEL: pl.Int16(),
    SPLIT: pl.String(),
}
EVALUATION_SCHEMA: Final[Mapping[str, pl.DataType]] = {
    **{c: DTYPES[OUTCOME_RULES[c]] for c in OUTCOME_COLUMNS},
    RESOLVED: pl.Date(),
}
_HASH_ROWS: Final = 50_000


class SnapshotError(RuntimeError):
    """A training set cannot be built or read as asked."""


@dataclass(frozen=True)
class Manifest:
    """One row of ``ops.training_sets``."""

    version: str
    cutoff: date
    git_commit: str
    path: str
    rows_train: int
    rows_validation: int
    bad_train: int
    bad_validation: int
    excluded_old_policy: int
    excluded_unresolved: int
    features_sha256: str
    evaluation_sha256: str

    def sha(self, name: str) -> str:
        return {FEATURES: self.features_sha256, EVALUATION: self.evaluation_sha256}[name]


@cache
def _query(name: str) -> sql.SQL:
    text = files("credit_risk.sql").joinpath(f"{name}.sql").read_text()
    # Trusted text: the files ship inside the package; values never go into them.
    return sql.SQL(text)


# ---------------------------------------------------------------- content hash (D-061)


def content_hash(frames: Mapping[str, pl.DataFrame]) -> str:
    """SHA-256 of the data, whatever the file format, compression or row order.

    For each frame, in name order: its name, its columns with their types, then its rows
    sorted by ``id`` as CSV written one fixed way (floats in scientific notation with 17
    significant digits, which is exact; text always quoted; missing values as an unquoted
    ``\\N``, so a missing value and the text ``\\N`` differ).
    """
    digest = hashlib.sha256()
    for name in sorted(frames):
        frame = frames[name].sort("id")
        digest.update(f"{name}\n".encode())
        digest.update(",".join(f"{c}:{t}" for c, t in frame.schema.items()).encode() + b"\n")
        for start in range(0, frame.height, _HASH_ROWS):
            text = frame.slice(start, _HASH_ROWS).write_csv(
                include_header=False,
                float_scientific=True,
                float_precision=16,
                null_value="\\N",
                date_format="%Y-%m-%d",
                quote_style="non_numeric",
                line_terminator="\n",
            )
            digest.update(text.encode())
    return digest.hexdigest()


# ---------------------------------------------------------------- reading clean


def _typed(text: pl.DataFrame, schema: Mapping[str, pl.DataType]) -> pl.DataFrame:
    """Postgres CSV text to the types of the cleaning rules (D-045)."""
    exprs = []
    for column, dtype in schema.items():
        c = pl.col(column)
        if dtype == pl.Boolean:
            exprs.append(c.replace_strict({"t": True, "f": False}, return_dtype=pl.Boolean))
        elif dtype == pl.Date:
            exprs.append(c.str.to_date("%Y-%m-%d"))
        else:
            exprs.append(c.cast(dtype, strict=True))
    return text.select(exprs)


def _copy_out(
    conn: Connection, query: sql.Composed, schema: Mapping[str, pl.DataType]
) -> pl.DataFrame:
    out = io.BytesIO()
    with conn.cursor().copy(query) as copy:
        for chunk in copy:
            out.write(chunk)
    text = pl.read_csv(out.getvalue(), schema=dict.fromkeys(schema, pl.String))
    return _typed(text, schema)


def month_loads(conn: Connection, cutoff: date, first: date = FIRST_PERIOD) -> list[int]:
    """The live clean load of every month and stream up to the cutoff.

    Refuses when a month is missing, deleted, or its last attempt failed (it waits for a
    corrected delivery), naming the months.
    """
    q = _query("month_loads").format(log=sql.Identifier("ops", "ingest_log"))
    rows = conn.execute(q, {"first": first, "cutoff": cutoff}).fetchall()
    gaps = sorted(
        {
            f"{period:%Y-%m}"
            for period, _, load_id, status, last in rows
            if load_id is None or status == "deleted" or last == "failed"
        }
    )
    if gaps:
        raise SnapshotError(f"clean is not complete up to {cutoff:%Y-%m}: {', '.join(gaps)}")
    return [int(load_id) for _, _, load_id, _, _ in rows]


def _columns(alias: str, names: tuple[str, ...]) -> sql.Composable:
    return sql.SQL(", ").join(sql.Identifier(alias, c) for c in names)


def build_frames(
    conn: Connection, cutoff: date
) -> tuple[pl.DataFrame, pl.DataFrame, dict[str, int]]:
    """Features, evaluation and counts of the training set at ``cutoff``.

    Runs inside the caller's transaction (it needs the temporary table of the ids).
    """
    conn.execute(_query("create_training_ids"))
    conn.execute(
        _query("training_ids"),
        {"cutoff": cutoff, "lag": CHARGE_OFF_LAG_MONTHS, "good": list(GOOD), "bad": list(BAD)},
    )
    row = conn.execute(_query("training_counts"), {"old_policy": list(OLD_POLICY)}).fetchone()
    if row is None:  # an aggregate always returns one row
        raise SnapshotError("the training set counts returned nothing")
    names = (
        *("rows_train", "rows_validation", "bad_train", "bad_validation"),
        *("excluded_old_policy", "excluded_unresolved", "unknown_status"),
    )
    counts = dict(zip(names, (int(v) for v in row), strict=True))
    if counts.pop("unknown_status"):
        raise SnapshotError("a matured loan has a status that is not in the label mapping")
    if counts["rows_train"] == 0 or counts["rows_validation"] == 0:
        raise SnapshotError(f"no matured loan with a label at {cutoff:%Y-%m}")
    features = _copy_out(
        conn,
        _query("training_features").format(columns=_columns("l", LISTING_COLUMNS)),
        FEATURE_SCHEMA,
    )
    evaluation = _copy_out(
        conn,
        _query("training_evaluation").format(columns=_columns("o", OUTCOME_COLUMNS)),
        EVALUATION_SCHEMA,
    )
    return features, evaluation, counts


# ---------------------------------------------------------------- manifest


def get_manifest(conn: Connection, version: str) -> Manifest | None:
    row = conn.execute(_query("get_training_set"), {"version": version}).fetchone()
    return None if row is None else Manifest(*row)


def stale_versions(conn: Connection) -> list[str]:
    """Versions built on a clean load that a corrected delivery has since replaced."""
    return [str(v) for (v,) in conn.execute(_query("stale_training_sets")).fetchall()]


def _verify(path: Path, expected: str) -> None:
    actual = file_sha256(path)
    if actual != expected:
        raise SnapshotError(f"{path}: checksum {actual} differs from the manifest {expected}")


# ---------------------------------------------------------------- build and read


def build(conn: Connection, cutoff: date, store: Store, *, commit: str) -> Manifest:
    """Build the training set at ``cutoff``, or return the version that already holds it.

    The same data give the same version: nothing is written again, and the stored files
    are checked against their checksums (D-061).
    """
    if not conn.autocommit:
        raise ValueError("building a training set needs a connection with autocommit=True")
    with conn.transaction():
        # One consistent view of clean for the whole build.
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        loads = month_loads(conn, cutoff)
        features, evaluation, counts = build_frames(conn, cutoff)
        frames = {FEATURES: features, EVALUATION: evaluation}
        version = content_hash(frames)
        existing = get_manifest(conn, version)
        if existing is not None:
            if not store.has(version):
                raise SnapshotError(f"version {version} has a manifest but no files")
            for name in frames:
                _verify(store.local(version, name), existing.sha(name))
            log.info("training set %s at %s: unchanged", version[:12], f"{cutoff:%Y-%m}")
            return existing
        if store.has(version):
            # Files saved by a build that stopped before writing its manifest.
            stored = {name: pl.read_parquet(store.local(version, name)) for name in frames}
            if content_hash(stored) != version:
                raise SnapshotError(f"stored files of {version} do not hold its data")
        else:
            with tempfile.TemporaryDirectory() as tmp:
                paths = {name: Path(tmp) / name for name in frames}
                for name, frame in frames.items():
                    frame.write_parquet(paths[name], compression="zstd")
                store.save(version, paths)
        manifest = Manifest(
            version=version,
            cutoff=cutoff,
            git_commit=commit,
            path=store.location(version),
            features_sha256=file_sha256(store.local(version, FEATURES)),
            evaluation_sha256=file_sha256(store.local(version, EVALUATION)),
            **counts,
        )
        conn.execute(_query("insert_training_set"), asdict(manifest))
        for load_id in sorted(set(loads)):
            conn.execute(
                _query("insert_training_set_load"), {"version": version, "load_id": load_id}
            )
    log.info(
        "training set %s at %s: train %d (%d bad), validation %d (%d bad)",
        version[:12],
        f"{cutoff:%Y-%m}",
        manifest.rows_train,
        manifest.bad_train,
        manifest.rows_validation,
        manifest.bad_validation,
    )
    return manifest


def _read(conn: Connection, store: Store, version: str, name: str) -> pl.DataFrame:
    manifest = get_manifest(conn, version)
    if manifest is None:
        raise SnapshotError(f"no training set {version}")
    path = store.local(version, name)
    _verify(path, manifest.sha(name))
    return pl.read_parquet(path)


def read_features(conn: Connection, store: Store, version: str) -> pl.DataFrame:
    """What training may see (D-060), after checking the file against its checksum."""
    return _read(conn, store, version, FEATURES)


def read_evaluation(conn: Connection, store: Store, version: str) -> pl.DataFrame:
    """The outcomes of a version, for evaluation only (D-060)."""
    return _read(conn, store, version, EVALUATION)


# ---------------------------------------------------------------- command line


def _git(*args: str) -> str:
    git = shutil.which("git")
    if git is None:
        raise SnapshotError("unknown code commit: set CREDIT_RISK_COMMIT")
    # Fixed arguments only; nothing from outside reaches the command.
    done = subprocess.run([git, *args], check=True, capture_output=True, text=True)  # noqa: S603
    return done.stdout.strip()


def git_commit() -> str:
    """The commit of the code: ``CREDIT_RISK_COMMIT`` (images) or git, with ``-dirty``."""
    if commit := os.environ.get("CREDIT_RISK_COMMIT"):
        return commit
    try:
        head = _git("rev-parse", "HEAD")
        dirty = _git("status", "--porcelain", "--untracked-files=no")
    except (OSError, subprocess.CalledProcessError) as error:
        raise SnapshotError("unknown code commit: set CREDIT_RISK_COMMIT") from error
    return f"{head}-dirty" if dirty else head


def main(argv: list[str] | None = None) -> None:
    """``python -m credit_risk.snapshot build 2014-01``, or ``stale`` to list stale versions."""
    parser = argparse.ArgumentParser(description="Build training set versions.")
    parser.add_argument("action", choices=["build", "stale"])
    parser.add_argument("cutoff", nargs="?", help="YYYY-MM (build)")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    with psycopg.connect(Settings().postgres_conninfo(), autocommit=True) as conn:
        if args.action == "build":
            if args.cutoff is None:
                parser.error("build needs a cutoff month, YYYY-MM")
            cutoff = date.fromisoformat(f"{args.cutoff}-01")
            manifest = build(conn, cutoff, LocalStore(args.root), commit=git_commit())
            print(manifest.version)
        else:
            for version in stale_versions(conn):
                print(version)


if __name__ == "__main__":
    main()
