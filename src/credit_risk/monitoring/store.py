"""The monitoring of a month against the database and the registry (D-138 to D-146).

- :func:`ensure_reference` builds, once per pair of champions, the reference of D-138:
  the listings of the 12 months before the pair's cutoff (the later training cutoff of
  its PD and its LGD), exactly as delivered (``raw.listings``), cleaned and scored with
  the API's own :func:`credit_risk.api.scoring.score` (D-142). Only the bins are kept,
  in ``monitoring.reference``; nothing is written to ``serving.predictions``. This is
  the second written exception to the single prediction path of D-008: the reference
  is never used to decide, only to compare.
- :func:`monitor` measures one month: the drift of the loans listed that month, the
  early warning of the cohort listed 17 months before, and the performance of the
  cohorts that matured this month. It replaces whatever the month had stored, in one
  transaction, so running a month again changes nothing (D-145). In the same
  transaction it records the alerts the measurements raise, by the rules of
  :mod:`credit_risk.monitoring.alerting` (D-147, D-149), each signal once.
"""

import logging
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from datetime import date
from functools import cache
from importlib.resources import files
from typing import Any, Final

import polars as pl
from mlflow import MlflowClient
from psycopg import Connection, sql

from credit_risk import alerts, registry
from credit_risk.api.scoring import Champions, cleaning_errors, score
from credit_risk.contracts import LISTINGS
from credit_risk.features import CATEGORICAL, FEATURES
from credit_risk.ingest import raw_frame
from credit_risk.model import LGDModel, PDModel
from credit_risk.monitoring import alerting
from credit_risk.monitoring.drift import Bins, Drift, Kind, fit, measure
from credit_risk.monitoring.outcomes import (
    EARLY_AFTER,
    EARLY_MONTHS,
    FirstYear,
    early_warning,
    first_year,
    performance,
)
from credit_risk.snapshot import BAD, GOOD, LGD_AGE_MONTHS
from credit_risk.validation.contract import CHARGE_OFF_LAG_MONTHS

log = logging.getLogger(__name__)

#: Months of listings in a reference, the ones just before the cutoff (D-138).
REFERENCE_MONTHS: Final = 12
#: The predictions watched for drift, besides the 30 features (D-139).
PREDICTIONS: Final = ("pd", "lgd", "el_rate")
#: The terms a cohort can have.
TERMS: Final = (36, 60)

Pair = tuple[str, str]


@cache
def _query(name: str) -> sql.SQL:
    # Trusted text: the files ship inside the package; values never go into them.
    return sql.SQL(files("credit_risk.sql").joinpath(f"{name}.sql").read_text())


def add_months(month: date, months: int) -> date:
    index = month.year * 12 + month.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def kind_of(subject: str) -> Kind:
    if subject in PREDICTIONS:
        return "prediction"
    return "categorical" if subject in CATEGORICAL else "numeric"


#: Every variable watched, in the order they are stored.
SUBJECTS: Final = (*FEATURES, *PREDICTIONS)
SCHEMA: Final[dict[str, pl.DataType]] = {
    s: pl.String() if kind_of(s) == "categorical" else pl.Float64() for s in SUBJECTS
}


def _frame(rows: list[dict[str, Any]]) -> pl.DataFrame:
    """Rows of features and predictions as one typed frame, every subject a column."""
    return pl.DataFrame(
        [{s: row.get(s) for s in SUBJECTS} for row in rows], schema=SCHEMA, strict=False
    )


# ---------------------------------------------------------------- the reference


def cutoff(conn: Connection, name: str, version: str) -> date:
    """The training cutoff of a registered version: the month of its training set."""
    tags = MlflowClient().get_model_version(name, version).tags
    training_set = tags.get(registry.TRAINING_SET)
    if training_set is None:
        raise ValueError(f"{name} version {version} has no {registry.TRAINING_SET} tag")
    row = conn.execute(
        "SELECT cutoff FROM ops.training_sets WHERE version = %s", (training_set,)
    ).fetchone()
    if row is None:
        raise ValueError(f"{name} version {version}: training set {training_set} not found")
    found: date = row[0]
    return found


