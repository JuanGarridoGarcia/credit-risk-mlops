"""T8.1, T8.3 and T8.4: the MLflow server of docker compose and what a run records (D-079).

T8.2, which recreates the MLflow container, lives with B4 in ``test_persistence.py``.
"""

import os
import urllib.request
import uuid
from collections.abc import Iterator
from datetime import date

import mlflow
import numpy as np
import polars as pl
import psycopg
import pytest
from mlflow import MlflowClient

from credit_risk import registry
from credit_risk.pipeline import retrain
from credit_risk.settings import Settings
from credit_risk.snapshot import FEATURES, SPLIT, content_hash
from credit_risk.tracking import DATABASE, LIBRARIES
from credit_risk.train import prepare_frame, train_pd
from tests.synthetic import CUTOFF, training_set

pytestmark = pytest.mark.integration


def tracking_uri() -> str:
    return os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")


@pytest.fixture(scope="module")
def prefix() -> Iterator[str]:
    """Experiment and model names of their own, so tests never touch real models."""
    mlflow.set_tracking_uri(tracking_uri())
    name = f"test-{uuid.uuid4().hex[:8]}-"
    yield name
    client = MlflowClient()
    for model in ("pd", "lgd"):
        for version in client.search_model_versions(f"name='{name}{model}'"):
            client.delete_model_version(f"{name}{model}", version.version)
        if client.search_registered_models(f"name='{name}{model}'"):
            client.delete_registered_model(f"{name}{model}")
    for experiment in client.search_experiments(filter_string=f"name LIKE '{name}%'"):
        client.delete_experiment(experiment.experiment_id)


@pytest.fixture(scope="module")
def training() -> tuple[pl.DataFrame, str]:
    listings = training_set(seed=21)
    return listings, content_hash({FEATURES: listings})


@pytest.fixture(scope="module")
def retrained(prefix: str, training: tuple[pl.DataFrame, str]) -> dict[str, registry.Verdict]:
    listings, version = training
    return retrain(listings, CUTOFF, version, prefix=prefix, trials=3)


# T8.1
def test_the_server_answers_and_keeps_its_metadata_in_postgres(
    settings: Settings, prefix: str
) -> None:
    with urllib.request.urlopen(f"{tracking_uri()}/health", timeout=10) as answer:  # noqa: S310
        assert answer.status == 200
    mlflow.set_experiment(f"{prefix}server")
    with mlflow.start_run() as run:
        mlflow.log_metric("x", 1.0)
    conninfo = settings.postgres_conninfo().replace(
        f"dbname={settings.postgres_db}", f"dbname={DATABASE}"
    )
    with psycopg.connect(conninfo) as conn:
        row = conn.execute("SELECT status FROM runs WHERE run_uuid = %s", (run.info.run_id,))
        assert row.fetchone() == ("FINISHED",)


# T8.3
def test_every_run_of_a_real_training_carries_the_required_fields(
    prefix: str, retrained: dict[str, registry.Verdict], training: tuple[pl.DataFrame, str]
) -> None:
    runs = mlflow.search_runs(
        experiment_names=[f"{prefix}pd", f"{prefix}lgd"], output_format="list"
    )
    assert len(runs) == 6  # three models of each target
    for run in runs:
        tags, params, metrics = run.data.tags, run.data.params, run.data.metrics
        assert tags["commit"]
        assert tags["snapshot"] == training[1]
        assert params["seed"]
        for library in ("python", *LIBRARIES):
            assert tags[f"version.{library}"]
        values = [m for m in metrics if "." not in m]
        assert values
        for name in values:
            assert metrics[f"{name}.low"] <= metrics[name] <= metrics[f"{name}.high"], name


def _value(text: str) -> object:
    for kind in (int, float):
        try:
            return kind(text)
        except ValueError:
            continue
    return text


# T8.4
def test_the_model_is_rebuilt_from_what_its_run_recorded(
    prefix: str, retrained: dict[str, registry.Verdict]
) -> None:
    client = MlflowClient()
    runs = {
        r.data.tags["model"]: r
        for r in mlflow.search_runs(experiment_names=[f"{prefix}pd"], output_format="list")
    }
    stored = {
        name: registry.load(f"{prefix}pd", v.version)
        for v in client.search_model_versions(f"name='{prefix}pd'")
        if (name := client.get_run(v.run_id or "").data.tags["model"]) != "baseline"
    }
    assert stored, "no candidate was registered"
    # Only what the runs recorded: the snapshot, the seed and the hyperparameters.
    snapshot = runs["logistic"].data.tags["snapshot"]
    listings = training_set(seed=21)
    assert content_hash({FEATURES: listings}) == snapshot
    seed = int(runs["logistic"].data.params["seed"])
    params = {
        name: {k: _value(v) for k, v in runs[name].data.params.items() if k != "seed"}
        for name in ("logistic", "lightgbm")
    }
    rebuilt = train_pd(prepare_frame(listings), date(2014, 1, 1), seed, params=params)
    validation = prepare_frame(listings).filter(pl.col(SPLIT) == "validation")
    for name, model in stored.items():
        again = getattr(rebuilt, name)
        assert np.array_equal(
            model.predict_pd(validation).to_numpy(), again.predict_pd(validation).to_numpy()
        ), name
