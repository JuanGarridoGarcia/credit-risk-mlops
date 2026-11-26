"""The study that calibrates the alert thresholds with only what was known at T0 (D-150).

The thresholds of the alerts (D-149) are set before the system starts, so they can use
only the data the system had at T0 (2014-01): every month, cohort and outcome read here
is no later than :data:`LAST_KNOWN` (2013-12), and :func:`check_known` refuses anything
later. The simulation 2014 to 2018 then is the exam of the frozen thresholds.

The models are the pair of champions at T0. The PD learns from listings up to about
2010-08 (the cohorts matured at T0), so the months between that and T0 are real history
it never saw. The study measures, on that history:

- **drift** (:func:`drift_study`): a pseudo cutoff every month from 2011-09; the reference
  of each is its 12 months before (D-138), and every later month up to 2013-12 is measured
  against it, at its lag (months after the reference). With the PSI of every subject goes
  its noise: the 99th percentile of the PSI of samples of the same size drawn from the
  reference itself, what chance alone gives;
- **early warning** (:func:`early_warning_study`): the cohorts whose 17 months had passed
  by 2013-12, measured as the monitoring does (D-143);
- **performance** (:func:`performance_study`): the AUC and the calibration error, with
  their bootstrap intervals, of the last six 36-month cohorts matured by 2013-12, against
  the pooled value of the six: the month-to-month spread of a model on its own period;
- **LGD level** (:func:`level_study`): the level correction (D-094) of the baseline LGD
  at a pseudo cutoff every quarter from 2011-01, and the level error on resolved defaults.
"""

import json
import logging
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Final

import numpy as np
import polars as pl
from psycopg import Connection

from credit_risk import lgd as lgd_models
from credit_risk.api.scoring import Champions
from credit_risk.compare import interval
from credit_risk.monitoring.drift import counts, psi
from credit_risk.monitoring.outcomes import early_warning
from credit_risk.monitoring.store import (
    PREDICTIONS,
    SUBJECTS,
    Pair,
    _champions,
    _label,
    add_months,
    first_year_shares,
    kind_of,
    reference_bins,
    reference_months,
    scored_reference,
)
from credit_risk.snapshot import LGD, LGD_AGE_MONTHS, SnapshotError, build_frames
from credit_risk.validation.contract import CHARGE_OFF_LAG_MONTHS

log = logging.getLogger(__name__)

#: The first month of the simulation; nothing from it on is used.
T0: Final = date(2014, 1, 1)
#: The last month whose data the study may read.
LAST_KNOWN: Final = date(2013, 12, 1)
#: The first pseudo cutoff whose reference is entirely after the T0 PD's training data.
FIRST_CUTOFF: Final = date(2011, 9, 1)
#: The longest lag measured: a reference serves until the next promotion.
MAX_LAG: Final = 11
#: Draws of the noise of the PSI, and its percentile.
NOISE_DRAWS: Final = 200
NOISE_PERCENTILE: Final = 99
#: The cohorts of the performance study: the last six 36-month cohorts matured by 2013-12.
PERFORMANCE_COHORTS: Final = 6
#: Pseudo cutoffs of the LGD level study: every quarter from here to LAST_KNOWN.
FIRST_LEVEL_CUTOFF: Final = date(2011, 1, 1)
SEED: Final = 0


class FutureDataError(ValueError):
    """The study was handed data from after what was known at T0."""


def check_known(what: str, months: Iterable[date]) -> None:
    """Refuse any month after :data:`LAST_KNOWN` (T33.1)."""
    late = sorted(m for m in months if m > LAST_KNOWN)
    if late:
        raise FutureDataError(f"{what}: {late[0]:%Y-%m} is after {LAST_KNOWN:%Y-%m}, unknown at T0")


def months_between(first: date, last: date) -> list[date]:
    out, month = [], first
    while month <= last:
        out.append(month)
        month = add_months(month, 1)
    return out


# ---------------------------------------------------------------- drift


