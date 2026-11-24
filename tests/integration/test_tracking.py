"""T8.1, T8.3, T8.4 and T14: the MLflow server of docker compose, what a run records
(D-079) and the model card of every registered version (D-095).

T8.2, which recreates the MLflow container, lives with B4 in ``test_persistence.py``.
"""

import os
import urllib.request
import uuid
from collections.abc import Iterator
from datetime import date
from typing import Any

import mlflow
import numpy as np
import polars as pl
import psycopg
import pytest
from mlflow import MlflowClient

from credit_risk import card, registry
from credit_risk.pipeline import retrain
from credit_risk.settings import Settings
from credit_risk.snapshot import FEATURES, LABEL, LGD, SPLIT, content_hash
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


def _cards(prefix: str) -> dict[tuple[str, str], tuple[str, Any]]:
    """The card of every registered version, with its run: {(target, version): (text, run)}."""
    client = MlflowClient()
    cards = {}
    for target in ("pd", "lgd"):
        for v in client.search_model_versions(f"name='{prefix}{target}'"):
            run_id = v.run_id or ""
            assert card.CARD_FILE in [a.path for a in client.list_artifacts(run_id)], (target, v)
            text = mlflow.artifacts.load_text(f"runs:/{run_id}/{card.CARD_FILE}")
            cards[(target, v.version)] = (text, client.get_run(run_id))
    return cards


# T14.1
def test_every_registered_version_has_its_model_card(
    prefix: str, retrained: dict[str, registry.Verdict]
) -> None:
    cards = _cards(prefix)
    # The chosen model and the baseline of each target (D-090), champion or not.
    assert len(cards) == 4
    for text, _ in cards.values():
        positions = [text.index(f"\n## {s}\n") for s in card.SECTIONS]
        assert positions == sorted(positions)


# T14.3
def test_the_numbers_of_the_card_are_those_of_the_run(
    prefix: str, retrained: dict[str, registry.Verdict], training: tuple[pl.DataFrame, str]
) -> None:
    listings, snapshot = training
    frame = prepare_frame(listings).filter(pl.col("term") == 36)
    lgd = frame.filter(pl.col(LGD).is_not_null())
    by_hand: dict[str, dict[str, tuple[int, int]]] = {"pd": {}, "lgd": {}}
    for split in ("train", "validation"):
        part = frame.filter(pl.col(SPLIT) == split)
        by_hand["pd"][split] = (part.height, int(part[LABEL].sum()))
        rows = lgd.filter(pl.col(SPLIT) == split).height
        by_hand["lgd"][split] = (rows, rows)  # every LGD row is a default
    for (target, _), (text, run) in _cards(prefix).items():
        tags, metrics = run.data.tags, run.data.metrics
        assert f"- Training set version: `{snapshot}`" in text
        assert f"- Run: `{run.info.run_id}`" in text
        for name in (m for m in metrics if "." not in m):
            row = (
                f"| {name} | {metrics[name]:.4f} | {metrics[f'{name}.low']:.4f} "
                f"| {metrics[f'{name}.high']:.4f} |"
            )
            assert row in text, (target, name)
        for split in ("train", "validation"):
            rows, defaults = by_hand[target][split]
            assert (tags[f"rows.{split}"], tags[f"defaults.{split}"]) == (str(rows), str(defaults))
            assert f"| {split} | {rows} | {defaults} |" in text


# T14.5
def test_the_card_carries_what_is_particular_to_each_model(
    prefix: str, retrained: dict[str, registry.Verdict]
) -> None:
    for (target, _), (text, run) in _cards(prefix).items():
        tags = run.data.tags
        if target == "pd":
            line = f"- Features removed for a wrong sign (D-092): {tags['removed_features']}"
        else:
            line = f"- Level shift fitted on validation (D-094): {tags['level_shift']}"
            assert float(tags["level_shift"]) != 0.0
        assert line in text, target