def pair_cutoff(conn: Connection, pair: Pair, prefix: str = "") -> date:
    """The later training cutoff of the pair: the reference follows the newer model."""
    pd_version, lgd_version = pair
    return max(cutoff(conn, f"{prefix}pd", pd_version), cutoff(conn, f"{prefix}lgd", lgd_version))


def reference_months(at: date) -> list[date]:
    """The 12 listing months before the cutoff ``at``: ``at - 12`` to ``at - 1``."""
    return [add_months(at, -k) for k in range(REFERENCE_MONTHS, 0, -1)]


def has_reference(conn: Connection, pair: Pair) -> bool:
    row = conn.execute(
        "SELECT count(*) FROM monitoring.reference WHERE pd_version = %s AND lgd_version = %s",
        pair,
    ).fetchone()
    return row is not None and row[0] > 0


def _champions(pair: Pair, prefix: str) -> Champions:
    pd_model = registry.load(f"{prefix}pd", pair[0])
    lgd_model = registry.load(f"{prefix}lgd", pair[1])
    if not isinstance(pd_model, PDModel) or not isinstance(lgd_model, LGDModel):
        raise TypeError("the registry returned something that is not a model")
    return Champions(pd_model, lgd_model, pair[0], pair[1])


def scored_reference(conn: Connection, champions: Champions, months: list[date]) -> pl.DataFrame:
    """Features and predictions (and ``loan_id``) of the listings of ``months``, as the API
    scores them.

    Month by month, so that only one month of answers is in memory at a time.
    """
    parts = []
    for month in months:
        raw = raw_frame(conn, LISTINGS, month)
        if raw.height == 0:
            continue
        typed, errors = cleaning_errors(raw)
        keep = pl.Series([not e for e in errors])
        if not keep.all():
            # Clean months only reach here (D-055); a row that does not clean is skipped.
            log.warning("%s: %d listings do not clean, left out", month, int((~keep).sum()))
        answers = score(champions, typed.filter(keep), raw.filter(keep))
        rows = [{**a.features, "pd": a.pd, "lgd": a.lgd, "el_rate": a.el_rate} for a in answers]
        ids = pl.Series([a.loan_id for a in answers], dtype=pl.Int64)
        parts.append(_frame(rows).with_columns(loan_id=ids))
    if not parts:
        raise ValueError(f"no listings in the reference months {months[0]} to {months[-1]}")
    return pl.concat(parts)


def reference_bins(frame: pl.DataFrame) -> list[Bins]:
    """The bins of every subject; predictions only over the loans a model covers."""
    out = []
    for subject in SUBJECTS:
        kind = kind_of(subject)
        values = frame[subject]
        out.append(fit(subject, kind, values.drop_nulls() if kind == "prediction" else values))
    return out


def ensure_reference(conn: Connection, pair: Pair, prefix: str = "") -> bool:
    """Build the reference of ``pair`` unless it exists; return whether it was built."""
    if has_reference(conn, pair):
        return False
    at = pair_cutoff(conn, pair, prefix)
    months = reference_months(at)
    frame = scored_reference(conn, _champions(pair, prefix), months)
    rows = [
        {
            "pd_version": pair[0],
            "lgd_version": pair[1],
            "cutoff": at,
            "first_month": months[0],
            "last_month": months[-1],
            **_bins_row(b),
        }
        for b in reference_bins(frame)
    ]
    with conn.transaction():
        conn.cursor().executemany(
            """
            INSERT INTO monitoring.reference
                (pd_version, lgd_version, subject, kind, cutoff, first_month, last_month,
                 rows, nulls, edges, categories, shares, minimum, maximum, sample)
            VALUES (%(pd_version)s, %(lgd_version)s, %(subject)s, %(kind)s, %(cutoff)s,
                    %(first_month)s, %(last_month)s, %(rows)s, %(nulls)s, %(edges)s,
                    %(categories)s, %(shares)s, %(minimum)s, %(maximum)s, %(sample)s)
            ON CONFLICT DO NOTHING
            """,
            rows,
        )
    log.info(
        "reference of pd %s, lgd %s: %s to %s, %d loans", *pair, months[0], months[-1], frame.height
    )
    return True


