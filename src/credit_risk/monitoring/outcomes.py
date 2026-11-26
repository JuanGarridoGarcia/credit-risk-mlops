"""What the outcomes say about the models: early warning (D-143) and real performance (D-144).

Labels arrive late: a loan is known to be good only when it ends, 3 to 5 years after it
was listed. Two measures use what is known in time:

- **early warning**, 17 months after a cohort is listed: the share of its loans that
  stopped paying within 12 months of issue (first missed payment no later than month 12)
  against what the PD expected for them, ``PD x the share of defaults that come in the
  first year``, by term and grade, measured on the cohorts that had matured at the PD's
  cutoff (D-040). The ratio observed / expected carries a 95% Wilson interval;
- **real performance**, when a cohort has matured (term + 5 months, D-040): the metrics
  of promotion (:mod:`credit_risk.compare`), overall and by grade, the LGD against the loss
  of the defaults resolved at least 12 months before (D-017), and the realised return of
  what the investor bought (:mod:`credit_risk.business`).

Everything here is pure: :mod:`credit_risk.monitoring.store` reads the rows and writes the
results.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Final

import numpy as np
import numpy.typing as npt
import polars as pl

from credit_risk.business import NOTE, received
from credit_risk.compare import auc, brier, calibration_error, rmse

#: Months after listing when the 12-month default rate of a cohort is known: 12 months,
#: plus the 5 months to the charge-off (data_audit.md 4.2), with one to spare.
EARLY_AFTER: Final = 17
#: First missed payment no later than this many months after issue (D-003).
EARLY_MONTHS: Final = 12
#: Fewer defaults than this in a term and grade: the term's share is used instead.
MIN_DEFAULTS: Final = 50
#: Normal quantile of the 95% Wilson interval.
Z: Final = 1.959963984540054
#: The segment of a performance row that holds the whole cohort.
ALL: Final = "all"


@dataclass(frozen=True)
class FirstYear:
    """Share of the defaults that come in the first year, by term and grade."""

    by_grade: Mapping[tuple[int, str], float]
    by_term: Mapping[int, float]

    def share(self, term: int, grade: str) -> float | None:
        found = self.by_grade.get((term, grade))
        return found if found is not None else self.by_term.get(term)


def first_year(rows: list[tuple[int, str, int, int]]) -> FirstYear:
    """From ``(term, grade, defaults, early defaults)``: the shares, grade by grade.

    A grade with fewer than :data:`MIN_DEFAULTS` defaults takes the share of its term.
    """
    by_grade: dict[tuple[int, str], float] = {}
    totals: dict[int, list[int]] = {}
    for term, grade, defaults, early in rows:
        if not 0 <= early <= defaults:
            raise ValueError(f"{term} months, grade {grade}: {early} early of {defaults}")
        total = totals.setdefault(term, [0, 0])
        total[0] += defaults
        total[1] += early
        if defaults >= MIN_DEFAULTS:
            by_grade[(term, grade)] = early / defaults
    by_term = {term: e / d for term, (d, e) in totals.items() if d > 0}
    return FirstYear(by_grade, by_term)


def wilson(successes: int, n: int, z: float = Z) -> tuple[float, float]:
    """95% Wilson interval of a proportion; it always contains ``successes / n``."""
    if n <= 0:
        raise ValueError("an interval needs at least one case")
    p = successes / n
    denominator = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    # In exact arithmetic the interval contains p; in floating point centre - half can
    # land a hair above 0 when p = 0 (E-057), so the bounds are clamped to p.
    return min(p, max(0.0, centre - half)), max(p, min(1.0, centre + half))


def _auc(y: npt.NDArray[np.float64], score: npt.NDArray[np.float64]) -> float | None:
    value = auc(y.astype(np.float64), score.astype(np.float64))
    return None if math.isnan(value) else value


@dataclass(frozen=True)
class EarlyWarning:
    """The 12-month default rate of one cohort and term, against what was expected."""

    term: int
    loans: int
    defaults: int
    expected_defaults: float
    observed_rate: float
    expected_rate: float
    ratio: float
    ratio_low: float
    ratio_high: float
    auc: float | None


def early_warning(loans: pl.DataFrame, shares: FirstYear) -> list[EarlyWarning]:
    """One result per term of ``loans``: columns ``term``, ``grade``, ``pd`` and ``early``.

    ``early`` is whether the loan stopped paying within 12 months, as known now. A term
    whose share of first-year defaults is unknown (no default at all at the cutoff) has no
    result.
    """
    out = []
    for (term,), group in sorted(loans.group_by("term"), key=lambda g: int(g[0][0])):
        term = int(term)
        weights = [shares.share(term, str(g)) for g in group["grade"].to_list()]
        if any(w is None for w in weights):
            continue
        pd_ = group["pd"].to_numpy().astype(np.float64)
        expected = float(np.sum(pd_ * np.asarray(weights, np.float64)))
        y = group["early"].to_numpy().astype(np.float64)
        n, k = group.height, int(y.sum())
        if expected <= 0:
            continue
        expected_rate = expected / n
        low, high = wilson(k, n)
        out.append(
            EarlyWarning(
                term=term,
                loans=n,
                defaults=k,
                expected_defaults=expected,
                observed_rate=k / n,
                expected_rate=expected_rate,
                ratio=(k / n) / expected_rate,
                ratio_low=low / expected_rate,
                ratio_high=high / expected_rate,
                auc=_auc(y, pd_),
            )
        )
    return out


@dataclass(frozen=True)
class Performance:
    """The metrics of one matured cohort, term and segment (``all`` or ``grade=X``)."""

    term: int
    segment: str
    loans: int
    defaults: int
    unresolved: int
    auc: float | None
    brier: float | None
    calibration_error: float | None
    mean_pd: float | None
    default_rate: float | None
    lgd_loans: int | None = None
    lgd_rmse: float | None = None
    lgd_level: float | None = None
    purchases: int | None = None
    invested: float | None = None
    received: float | None = None
    realised_return: float | None = None


def _pd_metrics(term: int, segment: str, group: pl.DataFrame, unresolved: int) -> Performance:
    y = group["label"].to_numpy().astype(np.float64)
    p = group["pd"].to_numpy().astype(np.float64)
    known = group.height > 0
    return Performance(
        term=term,
        segment=segment,
        loans=group.height,
        defaults=int(y.sum()),
        unresolved=unresolved,
        auc=_auc(y, p) if known else None,
        brier=brier(y, p) if known else None,
        calibration_error=calibration_error(y, p) if known else None,
        mean_pd=float(p.mean()) if known else None,
        default_rate=float(y.mean()) if known else None,
    )


def performance(loans: pl.DataFrame) -> list[Performance]:
    """Metrics of one matured cohort of one pair of models.

    ``loans``: ``term``, ``grade``, ``pd``, ``lgd``, ``label`` (1 bad, 0 good, null when
    unresolved or of the old policy), ``lgd_actual`` (the loss of a bad loan resolved at
    least 12 months ago, else null), ``amount`` (dollars bought, 0 when none), and the
    outcome columns of :func:`credit_risk.business.received` (``funded_amnt``,
    ``total_pymnt``, ``collection_recovery_fee``).
    """
    out = []
    for (term,), cohort in sorted(loans.group_by("term"), key=lambda g: int(g[0][0])):
        term = int(term)
        known = cohort.filter(pl.col("label").is_not_null())
        overall = _pd_metrics(term, ALL, known, cohort.height - known.height)
        lgd = known.filter(pl.col("lgd_actual").is_not_null())
        bought = known.filter(pl.col("amount") > 0)
        values, _ = (
            received(bought.select(pl.col("loan_id").alias("id")), _outcomes(bought))
            if bought.height
            else (np.array([], np.float64), None)
        )
        invested = float(bought["amount"].sum()) if bought.height else 0.0
        got = float(np.sum(values / NOTE * bought["amount"].to_numpy())) if bought.height else 0.0
        lgd_rmse = lgd_level = None
        if lgd.height:
            actual = lgd["lgd_actual"].to_numpy().astype(np.float64)
            predicted = lgd["lgd"].to_numpy().astype(np.float64)
            lgd_rmse = rmse(actual, predicted)
            lgd_level = float(predicted.mean() - actual.mean())
        out.append(
            replace(
                overall,
                lgd_loans=lgd.height,
                lgd_rmse=lgd_rmse,
                lgd_level=lgd_level,
                purchases=bought.height,
                invested=invested,
                received=got,
                realised_return=got / invested - 1 if invested else None,
            )
        )
        for (grade,), group in sorted(cohort.group_by("grade"), key=lambda g: str(g[0][0])):
            resolved = group.filter(pl.col("label").is_not_null())
            out.append(
                _pd_metrics(term, f"grade={grade}", resolved, group.height - resolved.height)
            )
    return out


def _outcomes(bought: pl.DataFrame) -> pl.DataFrame:
    return bought.select(
        pl.col("loan_id").alias("id"),
        "label",
        "funded_amnt",
        "total_pymnt",
        "collection_recovery_fee",
    )
