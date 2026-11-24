"""The behavioural battery (D-086): what any model must do before it can be promoted.

It looks at a model only from outside, through ``predict_pd``, so it judges the whole
model as it will be used: learned preparation, estimator and calibration together. Four
kinds of checks:

- **invariance**: fields the model does not use leave the PD unchanged, and a loan gets
  exactly the same PD alone as inside a batch;
- **direction**: raising each of the nine features of D-080 in its risk direction never
  lowers the PD (and the reverse for the protective ones), on real validation loans;
- **minimum cases**: a clearly good profile scores below a clearly bad one, every PD lies
  in [0, 1], empty optional fields are scored, an uncovered term gets no PD (D-070);
- **time**: one prediction takes under 50 ms at the 95th percentile, in process.

A constant model and a random model must fail it (T10.5).
"""

import math
import time
from dataclasses import dataclass, field
from typing import Final, Protocol

import numpy as np
import polars as pl

from credit_risk.explain import explain
from credit_risk.features import FEATURES, FICO, build_features
from credit_risk.model import MONOTONE, PDModel

#: D-086: one prediction, in process, at the 95th percentile.
MAX_LATENCY_MS: Final = 50.0
#: Loans used for the direction check, and points tried for each feature.
DIRECTION_LOANS: Final = 200
DIRECTION_POINTS: Final = 10
SINGLE_LOANS: Final = 50
LATENCY_CALLS: Final = 200
#: Listing fields no model uses: changing them must not move the PD.
UNUSED: Final = {"id": 999_999_999, "emp_title": "Changed title", "addr_state": "ZZ"}

GOOD: Final = {
    "grade": "A", "sub_grade": "A1", FICO: 800.0, "dti": 5.0, "int_rate": 6.0,
    "revol_util": 10.0, "annual_inc": 150_000.0, "delinq_2yrs": 0, "inq_last_6mths": 0,
    "pub_rec": 0,
}  # fmt: skip
BAD: Final = {
    "grade": "G", "sub_grade": "G5", FICO: 640.0, "dti": 35.0, "int_rate": 26.0,
    "revol_util": 95.0, "annual_inc": 25_000.0, "delinq_2yrs": 3, "inq_last_6mths": 5,
    "pub_rec": 2,
}  # fmt: skip
#: Kept filled in the "empty optional fields" case; every other feature is emptied.
ESSENTIAL: Final = ("loan_amnt", "term", "int_rate", "grade", "sub_grade")


class Scorer(Protocol):
    """What the battery needs from a model."""

    @property
    def covered_terms(self) -> tuple[int, ...]: ...

    def predict_pd(self, features: pl.DataFrame) -> pl.Series: ...


@dataclass
class BatteryResult:
    checks: dict[str, bool] = field(default_factory=dict)
    details: dict[str, str] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return all(self.checks.values())


def _same(a: pl.Series, b: pl.Series) -> bool:
    x, y = a.to_numpy(), b.to_numpy()
    return bool(np.array_equal(x, y, equal_nan=True))


def _set(frame: pl.DataFrame, values: dict[str, object]) -> pl.DataFrame:
    return frame.with_columns(
        pl.lit(v, dtype=frame.schema[c]).alias(c) for c, v in values.items() if c in frame
    )


def invariance(model: Scorer, listings: pl.DataFrame, result: BatteryResult) -> None:
    features = build_features(listings)
    changed = build_features(_set(listings, UNUSED))
    result.checks["invariance: unused fields"] = _same(
        model.predict_pd(features), model.predict_pd(changed)
    )
    batch = model.predict_pd(features)
    n = min(SINGLE_LOANS, features.height)
    alone = pl.concat([model.predict_pd(features.slice(i, 1)) for i in range(n)])
    result.checks["invariance: alone or in a batch"] = _same(batch.head(alone.len()), alone)


