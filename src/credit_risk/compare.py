"""Comparing two models: the paired bootstrap (D-075) and the key segments (D-081).

One function, :func:`paired_bootstrap`, decides every "is the new model better than the
current one by more than the noise": logistic regression against LightGBM (D-068), the
chosen model against the baseline (D-090) and a challenger against the champion (D-082).

The difference is always taken as an **improvement**: new minus current for a metric
where higher is better (AUC), current minus new where lower is better (Brier score,
RMSE, calibration error). The new model is *better* when the whole 95% interval of the
improvement is above zero, *worse* when the whole interval is below zero.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Final

import numpy as np
import numpy.typing as npt
import polars as pl
from scipy.stats import rankdata

Array = npt.NDArray[np.float64]
Mask = npt.NDArray[np.bool_]
Metric = Callable[[Array, Array], float]

RESAMPLES: Final = 1_000
LEVEL: Final = 0.95
#: D-081: a segment with fewer events than this is merged with its neighbour.
MIN_SEGMENT_EVENTS: Final = 50
#: D-093: how much worse a segment must be, for sure, to block a promotion.
PD_MARGINS: Final = {"auc": 0.01, "calibration_error": 0.01}
LGD_MARGINS: Final = {"calibration_error": 0.02}


def auc(y: Array, score: Array) -> float:
    """Area under the ROC curve (Mann-Whitney), ties counted as half."""
    positives = y == 1
    n_pos = int(positives.sum())
    n_neg = y.size - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    ranks = rankdata(score)
    return float((ranks[positives].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def brier(y: Array, p: Array) -> float:
    return float(np.mean((p - y) ** 2))


def rmse(y: Array, p: Array) -> float:
    return float(np.sqrt(np.mean((p - y) ** 2)))


def calibration_error(y: Array, p: Array) -> float:
    """Absolute difference between the mean prediction and the mean outcome (D-081)."""
    return float(abs(np.mean(p) - np.mean(y)))


#: Whether a higher value of each metric is better.
HIGHER_IS_BETTER: Final[Mapping[str, bool]] = {
    "auc": True,
    "brier": False,
    "rmse": False,
    "calibration_error": False,
}
METRICS: Final[Mapping[str, Metric]] = {
    "auc": auc,
    "brier": brier,
    "rmse": rmse,
    "calibration_error": calibration_error,
}


@dataclass(frozen=True)
class Comparison:
    """Result of a paired bootstrap; ``improvements`` holds one value per resample."""

    metric: str
    new: float
    current: float
    low: float
    high: float
    improvements: Array

    @property
    def better(self) -> bool:
        """The whole interval of the improvement is above zero."""
        return self.low > 0

    @property
    def worse(self) -> bool:
        """The whole interval of the improvement is below zero."""
        return self.high < 0


def _resample(y: Array, rng: np.random.Generator, stratify: bool) -> npt.NDArray[np.intp]:
    # Stratifying only makes sense for a 0/1 label; a continuous one (LGD) is drawn plainly.
    if not stratify or not np.isin(y, (0.0, 1.0)).all():
        return rng.integers(0, y.size, y.size)
    # Each resample keeps the number of defaults and of non-defaults (D-075).
    groups = [np.flatnonzero(y == value) for value in np.unique(y)]
    return np.concatenate([rng.choice(g, g.size, replace=True) for g in groups])


def paired_bootstrap(
    y: Array,
    new: Array,
    current: Array,
    metric: str,
    *,
    resamples: int = RESAMPLES,
    seed: int = 0,
    stratify: bool = True,
) -> Comparison:
    """Compare two models' predictions on the same loans (D-075).

    Each resample draws the loans with replacement (keeping the number of defaults when
    ``stratify``), scores both models on the *same* draw and keeps the improvement.
    """
    score = METRICS[metric]
    sign = 1.0 if HIGHER_IS_BETTER[metric] else -1.0
    rng = np.random.default_rng(seed)
    improvements = np.empty(resamples)
    for i in range(resamples):
        idx = _resample(y, rng, stratify)
        improvements[i] = sign * (score(y[idx], new[idx]) - score(y[idx], current[idx]))
    tail = (1 - LEVEL) / 2 * 100
    low, high = np.nanpercentile(improvements, [tail, 100 - tail])
    return Comparison(
        metric=metric,
        new=score(y, new),
        current=score(y, current),
        low=float(low),
        high=float(high),
        improvements=improvements,
    )


def interval(
    y: Array, p: Array, metric: str, *, resamples: int = RESAMPLES, seed: int = 0
) -> tuple[float, float, float]:
    """A metric of one model with its 95% bootstrap interval: (value, low, high)."""
    score = METRICS[metric]
    rng = np.random.default_rng(seed)
    values = np.empty(resamples)
    for i in range(resamples):
        idx = _resample(y, rng, stratify=True)
        values[i] = score(y[idx], p[idx])
    tail = (1 - LEVEL) / 2 * 100
    low, high = np.nanpercentile(values, [tail, 100 - tail])
    value = score(y, p)
    # A metric bounded at zero (the calibration error) can sit below every resample when
    # it is close to zero; the interval is widened to hold the value itself (E-036).
    return value, float(min(low, value)), float(max(high, value))


# ---------------------------------------------------------------- segments (D-081)


def _merge(groups: list[tuple[str, Mask]], events: Array, minimum: int) -> list[tuple[str, Mask]]:
    """Merge every group with fewer than ``minimum`` events into its next neighbour (the
    previous one for the last group), until all reach it or one group is left."""
    groups = [(name, mask) for name, mask in groups if mask.any()]
    while len(groups) > 1:
        counts = [float(events[mask].sum()) for _, mask in groups]
        small = next((i for i, n in enumerate(counts) if n < minimum), None)
        if small is None:
            break
        other = small + 1 if small + 1 < len(groups) else small - 1
        first, second = sorted((small, other))
        name = f"{groups[first][0]}+{groups[second][0]}"
        merged = (name, groups[first][1] | groups[second][1])
        groups = [*groups[:first], merged, *groups[second + 1 :]]
    return groups


def segments(
    frame: pl.DataFrame,
    events: Array,
    covered_terms: tuple[int, ...],
    minimum: int = MIN_SEGMENT_EVENTS,
) -> dict[str, Mask]:
    """The blocking segments of D-081 over the rows of ``frame``.

    ``grade`` (F and G together), ``term`` (covered terms only) and the listing quarter
    (``issue_d``). ``events`` counts what makes a segment big enough: the defaults for
    the PD, every row for the LGD.
    """
    grade = frame["grade"].to_numpy()
    grades = [(g, grade == g) for g in ("A", "B", "C", "D", "E")]
    grades.append(("F+G", (grade == "F") | (grade == "G")))
    term = frame["term"].to_numpy()
    terms = [(f"{t} months", term == t) for t in covered_terms]
    issue = frame["issue_d"]
    quarter = (issue.dt.year().cast(pl.Int32) * 10 + issue.dt.quarter()).to_numpy()
    quarters = [(f"{q // 10}Q{q % 10}", quarter == q) for q in sorted(np.unique(quarter).tolist())]
    result: dict[str, Mask] = {}
    for kind, groups in (("grade", grades), ("term", terms), ("quarter", quarters)):
        for name, mask in _merge(groups, events, minimum):
            result[f"{kind} {name}"] = mask
    return result


@dataclass(frozen=True)
class SegmentResult:
    segment: str
    comparison: Comparison
    margin: float = 0.0

    @property
    def blocking(self) -> bool:
        """Clearly worse by more than the margin (D-093): the whole interval of the
        improvement lies below minus the margin."""
        return self.comparison.high < -self.margin


def segment_check(
    y: Array,
    new: Array,
    current: Array,
    masks: Mapping[str, Mask],
    metrics: tuple[str, ...] = ("auc", "calibration_error"),
    *,
    margins: Mapping[str, float] | None = None,
    resamples: int = RESAMPLES,
    seed: int = 0,
    stratify: bool = True,
) -> list[SegmentResult]:
    """Paired bootstrap of each metric inside each segment (D-081)."""
    results = []
    for name, mask in masks.items():
        for metric in metrics:
            if metric == "auc" and np.unique(y[mask]).size < 2:
                continue
            comparison = paired_bootstrap(
                y[mask],
                new[mask],
                current[mask],
                metric,
                resamples=resamples,
                seed=seed,
                stratify=stratify,
            )
            margin = (margins or {}).get(metric, 0.0)
            results.append(SegmentResult(name, comparison, margin))
    return results


def segments_pass(results: list[SegmentResult]) -> bool:
    """D-081: the new model fails if it is clearly worse in any segment, on any metric, by
    more than the margin of that metric (D-093)."""
    return not any(r.blocking for r in results)


def choose(lightgbm_vs_logistic: Comparison) -> str:
    """D-068: LightGBM only if it beats the logistic regression by more than the noise."""
    return "lightgbm" if lightgbm_vs_logistic.better else "logistic"
