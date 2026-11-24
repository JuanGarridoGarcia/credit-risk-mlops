"""T16.1 to T16.6: retries (D-102), idempotent training and promotion (D-101) and the
PD and LGD tasks apart (D-100), approved by Juan on 2026-11-24.

The MLflow tests run against a local SQLite store in a temporary folder: no Docker. The
flow itself, with Postgres, MLflow and the Prefect server, is tested in
``tests/integration/test_flows.py`` (T16.7 to T16.10).
"""

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import mlflow
import numpy as np
import polars as pl
import psycopg
import pytest
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import (
    INVALID_PARAMETER_VALUE,
    RESOURCE_DOES_NOT_EXIST,
    TEMPORARILY_UNAVAILABLE,
)
from prefect import flow, task
from prefect.testing.utilities import prefect_test_harness

from credit_risk import flows, pipeline, registry
from credit_risk.ingest import DeliveryError
from credit_risk.lgd import train_lgd
from credit_risk.snapshot import FEATURES, SPLIT, SnapshotError, content_hash
from credit_risk.storage import StoreError
from credit_risk.train import SEED, prepare_frame, train_pd
from credit_risk.validation.report import ValidationFailed
from tests.synthetic import CUTOFF, training_set

TRIALS = 3
COMMIT = "c" * 40

# The SQLite store of MLflow uses a SQLAlchemy loader deprecated in SQLAlchemy 2.1 (E-037);
# it is MLflow's code, not ours, and the server of docker compose runs the same code.
pytestmark = pytest.mark.filterwarnings(
    "ignore:The ``noload`` loader strategy is deprecated:sqlalchemy.exc.SADeprecationWarning"
)