def scored_months(conn: Connection, champions: Champions, months: list[date]) -> pl.DataFrame:
    """Every listing of ``months`` scored by the champions, with its month."""
    check_known("scored months", months)
    parts = []
    for month in months:
        try:
            frame = scored_reference(conn, champions, [month])
        except ValueError:
            continue  # a month with no listings
        parts.append(frame.with_columns(period=pl.lit(month)))
    return pl.concat(parts)


def noise(shares: tuple[float, ...], n: int, rng: np.random.Generator) -> float:
    """The PSI chance alone gives: percentile of the PSI of ``n`` draws from ``shares``."""
    p = np.asarray(shares, np.float64)
    draws = rng.multinomial(n, p / p.sum(), size=NOISE_DRAWS) / n
    values = [psi(p, d) for d in draws]
    return float(np.percentile(values, NOISE_PERCENTILE))


@dataclass(frozen=True)
class DriftRow:
    cutoff: str
    month: str
    lag: int
    subject: str
    kind: str
    rows: int
    psi: float
    noise: float


def drift_study(scored: pl.DataFrame, last: date = LAST_KNOWN) -> list[DriftRow]:
    """PSI of every subject of every month after each pseudo cutoff, at its lag."""
    check_known("drift months", scored["period"].unique().to_list())
    rng = np.random.default_rng(SEED)
    out = []
    for cutoff in months_between(FIRST_CUTOFF, last):
        reference = scored.filter(pl.col("period").is_in(reference_months(cutoff)))
        bins = {b.subject: b for b in reference_bins(reference)}
        for lag in range(MAX_LAG + 1):
            month = add_months(cutoff, lag)
            if month > last:
                break
            frame = scored.filter(pl.col("period") == month)
            for subject in SUBJECTS:
                values = frame[subject]
                if kind_of(subject) == "prediction":
                    values = values.drop_nulls()
                if values.len() == 0:
                    continue
                found = counts(bins[subject], values)
                shares = found / found.sum()
                out.append(
                    DriftRow(
                        cutoff=f"{cutoff:%Y-%m}",
                        month=f"{month:%Y-%m}",
                        lag=lag,
                        subject=subject,
                        kind=kind_of(subject),
                        rows=values.len(),
                        psi=round(psi(bins[subject].shares, shares), 6),
                        noise=round(noise(bins[subject].shares, values.len(), rng), 6),
                    )
                )
    return out


# ---------------------------------------------------------------- early warning


def _outcomes(conn: Connection, listed: date, at: date) -> pl.DataFrame:
    rows = conn.execute(
        """
        SELECT l.id, o.loan_status, o.last_pymnt_d
        FROM clean.listings AS l
        LEFT JOIN clean.outcomes AS o ON o.id = l.id AND o.period <= %(at)s::date
        WHERE l.period = %(listed)s
        """,
        {"listed": listed, "at": at},
    ).fetchall()
    return pl.DataFrame(
        [{"loan_id": i, "status": s, "last_paid": p} for i, s, p in rows],
        schema={"loan_id": pl.Int64(), "status": pl.String(), "last_paid": pl.Date()},
    )


@dataclass(frozen=True)
class EarlyRow:
    cohort: str
    evaluated: str
    term: int
    loans: int
    defaults: int
    ratio: float
    ratio_low: float
    ratio_high: float


def early_warning_study(
    conn: Connection, scored: pl.DataFrame, last: date = LAST_KNOWN
) -> list[EarlyRow]:
    """The early warning (D-143) of every cohort measured at 17 months by ``last``."""
    from credit_risk.monitoring.outcomes import EARLY_AFTER, EARLY_MONTHS

    shares = first_year_shares(conn, last)
    out = []
    for listed in sorted(scored["period"].unique().to_list()):
        at = add_months(listed, EARLY_AFTER)
        if at > last:
            continue
        check_known("early warning", [listed, at])
        known = _outcomes(conn, listed, at)
        loans = scored.filter((pl.col("period") == listed) & pl.col("pd").is_not_null()).join(
            known, on="loan_id", how="left"
        )
        last_early = add_months(listed, EARLY_MONTHS - 1)
        early = [
            _label(s) == 1 and (p is None or p.replace(day=1) <= last_early)
            for s, p in zip(loans["status"].to_list(), loans["last_paid"].to_list(), strict=True)
        ]
        frame = loans.select(
            pl.col("term").cast(pl.Int64), pl.col("grade"), pl.col("pd")
        ).with_columns(early=pl.Series(early))
        for r in early_warning(frame, shares):
            out.append(
                EarlyRow(
                    cohort=f"{listed:%Y-%m}",
                    evaluated=f"{at:%Y-%m}",
                    term=r.term,
                    loans=r.loans,
                    defaults=r.defaults,
                    ratio=round(r.ratio, 6),
                    ratio_low=round(r.ratio_low, 6),
                    ratio_high=round(r.ratio_high, 6),
                )
            )
    return out


