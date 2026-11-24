"""T10.1 to T10.5: the behavioural battery (D-086) does its job.

A sensible model trained on made-up data with the directions of D-080 passes each check;
a constant model and a random model fail the battery; and a model built to break one
check fails exactly that check.
"""

import time
from dataclasses import dataclass

import polars as pl
import pytest

from credit_risk import battery
from credit_risk.features import build_features
from credit_risk.model import PDModel
from credit_risk.snapshot import SPLIT
from credit_risk.train import prepare_frame, train_pd
from tests.synthetic import CUTOFF, training_set


@pytest.fixture(scope="module")
def listings() -> pl.DataFrame:
    return training_set(seed=5)


@pytest.fixture(scope="module")
def validation(listings: pl.DataFrame) -> pl.DataFrame:
    return listings.filter(pl.col(SPLIT) == "validation")


@pytest.fixture(scope="module")
def model(listings: pl.DataFrame) -> PDModel:
    return train_pd(prepare_frame(listings), CUTOFF, trials=5).logistic


@pytest.fixture(scope="module")
def result(model: PDModel, validation: pl.DataFrame) -> battery.BatteryResult:
    return battery.run(model, validation)


@dataclass
class Wrapped:
    """A sensible model with one deliberate defect."""

    inner: PDModel
    defect: str

    @property
    def covered_terms(self) -> tuple[int, ...]:
        return self.inner.covered_terms

    def predict_pd(self, features: pl.DataFrame) -> pl.Series:
        pd_ = self.inner.predict_pd(features)
        if self.defect == "batch size":
            return pd_ + features.height * 1e-9
        if self.defect == "dti protects":
            return (pd_ - features["dti"].fill_null(0) * 1e-3).clip(0, 1)
        if self.defect == "slow":
            time.sleep(0.06)
        return pd_


# T10.1
def test_unused_fields_and_batch_size_do_not_move_the_pd(
    result: battery.BatteryResult, model: PDModel, validation: pl.DataFrame
) -> None:
    assert result.checks["invariance: unused fields"]
    assert result.checks["invariance: alone or in a batch"]
    broken = battery.BatteryResult()
    battery.invariance(Wrapped(model, "batch size"), validation, broken)
    assert not broken.checks["invariance: alone or in a batch"]


# T10.2
def test_raising_a_risk_feature_never_lowers_the_pd(
    result: battery.BatteryResult, model: PDModel, validation: pl.DataFrame
) -> None:
    directions = {k: v for k, v in result.checks.items() if k.startswith("direction")}
    assert len(directions) == 9
    assert all(directions.values())
    broken = battery.BatteryResult()
    battery.direction(Wrapped(model, "dti protects"), build_features(validation), broken)
    assert not broken.checks["direction: dti"]
    assert broken.checks["direction: int_rate"]


# T10.3
def test_the_minimum_cases(result: battery.BatteryResult) -> None:
    assert result.checks["minimum: good profile below bad profile"]
    assert result.checks["minimum: every PD in [0, 1]"]
    assert result.checks["minimum: empty optional fields are scored"]
    assert result.checks["minimum: an uncovered term gets no PD"]


# T10.4
def test_one_prediction_takes_under_50_ms(
    result: battery.BatteryResult, model: PDModel, validation: pl.DataFrame
) -> None:
    assert result.checks["time: p95 under 50 ms"], result.details["time: p95 under 50 ms"]
    broken = battery.BatteryResult()
    battery.latency(Wrapped(model, "slow"), build_features(validation).head(20), broken)
    assert not broken.checks["time: p95 under 50 ms"]


# T10.5
def test_a_constant_and_a_random_model_fail(
    result: battery.BatteryResult, model: PDModel, validation: pl.DataFrame
) -> None:
    assert result.passed, {k: v for k, v in result.checks.items() if not v}
    constant = battery.run(battery.ConstantModel(model.covered_terms), validation)
    assert not constant.passed
    assert not constant.checks["minimum: good profile below bad profile"]
    random = battery.run(battery.RandomModel(model.covered_terms), validation)
    assert not random.passed
    assert not random.checks["invariance: unused fields"]
    assert not all(v for k, v in random.checks.items() if k.startswith("direction"))