def _bins_row(b: Bins) -> dict[str, Any]:
    numeric = b.numeric
    return {
        "subject": b.subject,
        "kind": b.kind,
        "rows": b.rows,
        "nulls": b.nulls,
        "edges": list(b.edges) if numeric else None,
        "categories": None if numeric else list(b.categories),
        "shares": list(b.shares),
        "minimum": b.minimum,
        "maximum": b.maximum,
        "sample": list(b.sample) if numeric else None,
    }


def read_reference(conn: Connection, pair: Pair) -> dict[str, Bins]:
    """The bins of every subject of the reference of ``pair``."""
    rows = conn.execute(
        """
        SELECT subject, kind, rows, nulls, shares, edges, categories, minimum, maximum, sample
        FROM monitoring.reference WHERE pd_version = %s AND lgd_version = %s
        """,
        pair,
    ).fetchall()
    return {
        r[0]: Bins(
            subject=r[0],
            kind=r[1],
            rows=r[2],
            nulls=r[3],
            shares=tuple(r[4]),
            edges=tuple(r[5] or ()),
            categories=tuple(r[6] or ()),
            minimum=r[7],
            maximum=r[8],
            sample=tuple(r[9] or ()),
        )
        for r in rows
    }


def current_pair(prefix: str = "") -> Pair | None:
    """The pair of champions in the registry now, or None while one is missing."""
    pd_version = registry.champion(f"{prefix}pd")
    lgd_version = registry.champion(f"{prefix}lgd")
    if pd_version is None or lgd_version is None:
        return None
    return pd_version, lgd_version


# ---------------------------------------------------------------- one month


def month_predictions(conn: Connection, period: date) -> dict[Pair, pl.DataFrame]:
    """What each pair of champions received and answered for the loans listed in ``period``."""
    found: dict[Pair, list[dict[str, Any]]] = {}
    for pd_version, lgd_version, features, pd_, lgd, el_rate in conn.execute(
        _query("month_predictions"), {"period": period}
    ):
        found.setdefault((pd_version, lgd_version), []).append(
            {**features, "pd": pd_, "lgd": lgd, "el_rate": el_rate}
        )
    return {pair: _frame(rows) for pair, rows in sorted(found.items())}


def drift(frame: pl.DataFrame, reference: dict[str, Bins]) -> list[Drift]:
    """The drift of every subject of one month of one pair."""
    out = []
    for subject in SUBJECTS:
        values = frame[subject]
        if kind_of(subject) == "prediction":
            values = values.drop_nulls()  # only the loans the models cover
        if values.len():
            out.append(measure(reference[subject], values))
    return out


def _label(status: str | None) -> int | None:
    if status in GOOD:
        return 0
    if status in BAD:
        return 1
    return None  # no outcome yet, or a status of the old credit policy


def cohort(conn: Connection, listed: date, at: date) -> pl.DataFrame:
    """The covered loans listed in ``listed``, with what is known of them at ``at``."""
    rows = conn.execute(_query("cohort_outcomes"), {"cohort": listed, "at": at}).fetchall()
    last_early = add_months(listed, EARLY_MONTHS - 1)
    lgd_by = add_months(at, -LGD_AGE_MONTHS)
    records = []
    for r in rows:
        (loan_id, pd_version, lgd_version, term, grade, pd_, lgd, status, resolved, last_paid,
         funded, total_pymnt, principal, recoveries, fee, amount) = r  # fmt: skip
        label = _label(status)
        early = label == 1 and (last_paid is None or last_paid.replace(day=1) <= last_early)
        lgd_actual = None
        if label == 1 and resolved <= lgd_by and funded:
            lgd_actual = (funded - principal - (recoveries - (fee or 0.0))) / funded
        records.append(
            {
                "loan_id": loan_id,
                "pd_version": pd_version,
                "lgd_version": lgd_version,
                "term": term,
                "grade": grade,
                "pd": pd_,
                "lgd": lgd,
                "label": label,
                "early": early,
                "lgd_actual": lgd_actual,
                "amount": amount,
                "funded_amnt": funded,
                "total_pymnt": total_pymnt,
                "collection_recovery_fee": fee,
            }
        )
    return pl.DataFrame(
        records,
        schema={
            "loan_id": pl.Int64(),
            "pd_version": pl.String(),
            "lgd_version": pl.String(),
            "term": pl.Int64(),
            "grade": pl.String(),
            "pd": pl.Float64(),
            "lgd": pl.Float64(),
            "label": pl.Int16(),
            "early": pl.Boolean(),
            "lgd_actual": pl.Float64(),
            "amount": pl.Float64(),
            "funded_amnt": pl.Float64(),
            "total_pymnt": pl.Float64(),
            "collection_recovery_fee": pl.Float64(),
        },
    )


