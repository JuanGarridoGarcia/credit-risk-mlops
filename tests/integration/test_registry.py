"""T11.1 to T11.5: promotion, evidence, alert and rollback in the MLflow registry (D-082).

Each test registers its own models under names of its own. The challengers that must
fail exactly one rule are a sensible model with one deliberate defect (``Defect``), so
that every other rule still passes.
"""

import copy
import logging
import os
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import mlflow
import numpy as np
import polars as pl
import pytest
from mlflow import MlflowClient

from credit_risk import registry
from credit_risk.model import PDModel
from credit_risk.snapshot import SPLIT
from credit_risk.train import PDTraining, prepare_frame, train_pd
from tests.synthetic import CUTOFF, training_set

pytestmark = pytest.mark.integration

RESAMPLES = 200


@dataclass
class Defect:
    """A sensible model with one deliberate defect (picklable: it is stored as a model)."""

    inner: PDModel
    kind: str

    @property
    def covered_terms(self) -> tuple[int, ...]:
        return self.inner.covered_terms

    @property
    def estimator(self) -> Any:
        if self.kind != "sign":
            return self.inner.estimator
        # Same predictions, but a coefficient with the wrong sign on record.
        flipped = copy.deepcopy(self.inner.estimator)
        flipped.coef_[0, self.inner.prepare.names.index("int_rate")] *= -1
        return flipped

    @property
    def prepare(self) -> Any:
        return self.inner.prepare

    def predict_pd(self, features: pl.DataFrame) -> pl.Series:
        pd_ = self.inner.predict_pd(features)
        if self.kind == "segment":
            # Far too high in grade C: clearly worse calibration there, ranking kept.
            in_c = (features["grade"] == "C").cast(pl.Float64)
            return (pd_ * (1 + 1.5 * in_c)).clip(0, 1)
        if self.kind == "battery":
            # A loan's PD depends, very slightly, on the size of the batch.
            return pd_ + features.height * 1e-12
        return pd_


@pytest.fixture(scope="module")
def listings() -> pl.DataFrame:
    # Enough defaults in validation (about 970) for the logistic model to beat the
    # baseline clearly, so each defect is the only reason a challenger fails.
    return training_set(20_000, seed=31)


@pytest.fixture(scope="module")
def validation(listings: pl.DataFrame) -> pl.DataFrame:
    return listings.filter(pl.col(SPLIT) == "validation")


@pytest.fixture(scope="module")
def trained(listings: pl.DataFrame) -> PDTraining:
    return train_pd(prepare_frame(listings), CUTOFF, trials=3)


@pytest.fixture
def name() -> Iterator[str]:
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    model = f"test-registry-{uuid.uuid4().hex[:8]}"
    yield model
    client = MlflowClient()
    for version in client.search_model_versions(f"name='{model}'"):
        client.delete_model_version(model, version.version)
    if client.search_registered_models(f"name='{model}'"):
        client.delete_registered_model(model)
    for experiment in client.search_experiments(filter_string=f"name = '{model}'"):
        client.delete_experiment(experiment.experiment_id)


def _register(name: str, model: object, label: str) -> str:
    mlflow.set_experiment(name)
    with mlflow.start_run(run_name=label) as run:
        mlflow.set_tag("model", label)
    source = registry.log_model(run.info.run_id, model)
    return registry.register(name, run.info.run_id, source)


def _promote(name: str, version: str, validation: pl.DataFrame, **kwargs: Any) -> Any:
    return registry.promote(name, version, validation, target="pd", resamples=RESAMPLES, **kwargs)


@pytest.fixture
def baseline_champion(name: str, trained: PDTraining, validation: pl.DataFrame) -> str:
    """The baseline as champion, through the D-090 path (a first challenger that fails)."""
    baseline = _register(name, trained.baseline, "baseline")
    weak = _register(name, Defect(trained.baseline, "none"), "copy of the baseline")
    _promote(name, weak, validation, baseline_version=baseline)
    assert registry.champion(name) == baseline
    return baseline


# T11.1
@pytest.mark.parametrize(
    ("kind", "rule"),
    [
        ("noise", "better than the noise"),
        ("segment", "no key segment clearly worse"),
        ("sign", "signs and constraints"),
        ("battery", "behavioural battery"),
    ],
)
def test_a_challenger_failing_one_rule_is_not_promoted(
    name: str,
    trained: PDTraining,
    validation: pl.DataFrame,
    baseline_champion: str,
    kind: str,
    rule: str,
) -> None:
    challenger = trained.baseline if kind == "noise" else Defect(trained.logistic, kind)
    version = _register(name, challenger, kind)
    verdict = _promote(name, version, validation)
    assert verdict.reasons == [rule]
    assert registry.champion(name) == baseline_champion