@pytest.fixture(scope="module")
def local_mlflow(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """A tracking store and artefact folder of their own, in a temporary folder."""
    folder = tmp_path_factory.mktemp("mlflow")
    previous_cwd, previous_uri = Path.cwd(), mlflow.get_tracking_uri()
    previous_commit = os.environ.get("CREDIT_RISK_COMMIT")
    # Artefacts of a SQLite store go under the working directory.
    os.chdir(folder)
    mlflow.set_tracking_uri(f"sqlite:///{folder / 'mlflow.db'}")
    os.environ["CREDIT_RISK_COMMIT"] = COMMIT
    yield folder
    os.chdir(previous_cwd)
    mlflow.set_tracking_uri(previous_uri)
    if previous_commit is None:
        os.environ.pop("CREDIT_RISK_COMMIT", None)
    else:
        os.environ["CREDIT_RISK_COMMIT"] = previous_commit


@pytest.fixture(scope="module")
def data() -> tuple[pl.DataFrame, str]:
    listings = training_set(seed=21)
    return listings, content_hash({FEATURES: listings})


class Calls:
    """Counts the calls to a training function, letting each one through."""

    def __init__(self, function: Any) -> None:
        self.function = function
        self.count = 0
        self.args: list[Any] = []

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.count += 1
        self.args.append(args)
        return self.function(*args, **kwargs)


def _versions(name: str) -> list[str]:
    return sorted(v.version for v in MlflowClient().search_model_versions(f"name='{name}'"))


# T16.1
@pytest.mark.parametrize(
    "error",
    [
        psycopg.OperationalError("connection to server at postgres failed"),
        MlflowException(
            "API request to http://mlflow:5000/api/2.0/mlflow/runs/create failed with "
            "exception HTTPConnectionPool(host='mlflow', port=5000): Max retries exceeded"
        ),
        MlflowException(
            "API request to http://mlflow:5000/api/2.0/mlflow/runs/get failed with timeout "
            "exception ReadTimeout"
        ),
        MlflowException("service unavailable", error_code=TEMPORARILY_UNAVAILABLE),
        MlflowException("API request to endpoint failed with error code 502 != 200"),
    ],
    ids=["postgres", "mlflow-connection", "mlflow-timeout", "mlflow-503", "mlflow-500"],
)
def test_transient_errors_are_retried(error: BaseException) -> None:
    assert flows.is_transient(error)


@pytest.mark.parametrize(
    "error",
    [
        ValidationFailed.__new__(ValidationFailed),
        DeliveryError("columns do not match the listings contract"),
        StoreError("checksum differs"),
        SnapshotError("no training set at 2014-01"),
        registry.RegistryError("no champion of pd and no baseline to compare with"),
        MlflowException("bad parameter", error_code=INVALID_PARAMETER_VALUE),
        MlflowException("no such run", error_code=RESOURCE_DOES_NOT_EXIST),
        psycopg.errors.UniqueViolation("duplicate key"),
        FileNotFoundError("no listings delivery for 2014-01"),
        KeyError("something we did not foresee"),
    ],
    ids=lambda e: type(e).__name__,
)
def test_permanent_and_unknown_errors_are_not_retried(error: BaseException) -> None:
    assert not flows.is_transient(error)


# T16.2
def test_retries_three_times_on_transient_errors_only() -> None:
    assert flows.RETRY["retries"] == 3
    assert flows.RETRY["retry_delay_seconds"] == [10, 30, 90]
    attempts = {"transient": 0, "permanent": 0}

    @task(**{**flows.RETRY, "retry_delay_seconds": 0})
    def flaky() -> str:
        attempts["transient"] += 1
        if attempts["transient"] < 3:
            raise psycopg.OperationalError("server closed the connection unexpectedly")
        return "done"

    @task(**{**flows.RETRY, "retry_delay_seconds": 0})
    def broken() -> str:
        attempts["permanent"] += 1
        raise DeliveryError("columns do not match the listings contract")

    @flow
    def both() -> tuple[str, Any]:
        return flaky(), broken(return_state=True)

    with prefect_test_harness():
        done, failed = both()

    assert done == "done"
    assert attempts["transient"] == 3
    assert failed.is_failed()
    assert attempts["permanent"] == 1


# T16.3
def test_the_same_key_twice_reuses_the_registered_version(
    local_mlflow: Path, data: tuple[pl.DataFrame, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    listings, version = data
    calls = Calls(train_pd)
    monkeypatch.setattr(pipeline, "train_pd", calls)
    prefix = "t163-"

    first = pipeline.retrain_pd(listings, CUTOFF, version, prefix=prefix, trials=TRIALS)
    registered = _versions(f"{prefix}pd")
    again = pipeline.retrain_pd(listings, CUTOFF, version, prefix=prefix, trials=TRIALS)

    assert calls.count == 1
    assert not first.reused
    assert again.reused
    assert again.version == first.version
    assert again.covered_terms == first.covered_terms
    assert again.verdict.passed == first.verdict.passed
    assert _versions(f"{prefix}pd") == registered

    # Another commit is another procedure: it trains again.
    monkeypatch.setenv("CREDIT_RISK_COMMIT", "d" * 40)
    other = pipeline.retrain_pd(listings, CUTOFF, version, prefix=prefix, trials=TRIALS)
    assert calls.count == 2
    assert not other.reused
    assert other.version not in registered

    # Another training set too.
    changed = listings.with_columns(pl.col("dti") * 1.01)
    other_version = content_hash({FEATURES: changed})
    monkeypatch.setenv("CREDIT_RISK_COMMIT", COMMIT)
    pipeline.retrain_pd(changed, CUTOFF, other_version, prefix=prefix, trials=TRIALS)
    assert calls.count == 3


# T16.4
def test_a_run_never_registered_is_trained_again_and_marked_failed(
    local_mlflow: Path, data: tuple[pl.DataFrame, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    listings, version = data
    prefix = "t164-"

    def lost(*args: Any, **kwargs: Any) -> str:
        raise MlflowException("API request failed with exception: connection reset")

    with monkeypatch.context() as patch:
        patch.setattr(registry, "register", lost)
        with pytest.raises(MlflowException):
            pipeline.retrain_pd(listings, CUTOFF, version, prefix=prefix, trials=TRIALS)
    client = MlflowClient()
    experiment = client.get_experiment_by_name(f"{prefix}pd")
    assert experiment is not None
    left = {r.info.run_id for r in client.search_runs([experiment.experiment_id])}
    assert left, "the first attempt logged its runs"
    assert not _versions(f"{prefix}pd")

    calls = Calls(train_pd)
    monkeypatch.setattr(pipeline, "train_pd", calls)
    outcome = pipeline.retrain_pd(listings, CUTOFF, version, prefix=prefix, trials=TRIALS)

    assert calls.count == 1
    assert not outcome.reused
    for run_id in left:
        run = client.get_run(run_id)
        assert run.info.status == "FAILED"
        assert run.data.tags["orphan"] == "true"
    registered = {str(v.run_id) for v in client.search_model_versions(f"name='{prefix}pd'")}
    assert registered.isdisjoint(left)


# T16.5
def test_promoting_the_same_version_twice_changes_nothing(
    local_mlflow: Path, data: tuple[pl.DataFrame, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    listings, version = data
    prefix = "t165-"
    name = f"{prefix}pd"
    validation = listings.filter(pl.col(SPLIT) == "validation")
    client = MlflowClient()

    # A promotion that stops after deciding, before the alias moves.
    real_move = registry._move
    with monkeypatch.context() as patch:

        def stops(*args: Any, **kwargs: Any) -> None:
            raise MlflowException("API request failed with exception: connection reset")

        patch.setattr(registry, "_move", stops)
        with pytest.raises(MlflowException):
            pipeline.retrain_pd(listings, CUTOFF, version, prefix=prefix, trials=TRIALS)
    assert registry.champion(name) is None
    assert registry._move is real_move

    judged = Calls(registry.judge)
    monkeypatch.setattr(registry, "judge", judged)
    outcome = pipeline.retrain_pd(listings, CUTOFF, version, prefix=prefix, trials=TRIALS)
    assert outcome.reused
    assert judged.count == 0, "the decision taken before is carried out, not taken again"
    champion = registry.champion(name)
    assert champion is not None

    def state() -> tuple[Any, ...]:
        run = client.get_run(str(client.get_model_version(name, outcome.version).run_id))
        tags = {v.version: dict(v.tags) for v in client.search_model_versions(f"name='{name}'")}
        history = client.get_metric_history(run.info.run_id, "promotion.auc.new")
        return registry.champion(name), tags, dict(run.data.tags), len(history)

    before = state()
    verdict = registry.promote(
        name, outcome.version, validation, target="pd", baseline_version=None
    )
    assert judged.count == 0
    assert verdict.passed == outcome.verdict.passed
    assert verdict.rules == outcome.verdict.rules
    assert state() == before


# T16.6
def test_the_lgd_gets_the_terms_of_the_pd_and_the_same_models(
    local_mlflow: Path, data: tuple[pl.DataFrame, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    listings, version = data
    prefix = "t166-"
    lgd_calls = Calls(train_lgd)
    monkeypatch.setattr(pipeline, "train_lgd", lgd_calls)

    verdicts = pipeline.retrain(listings, CUTOFF, version, prefix=prefix, trials=TRIALS)

    frame = prepare_frame(listings)
    pd_direct = train_pd(frame, CUTOFF, SEED, trials=TRIALS)
    assert lgd_calls.count == 1
    assert lgd_calls.args[0][2] == pd_direct.covered_terms
    lgd_direct = train_lgd(frame, CUTOFF, pd_direct.covered_terms, SEED, trials=TRIALS)
    validation = frame.filter(pl.col(SPLIT) == "validation")
    for target, direct, predict in (
        ("pd", pd_direct.chosen, "predict_pd"),
        ("lgd", lgd_direct.chosen, "predict_lgd"),
    ):
        name = f"{prefix}{target}"
        challenger = registry.trained(name, version, COMMIT)["challenger"]
        stored = registry.load(name, challenger)
        np.testing.assert_allclose(
            getattr(stored, predict)(validation).to_numpy(),
            getattr(direct, predict)(validation).to_numpy(),
        )
        assert set(verdicts) == {"pd", "lgd"}