def first_year_shares(conn: Connection, at: date) -> FirstYear:
    """Shares of first-year defaults among the cohorts matured at the cutoff ``at``."""
    rows = conn.execute(
        _query("first_year"),
        {"cutoff": at, "lag": CHARGE_OFF_LAG_MONTHS, "early": EARLY_MONTHS, "bad": list(BAD)},
    ).fetchall()
    return first_year([(int(t), str(g), int(d), int(e)) for t, g, d, e in rows])


def _groups(frame: pl.DataFrame, *keys: str) -> Iterator[tuple[tuple[Any, ...], pl.DataFrame]]:
    for key, group in sorted(frame.group_by(*keys), key=lambda g: tuple(map(str, g[0]))):
        yield tuple(key), group


@dataclass(frozen=True)
class Month:
    """What :func:`monitor` measured and stored for a month."""

    period: str
    pairs: list[Pair]
    drift: int
    early_warning: int
    performance: int
    references_built: int
    notes: list[str]
    #: Alerts the month raised (D-149), and how many were new (not recorded before).
    alerts: int = 0
    alerts_recorded: int = 0


def validation_auc(name: str, version: str) -> float | None:
    """The validation AUC logged with the run of a registered PD version."""
    client = MlflowClient()
    run_id = client.get_model_version(name, version).run_id
    if run_id is None:
        return None
    run = client.get_run(run_id)
    value = run.data.metrics.get("auc")
    return None if value is None else float(value)


def month_alerts(
    period: date,
    drifts: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    results: list[dict[str, Any]],
    prefix: str = "",
    thresholds: alerting.Thresholds | None = None,
) -> list[alerts.Alert]:
    """The alerts of one month's measurements (D-149, D-156)."""
    t = thresholds or alerting.load()
    aucs: dict[str, float | None] = {}

    def reference(version: str) -> float | None:
        if version not in aucs:
            aucs[version] = validation_auc(f"{prefix}pd", version)
        return aucs[version]

    return [
        *alerting.drift_alerts(period, drifts, t),
        *alerting.early_warning_alerts(period, warnings, t),
        *alerting.performance_alerts(period, results, t, reference),
    ]