# ---------------------------------------------------------------- performance


@dataclass(frozen=True)
class PerformanceRow:
    cohort: str
    loans: int
    defaults: int
    auc: float
    auc_low: float
    auc_high: float
    calibration_error: float
    calibration_low: float
    calibration_high: float


def _labelled(conn: Connection, champions: Champions, months: list[date]) -> pl.DataFrame:
    at = LAST_KNOWN
    frames = []
    for month in months:
        check_known("performance", [month])
        scored = scored_reference(conn, champions, [month]).filter(
            (pl.col("term") == 36) & pl.col("pd").is_not_null()
        )
        known = _outcomes(conn, month, at)
        frame = scored.join(known, on="loan_id", how="left").with_columns(
            label=pl.col("status").map_elements(_label, return_dtype=pl.Int16),
            period=pl.lit(month),
        )
        frames.append(frame.filter(pl.col("label").is_not_null()).select("period", "pd", "label"))
    return pl.concat(frames)


def performance_study(conn: Connection, champions: Champions) -> dict[str, Any]:
    """AUC and calibration error of each of the last matured 36-month cohorts, and pooled."""
    newest = add_months(LAST_KNOWN, -(36 + CHARGE_OFF_LAG_MONTHS))
    months = [add_months(newest, -k) for k in range(PERFORMANCE_COHORTS - 1, -1, -1)]
    loans = _labelled(conn, champions, months)

    def metrics(frame: pl.DataFrame) -> tuple[tuple[float, ...], tuple[float, ...]]:
        y = frame["label"].to_numpy().astype(np.float64)
        p = frame["pd"].to_numpy().astype(np.float64)
        return interval(y, p, "auc", seed=SEED), interval(y, p, "calibration_error", seed=SEED)

    rows = []
    for month in months:
        frame = loans.filter(pl.col("period") == month)
        a, c = metrics(frame)
        rows.append(
            PerformanceRow(
                cohort=f"{month:%Y-%m}",
                loans=frame.height,
                defaults=int(frame["label"].sum()),
                auc=round(a[0], 6),
                auc_low=round(a[1], 6),
                auc_high=round(a[2], 6),
                calibration_error=round(c[0], 6),
                calibration_low=round(c[1], 6),
                calibration_high=round(c[2], 6),
            )
        )
    a, c = metrics(loans)
    pooled = {"auc": round(a[0], 6), "calibration_error": round(c[0], 6)}
    return {"cohorts": [asdict(r) for r in rows], "pooled": pooled}


# ---------------------------------------------------------------- LGD level


def level_study(conn: Connection) -> list[dict[str, Any]]:
    """The level correction of the baseline LGD at a pseudo cutoff every quarter."""
    out = []
    cutoff = FIRST_LEVEL_CUTOFF
    while cutoff <= LAST_KNOWN:
        check_known("level", [cutoff])
        try:
            with conn.transaction():
                features, _, _ = build_frames(conn, cutoff)
        except SnapshotError:
            cutoff = add_months(cutoff, 3)
            continue  # nothing matured yet
        rows = lgd_models.lgd_rows(features)
        train = rows.filter(pl.col("split") == "train")
        validation = rows.filter(pl.col("split") == "validation")
        if train.height and validation.height:
            model = lgd_models.fit_level(lgd_models.fit_baseline(train, (36, 60)), validation)
            out.append(
                {
                    "cutoff": f"{cutoff:%Y-%m}",
                    "train": train.height,
                    "validation": validation.height,
                    "observed": round(float(validation[LGD].mean()), 6),  # type: ignore[arg-type]
                    "shift": round(model.shift, 6),
                }
            )
        cutoff = add_months(cutoff, 3)
    return out