def test_a_challenger_passing_every_rule_is_promoted(
    name: str, trained: PDTraining, validation: pl.DataFrame, baseline_champion: str
) -> None:
    version = _register(name, trained.logistic, "logistic")
    verdict = _promote(name, version, validation)
    assert verdict.passed, verdict.reasons
    assert registry.champion(name) == version


def test_promotion_cannot_skip_a_rule() -> None:
    import inspect

    parameters = set(inspect.signature(registry.promote).parameters)
    assert parameters == {
        "name", "version", "validation", "target", "baseline_version", "seed", "resamples",
    }  # fmt: skip


# T11.2
def test_every_decision_leaves_evidence(
    name: str, trained: PDTraining, validation: pl.DataFrame, baseline_champion: str
) -> None:
    client = MlflowClient()
    for model, outcome in ((Defect(trained.logistic, "segment"), "rejected"),
                           (trained.logistic, "promoted")):  # fmt: skip
        version = _register(name, model, outcome)
        _promote(name, version, validation)
        run_id = client.get_model_version(name, version).run_id
        assert run_id
        run = client.get_run(run_id)
        assert run.data.tags["promotion.outcome"] == outcome
        assert {k for k in run.data.tags if k.startswith("rule.")} == {
            "rule.better than the noise", "rule.no key segment clearly worse",
            "rule.signs and constraints", "rule.behavioural battery",
        }  # fmt: skip
        assert "promotion.auc.improvement.low" in run.data.metrics
        evidence = mlflow.artifacts.load_dict(f"runs:/{run_id}/promotion/evidence.json")
        assert len(evidence["improvements"]) == RESAMPLES
        assert evidence["segments"]
        assert evidence["battery"]["checks"]
        if outcome == "rejected":
            assert run.data.tags["promotion.reasons"] == "no key segment clearly worse"


# T11.3
def test_every_promotion_alerts(
    name: str,
    trained: PDTraining,
    validation: pl.DataFrame,
    baseline_champion: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    version = _register(name, trained.logistic, "logistic")
    with caplog.at_level(logging.WARNING, logger="credit_risk.registry"):
        _promote(name, version, validation)
    alerts = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert alerts == [f"champion {name} promoted: {baseline_champion} -> {version} at "
                      + alerts[0].rsplit(" at ", 1)[1]]  # fmt: skip
    tags = MlflowClient().get_model_version(name, version).tags
    assert tags["previous_champion"] == baseline_champion
    assert tags["promoted_at"]


# T11.4
def test_rollback_returns_to_the_previous_champion(
    name: str,
    trained: PDTraining,
    validation: pl.DataFrame,
    baseline_champion: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    version = _register(name, trained.logistic, "logistic")
    _promote(name, version, validation)
    assert registry.champion(name) == version
    with caplog.at_level(logging.WARNING, logger="credit_risk.registry"):
        assert registry.rollback(name) == (version, baseline_champion)
    assert registry.champion(name) == baseline_champion
    assert any("rolled back" in r.getMessage() for r in caplog.records)
    assert MlflowClient().get_model_version(name, version).tags["rolled_back_at"]
    features = prepare_frame(validation)
    back = registry.load(name, registry.champion(name) or "")
    assert np.array_equal(
        back.predict_pd(features).to_numpy(), trained.baseline.predict_pd(features).to_numpy()
    )
    # The baseline was the first champion: there is nothing before it.
    with pytest.raises(registry.RegistryError, match="no previous champion"):
        registry.rollback(name)
    assert registry.champion(name) == baseline_champion


# T11.5
def test_the_first_champion_must_beat_the_baseline(
    name: str, trained: PDTraining, validation: pl.DataFrame
) -> None:
    baseline = _register(name, trained.baseline, "baseline")
    failing = _register(name, Defect(trained.logistic, "battery"), "fails")
    assert not _promote(name, failing, validation, baseline_version=baseline).passed
    assert registry.champion(name) == baseline


def test_a_first_model_that_beats_the_baseline_is_champion(
    name: str, trained: PDTraining, validation: pl.DataFrame
) -> None:
    baseline = _register(name, trained.baseline, "baseline")
    good = _register(name, trained.logistic, "logistic")
    assert _promote(name, good, validation, baseline_version=baseline).passed
    assert registry.champion(name) == good