def monitor(
    conn: Connection,
    period: date,
    prefix: str = "",
    thresholds: alerting.Thresholds | None = None,
) -> Month:
    """Measure ``period``, store it (replacing what the month had, D-145) and record
    the alerts it raises (D-149)."""
    notes: list[str] = []
    built = 0
    drifts: list[dict[str, Any]] = []
    months = month_predictions(conn, period)
    if not months:
        notes.append(f"no predictions for the loans listed in {period:%Y-%m}: no drift")
    for pair, frame in months.items():
        built += ensure_reference(conn, pair, prefix)
        reference = read_reference(conn, pair)
        drifts += [
            {"pd_version": pair[0], "lgd_version": pair[1], **asdict(d)}
            for d in drift(frame, reference)
        ]

    # Early warning: the cohort listed 17 months ago (D-143).
    early_cohort = add_months(period, -EARLY_AFTER)
    warnings: list[dict[str, Any]] = []
    loans = cohort(conn, early_cohort, period)
    for (pd_version,), group in _groups(loans, "pd_version"):
        shares = first_year_shares(conn, cutoff(conn, f"{prefix}pd", pd_version))
        for result in early_warning(group, shares):
            warnings.append(
                {"cohort": early_cohort, "pd_version": pd_version, "evaluated": period,
                 **asdict(result)}
            )  # fmt: skip
    if loans.height and not warnings:
        notes.append(f"cohort {early_cohort:%Y-%m}: no share of first-year defaults known")

    # Real performance: the cohorts that matured this month, one per term (D-144).
    results: list[dict[str, Any]] = []
    for term in TERMS:
        listed = add_months(period, -(term + CHARGE_OFF_LAG_MONTHS))
        matured = cohort(conn, listed, period).filter(pl.col("term") == term)
        for (pd_version, lgd_version), group in _groups(matured, "pd_version", "lgd_version"):
            results += [
                {"cohort": listed, "pd_version": pd_version, "lgd_version": lgd_version,
                 "evaluated": period, **asdict(p)}
                for p in performance(group)
            ]  # fmt: skip

    with conn.transaction():
        conn.execute("DELETE FROM monitoring.drift WHERE period = %s", (period,))
        conn.execute("DELETE FROM monitoring.early_warning WHERE evaluated = %s", (period,))
        conn.execute("DELETE FROM monitoring.performance WHERE evaluated = %s", (period,))
        cursor = conn.cursor()
        if drifts:
            cursor.executemany(
                """
                INSERT INTO monitoring.drift
                    (period, pd_version, lgd_version, subject, kind, rows, psi, ks,
                     null_share, new_values)
                VALUES (%(period)s, %(pd_version)s, %(lgd_version)s, %(subject)s, %(kind)s,
                        %(rows)s, %(psi)s, %(ks)s, %(null_share)s, %(new_values)s)
                """,
                [{**d, "period": period} for d in drifts],
            )
        if warnings:
            cursor.executemany(
                """
                INSERT INTO monitoring.early_warning
                    (cohort, term, pd_version, evaluated, loans, defaults, expected_defaults,
                     observed_rate, expected_rate, ratio, ratio_low, ratio_high, auc)
                VALUES (%(cohort)s, %(term)s, %(pd_version)s, %(evaluated)s, %(loans)s,
                        %(defaults)s, %(expected_defaults)s, %(observed_rate)s,
                        %(expected_rate)s, %(ratio)s, %(ratio_low)s, %(ratio_high)s, %(auc)s)
                """,
                warnings,
            )
        if results:
            cursor.executemany(
                """
                INSERT INTO monitoring.performance
                    (cohort, term, pd_version, lgd_version, segment, evaluated, loans,
                     defaults, unresolved, auc, brier, calibration_error, mean_pd,
                     default_rate, lgd_loans, lgd_rmse, lgd_level, purchases, invested,
                     received, realised_return, auc_low, auc_high, calibration_low,
                     calibration_high)
                VALUES (%(cohort)s, %(term)s, %(pd_version)s, %(lgd_version)s, %(segment)s,
                        %(evaluated)s, %(loans)s, %(defaults)s, %(unresolved)s, %(auc)s,
                        %(brier)s, %(calibration_error)s, %(mean_pd)s, %(default_rate)s,
                        %(lgd_loans)s, %(lgd_rmse)s, %(lgd_level)s, %(purchases)s,
                        %(invested)s, %(received)s, %(realised_return)s, %(auc_low)s,
                        %(auc_high)s, %(calibration_low)s, %(calibration_high)s)
                """,
                results,
            )
        # The alerts of the month (D-147, D-149), in the same transaction as what they
        # read; a month run again records each signal once (D-145).
        found = month_alerts(period, drifts, warnings, results, prefix, thresholds)
        recorded = sum(alerts.record(a, conn) for a in found)
    month = Month(
        period=f"{period:%Y-%m}",
        pairs=list(months),
        drift=len(drifts),
        early_warning=len(warnings),
        performance=len(results),
        references_built=built,
        notes=notes,
        alerts=len(found),
        alerts_recorded=recorded,
    )
    for note in notes:
        log.info("monitor %s: %s", month.period, note)
    return month