# ---------------------------------------------------------------- the study


def t0_pair(conn: Connection) -> Pair:
    """The pair of champions trained at T0: the one that scored the first month served."""
    row = conn.execute(
        "SELECT pd_version, lgd_version FROM serving.predictions"
        " ORDER BY listed, prediction_id LIMIT 1"
    ).fetchone()
    if row is None:
        raise ValueError("no prediction yet: run the simulation past T0 first (make exam)")
    return (row[0], row[1])


def study(conn: Connection, pair: Pair, prefix: str = "") -> dict[str, Any]:
    """Every part of the study, for the pair of champions at T0."""
    champions = _champions(pair, prefix)
    first = add_months(FIRST_CUTOFF, -12)
    scored = scored_months(conn, champions, months_between(first, LAST_KNOWN))
    log.info("scored %d listings from %s to %s", scored.height, first, LAST_KNOWN)
    return {
        "pair": list(pair),
        "last_known": f"{LAST_KNOWN:%Y-%m}",
        "lgd_age_months": LGD_AGE_MONTHS,
        "drift": [asdict(r) for r in drift_study(scored)],
        "early_warning": [asdict(r) for r in early_warning_study(conn, scored)],
        "performance": performance_study(conn, champions),
        "level": level_study(conn),
    }


def save(result: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")


# ---------------------------------------------------------------- from the study to values

#: The values a PSI threshold is chosen from (D-156).
PSI_GRID: Final = (0.10, 0.15, 0.20, 0.25)
#: The lags of a fresh reference: with the quarterly retraining (D-106) a reference is at
#: most this many months old when it is replaced.
FRESH_LAGS: Final = 2
#: The values a threshold on the level of the LGD is chosen from (D-151, D-156).
LEVEL_GRID: Final = (0.05, 0.10, 0.15, 0.20)
#: Rules that are not read from the data: the early warning fires when its whole
#: interval says more defaults than expected (Juan, D-156), and a matured cohort is
#: clearly worse with the margins of a segment clearly worse at promotion (D-093).
RATIO_LOW: Final = 1.0
MARGIN: Final = 0.01


def summary(result: Mapping[str, Any]) -> dict[str, Any]:
    """The part of the study that sets the thresholds and is published (docs/thresholds.md)."""
    drift = pl.DataFrame(result["drift"])
    predictions = (
        drift.filter(pl.col("kind") == "prediction")
        .group_by("subject", "lag")
        .agg(
            months=pl.len(),
            median=pl.col("psi").median().round(3),
            max=pl.col("psi").max().round(3),
            noise=pl.col("noise").median().round(3),
        )
        .sort("subject", "lag")
    )
    inputs = (
        drift.filter((pl.col("kind") != "prediction") & (pl.col("lag") <= FRESH_LAGS))
        .group_by("subject")
        .agg(max=pl.col("psi").max().round(3), noise=pl.col("noise").median().round(3))
        .sort("max", "subject", descending=[True, False])
        .head(5)
    )
    return {
        "pair": result["pair"],
        "last_known": result["last_known"],
        "prediction_drift": predictions.to_dicts(),
        "input_drift": inputs.to_dicts(),
        "early_warning": [
            {k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items()}
            for row in result["early_warning"]
        ],
        "performance": {
            "cohorts": [
                {k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items()}
                for row in result["performance"]["cohorts"]
            ],
            "pooled": {k: round(v, 3) for k, v in result["performance"]["pooled"].items()},
        },
        "level": [
            {k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items()}
            for row in result["level"]
        ],
    }


def _first_above(grid: Iterable[float], largest: float, what: str) -> float:
    for value in grid:
        if value >= largest:
            return value
    raise ValueError(f"{what}: {largest} is above every value of the grid")


def propose(found: Mapping[str, Any]) -> dict[str, dict[str, float]]:
    """The thresholds the written rules of the study give (T33.3), by section of the file.

    - the PSI of a prediction: the smallest value of :data:`PSI_GRID` that no month
      exceeded with a fresh reference (lags 0 to :data:`FRESH_LAGS`);
    - the early warning and the margins of performance: the fixed rules above;
    - the level of the LGD: the first value of :data:`LEVEL_GRID` above every level
      correction before T0.
    """
    out: dict[str, dict[str, float]] = {}
    for prediction in PREDICTIONS:
        largest = max(
            row["max"]
            for row in found["prediction_drift"]
            if row["subject"] == prediction and row["lag"] <= FRESH_LAGS
        )
        out[f"prediction_drift.{prediction}"] = {
            "psi": _first_above(PSI_GRID, largest, f"PSI of {prediction}")
        }
    level = _first_above(
        (v for v in LEVEL_GRID if v > max(abs(r["shift"]) for r in found["level"])),
        0.0,
        "LGD level",
    )
    out["early_warning"] = {"ratio_low": RATIO_LOW}
    out["performance"] = {"auc_margin": MARGIN, "calibration_margin": MARGIN, "lgd_level": level}
    out["lgd_level_shift"] = {"shift": level}
    return out


def _row(*cells: object) -> str:
    return "| " + " | ".join(str(c) for c in cells) + " |"


def tables(found: Mapping[str, Any]) -> str:
    """The tables of docs/thresholds.md, in Markdown (T33.2 checks the published ones)."""
    lines = [
        f"Pair of champions at T0: PD {found['pair'][0]}, LGD {found['pair'][1]}. "
        f"Data up to {found['last_known']}.",
        "",
        "**PSI of the predictions by lag** (months after the reference): median and largest "
        "over the months measured; noise is the median of what chance alone gives.",
        "",
        _row("Prediction", "Lag", "Months", "Median", "Largest", "Noise"),
        _row(*["---"] * 6),
    ]
    for r in found["prediction_drift"]:
        lines.append(_row(r["subject"], r["lag"], r["months"], r["median"], r["max"], r["noise"]))
    lines += [
        "",
        f"**The input variables that moved most** with a reference 0 to {FRESH_LAGS} months "
        "old (they never alert, D-149):",
        "",
        _row("Variable", "Largest PSI", "Noise"),
        _row(*["---"] * 3),
    ]
    lines += [_row(r["subject"], r["max"], r["noise"]) for r in found["input_drift"]]
    lines += [
        "",
        "**Early warning** of every cohort measured by T0 (observed / expected first-year "
        f"defaults, 95% interval; fires above {RATIO_LOW}):",
        "",
        _row("Cohort", "Term", "Loans", "Defaults", "Ratio", "Low", "High", "Fires"),
        _row(*["---"] * 8),
    ]
    for r in found["early_warning"]:
        fires = "yes" if r["ratio_low"] > RATIO_LOW else ""
        lines.append(
            _row(r["cohort"], r["term"], r["loans"], r["defaults"], r["ratio"],
                 r["ratio_low"], r["ratio_high"], fires)
        )  # fmt: skip
    pooled = found["performance"]["pooled"]
    lines += [
        "",
        "**Performance of the last matured 36-month cohorts** (pooled AUC "
        f"{pooled['auc']}, calibration error {pooled['calibration_error']}):",
        "",
        _row("Cohort", "Loans", "Defaults", "AUC", "AUC low", "AUC high", "Calibration",
             "Cal. low", "Cal. high"),
        _row(*["---"] * 9),
    ]  # fmt: skip
    for r in found["performance"]["cohorts"]:
        lines.append(
            _row(r["cohort"], r["loans"], r["defaults"], r["auc"], r["auc_low"], r["auc_high"],
                 r["calibration_error"], r["calibration_low"], r["calibration_high"])
        )  # fmt: skip
    lines += [
        "",
        "**Level correction of the baseline LGD** at a pseudo cutoff every quarter:",
        "",
        _row("Cutoff", "Train", "Validation", "Observed LGD", "Correction"),
        _row(*["---"] * 5),
    ]
    for r in found["level"]:
        lines.append(_row(r["cutoff"], r["train"], r["validation"], r["observed"], r["shift"]))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- the exam

#: The kinds of alert the thresholds decide (D-149).
THRESHOLD_KINDS: Final = (
    "prediction_drift",
    "early_warning",
    "performance_drop",
    "lgd_level_shift",
)
#: The last month of the simulation: the exam is over when it has been monitored.
EXAM_LAST: Final = date(2018, 12, 1)


def _what(kind: str, details: Mapping[str, Any]) -> str:
    if kind == "prediction_drift":
        return f"{details['subject']} {details['psi']:.2f}"
    if kind == "early_warning":
        return f"{details['term']}m {details['cohort']} {details['ratio_low']:.2f}"
    if kind == "performance_drop":
        return f"{details['metric']} {details['term']}m {details['cohort']}"
    return f"{details['shift']:+.2f}"


def exam(conn: Connection) -> list[dict[str, Any]]:
    """The alerts the frozen thresholds raised in the simulation, by month and kind."""
    rows = conn.execute(
        "SELECT kind, coalesce(period, date_trunc('month', at)::date) AS month, details"
        " FROM ops.alerts WHERE kind = ANY(%s) ORDER BY month, kind, alert_id",
        (list(THRESHOLD_KINDS),),
    ).fetchall()
    out: dict[tuple[str, str], list[str]] = {}
    for kind, month, details in rows:
        out.setdefault((f"{month:%Y-%m}", kind), []).append(_what(kind, details))
    return [
        {"month": month, "kind": kind, "alerts": len(what), "what": "; ".join(what)}
        for (month, kind), what in out.items()
    ]


def exam_table(found: list[dict[str, Any]]) -> str:
    """The table of the exam in docs/thresholds.md (T33.4 checks the published one)."""
    lines = [_row("Month", "Kind", "Alerts", "What"), _row(*["---"] * 4)]
    lines += [_row(r["month"], r["kind"], r["alerts"], r["what"]) for r in found]
    totals = {k: sum(r["alerts"] for r in found if r["kind"] == k) for k in THRESHOLD_KINDS}
    lines += ["", "Totals: " + ", ".join(f"{k} {n}" for k, n in totals.items()) + "."]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- what is published

#: Where the summaries are committed, and the document that publishes them.
SUMMARY: Final = Path("reports/thresholds/summary.json")
EXAM: Final = Path("reports/thresholds/exam.json")
DOCUMENT: Final = Path("docs/thresholds.md")
#: The markers around the generated tables inside the document.
BEGIN: Final = "<!-- study tables: generated by make calibrate, do not edit -->"
END: Final = "<!-- end of the study tables -->"
EXAM_BEGIN: Final = "<!-- exam table: generated by make calibrate, do not edit -->"
EXAM_END: Final = "<!-- end of the exam table -->"


def published(document: str, begin: str = BEGIN, end: str = END) -> str:
    """The tables between two markers of the document."""
    start = document.index(begin) + len(begin)
    return document[start : document.index(end)].strip("\n") + "\n"


def main() -> None:  # pragma: no cover - thin command line, run by make calibrate
    import argparse

    import psycopg

    from credit_risk.settings import Settings

    parser = argparse.ArgumentParser(description="The study of the alert thresholds (D-150).")
    parser.add_argument("--prefix", default="", help="prefix of the model names")
    parser.add_argument("--full", type=Path, help="also write the whole study here")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    with psycopg.connect(Settings().postgres_conninfo(), autocommit=True) as conn:
        result = study(conn, t0_pair(conn), args.prefix)
        last = conn.execute("SELECT max(period) FROM monitoring.drift").fetchone()
        alerts = exam(conn) if last is not None and last[0] and last[0] >= EXAM_LAST else None
    if args.full:
        save(result, args.full)
    found = summary(result)
    save(found, SUMMARY)
    document = DOCUMENT.read_text()
    document = document.replace(published(document), tables(found))
    if alerts is not None:
        save({"alerts": alerts}, EXAM)
        document = document.replace(published(document, EXAM_BEGIN, EXAM_END), exam_table(alerts))
    else:
        log.info("the exam is not over: its table stays as it is")
    DOCUMENT.write_text(document)
    log.info("proposed thresholds: %s", propose(found))


if __name__ == "__main__":  # pragma: no cover
    main()


__all__ = ["PREDICTIONS", "FutureDataError", "check_known", "propose", "study", "summary"]