def direction(model: Scorer, features: pl.DataFrame, result: BatteryResult) -> None:
    loans = features.filter(pl.col("term").is_in(list(model.covered_terms))).head(DIRECTION_LOANS)
    for feature, sign in MONOTONE.items():
        values = loans[feature].cast(pl.Float64).drop_nulls()
        points = np.linspace(0.02, 0.98, DIRECTION_POINTS)
        grid = np.unique(np.quantile(values.to_numpy(), points))
        if loans.schema[feature].is_integer():
            grid = np.unique(np.round(grid))
        integer = loans.schema[feature].is_integer()
        sweep = pl.concat([_set(loans, {feature: round(v) if integer else float(v)}) for v in grid])
        pd_ = model.predict_pd(sweep).to_numpy().reshape(grid.size, loans.height)
        steps = np.diff(pd_, axis=0) * sign
        ok = bool(np.all(steps >= -1e-12))
        result.checks[f"direction: {feature}"] = ok
        if not ok:
            result.details[f"direction: {feature}"] = f"largest wrong step {steps.min():.3g}"


def minimum_cases(model: Scorer, features: pl.DataFrame, result: BatteryResult) -> None:
    covered = features.filter(pl.col("term").is_in(list(model.covered_terms)))
    template = covered.head(1)
    good = model.predict_pd(_set(template, GOOD))[0]
    bad = model.predict_pd(_set(template, BAD))[0]
    result.checks["minimum: good profile below bad profile"] = (
        good is not None and bad is not None and good < bad
    )
    result.details["minimum: good profile below bad profile"] = f"{good} < {bad}"
    pd_ = model.predict_pd(covered).to_numpy()
    result.checks["minimum: every PD in [0, 1]"] = bool(
        np.all(np.isfinite(pd_)) and np.all((pd_ >= 0) & (pd_ <= 1))
    )
    empty = template.with_columns(
        pl.lit(None, dtype=template.schema[c]).alias(c) for c in FEATURES if c not in ESSENTIAL
    )
    value = model.predict_pd(empty)[0]
    result.checks["minimum: empty optional fields are scored"] = value is not None and (
        0 <= value <= 1
    )
    uncovered = next(t for t in (60, 36, 48, 12) if t not in model.covered_terms)
    result.checks["minimum: an uncovered term gets no PD"] = (
        model.predict_pd(_set(template, {"term": uncovered}))[0] is None
    )


def latency(model: Scorer, features: pl.DataFrame, result: BatteryResult) -> None:
    rows = features.head(LATENCY_CALLS)
    times = []
    for i in range(rows.height):
        one = rows.slice(i, 1)
        start = time.perf_counter()
        model.predict_pd(one)
        if isinstance(model, PDModel):
            # The PD is served with its explanation (D-083), so both are timed.
            explain(model, one)
        times.append((time.perf_counter() - start) * 1000)
    p95 = float(np.percentile(times, 95))
    result.checks["time: p95 under 50 ms"] = p95 < MAX_LATENCY_MS
    result.details["time: p95 under 50 ms"] = f"{p95:.1f} ms"


def run(model: Scorer, listings: pl.DataFrame) -> BatteryResult:
    """The whole battery on validation ``listings`` (listing columns, as in the snapshot)."""
    result = BatteryResult()
    features = build_features(listings)
    invariance(model, listings, result)
    direction(model, features, result)
    minimum_cases(model, features, result)
    latency(model, features, result)
    return result


@dataclass
class ConstantModel:
    """A model that gives every covered loan the same PD (T10.5)."""

    covered_terms: tuple[int, ...]
    value: float = 0.1

    def predict_pd(self, features: pl.DataFrame) -> pl.Series:
        covered = features["term"].is_in(list(self.covered_terms))
        return pl.select(
            pl.when(covered).then(pl.lit(self.value)).otherwise(None).alias("pd")
        ).to_series()


@dataclass
class RandomModel:
    """A model that answers at random, a new draw at every call (T10.5)."""

    covered_terms: tuple[int, ...]
    rng: np.random.Generator = field(default_factory=lambda: np.random.default_rng(0))

    def predict_pd(self, features: pl.DataFrame) -> pl.Series:
        covered = features["term"].is_in(list(self.covered_terms)).to_numpy()
        values = np.where(covered, self.rng.random(features.height), math.nan)
        return pl.Series("pd", values, dtype=pl.Float64).fill_nan(None)
