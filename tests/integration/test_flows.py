"""T16.7 to T16.10: the monthly flow end to end and the Prefect server of docker compose
(step 4.1, D-099 to D-104), approved by Juan on 2026-11-24.

The flow runs in this process against the services of docker compose: a database of its
own (migrated here, dropped afterwards), the MLflow server under model names of its own,
and the Prefect server, which records every run. The data are the small made-up source of
``tests/synthetic_source.py``. The test publishes its deliveries with the real simulator
before each run, as the simulated world does before the system's flow (D-043, D-105).
"""

import asyncio
import os
import time
import urllib.request
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import mlflow
import psycopg
import pytest
from mlflow import MlflowClient
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import FlowRunFilter, FlowRunFilterId
from prefect.deployments import run_deployment

from credit_risk import flows, registry
from credit_risk.flows import Paths, monthly
from credit_risk.settings import Settings
from credit_risk.simulator.publish import load_prepared, publish
from tests.synthetic_source import CUTOFF, write_source

from .conftest import compose, database_url, dbmate, docker

pytestmark = pytest.mark.integration

TRIALS = 3
PERIOD = f"{CUTOFF:%Y-%m}"
#: The month after the cutoff, delivered with one row that breaks a critical rule.
BAD_MONTH = date(2012, 2, 1)


#: Environment variables the scenarios change, put back afterwards.
ENVIRONMENT = ("POSTGRES_DB", "CREDIT_RISK_COMMIT", "API_URL", "API_ADMIN_KEY")


def prefect_url() -> str:
    return os.environ.get("PREFECT_API_URL", "http://localhost:4200/api")


@dataclass(frozen=True)
class Scenario:
    paths: Paths
    prefix: str
    conninfo: str


@pytest.fixture(scope="module")
def scenario(settings: Settings, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Scenario]:
    """A migrated database, a source file and model names of their own; removed after."""
    folder = tmp_path_factory.mktemp("flow")
    _publish(folder / "source.csv.gz", folder / "landing", CUTOFF)
    paths = Paths(
        landing=str(folder / "landing"),
        reports=str(folder / "validation"),
        training_sets=str(folder / "training_sets"),
    )
    name = f"test_flow_{uuid.uuid4().hex[:8]}"
    prefix = f"test-flow-{uuid.uuid4().hex[:8]}-"
    with psycopg.connect(settings.postgres_conninfo(), autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{name}"')
    previous = {k: os.environ.get(k) for k in ENVIRONMENT}
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    try:
        dbmate(database_url(settings, name), "up")
        # Every task reads its settings from the environment, as in the worker. The API of
        # compose serves the real model names, not these: the flow must not notify it.
        for key in ("API_URL", "API_ADMIN_KEY"):
            os.environ.pop(key, None)
        os.environ["POSTGRES_DB"] = name
        os.environ["CREDIT_RISK_COMMIT"] = "f" * 40
        conninfo = settings.postgres_conninfo().replace(
            f"dbname={settings.postgres_db}", f"dbname={name}"
        )
        yield Scenario(paths, prefix, conninfo)
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        _remove_models(prefix)
        with psycopg.connect(settings.postgres_conninfo(), autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def _publish(
    source: Path, landing: Path, until: date, bad: tuple[date, str, str] | None = None
) -> None:
    """The simulated world: write the source and deliver every month up to ``until``."""
    sha = write_source(source, until=until, bad=bad)
    prepared = load_prepared(source, source.parent / f"cache_{sha[:8]}", sha)
    publish(prepared, landing, until)


def _remove_models(prefix: str) -> None:
    client = MlflowClient()
    for target in ("pd", "lgd", "buy_rule"):
        name = f"{prefix}{target}"
        if client.search_registered_models(f"name='{name}'"):
            for version in client.search_model_versions(f"name='{name}'"):
                client.delete_model_version(name, version.version)
            client.delete_registered_model(name)
    for experiment in client.search_experiments(filter_string=f"name LIKE '{prefix}%'"):
        client.delete_experiment(experiment.experiment_id)


def _run(scenario: Scenario, period: str, paths: Paths | None = None) -> Any:
    return monthly(period, paths or scenario.paths, scenario.prefix, TRIALS, return_state=True)


def _footprint(scenario: Scenario) -> dict[str, Any]:
    """Everything the flow writes: rows, training sets, runs and registered versions."""
    with psycopg.connect(scenario.conninfo) as conn:
        counts: dict[str, Any] = {
            table: conn.execute(f"SELECT count(*) FROM {table}").fetchone()  # noqa: S608
            for table in (
                "raw.listings", "raw.outcomes", "clean.listings", "clean.outcomes",
                "ops.training_sets", "ops.validation_warnings",
            )
        }  # fmt: skip
    client = MlflowClient()
    for target in ("pd", "lgd"):
        experiment = client.get_experiment_by_name(f"{scenario.prefix}{target}")
        assert experiment is not None
        counts[f"runs.{target}"] = len(client.search_runs([experiment.experiment_id]))
        counts[f"versions.{target}"] = sorted(
            v.version for v in client.search_model_versions(f"name='{scenario.prefix}{target}'")
        )
        counts[f"champion.{target}"] = registry.champion(f"{scenario.prefix}{target}")
    return counts


async def _task_runs(flow_run_id: Any) -> dict[str, list[Any]]:
    async with get_client() as client:
        runs = await client.read_task_runs(
            flow_run_filter=FlowRunFilter(id=FlowRunFilterId(any_=[flow_run_id]))
        )
    found: dict[str, list[Any]] = {}
    for run in runs:
        found.setdefault(run.name.rsplit("-", 1)[0], []).append(run)
    return found


@pytest.fixture(scope="module")
def first(scenario: Scenario) -> tuple[Any, dict[str, Any]]:
    state = _run(scenario, PERIOD)
    return state, _footprint(scenario)


# T16.7
def test_the_whole_flow_on_small_data_leaves_two_champions(
    scenario: Scenario, first: tuple[Any, dict[str, Any]]
) -> None:
    state, footprint = first

    assert state.is_completed(), state.message
    summary = state.result()
    assert summary["months_loaded"] == 56  # 2007-06 to 2012-01
    assert summary["pd"].covered_terms == (36,)
    assert not summary["pd"].reused
    assert footprint["ops.training_sets"] == (1,)
    for target in ("pd", "lgd"):
        assert footprint[f"champion.{target}"] is not None
        assert footprint[f"champion.{target}"] in footprint[f"versions.{target}"]


# T16.9
def test_running_the_same_month_again_duplicates_nothing(
    scenario: Scenario, first: tuple[Any, dict[str, Any]]
) -> None:
    _, before = first

    state = _run(scenario, PERIOD)

    assert state.is_completed(), state.message
    summary = state.result()
    assert summary["pd"].reused
    assert summary["lgd"].reused
    assert _footprint(scenario) == before


# T16.8
def test_a_critical_validation_failure_stops_the_flow(
    scenario: Scenario, first: tuple[Any, dict[str, Any]], tmp_path: Path
) -> None:
    _, before = first
    # The next month arrives with one row that breaks a critical rule; the months before
    # are delivered again byte for byte the same.
    _publish(tmp_path / "source_bad.csv.gz", Path(scenario.paths.landing), BAD_MONTH,
             bad=(BAD_MONTH, "grade", "Z"))  # fmt: skip

    state = _run(scenario, f"{BAD_MONTH:%Y-%m}")

    assert state.is_failed()
    tasks = asyncio.run(_task_runs(state.state_details.flow_run_id))
    assert [t.state.type.value for t in tasks["load"]] == ["FAILED"]
    assert tasks["load"][0].run_count == 1, "a failed validation is never retried"
    assert "ValidationFailed" in (tasks["load"][0].state.message or "")
    for later in ("monitor", "version", "train-pd", "train-lgd", "buy-rule", "reference", "reload"):
        assert later not in tasks, f"{later} ran after a failed validation"
    after = _footprint(scenario)
    # Raw keeps the delivery as it came, by design (D-044): validation stops it at clean.
    raw = ("raw.listings", "raw.outcomes")
    assert {k: v for k, v in after.items() if k not in raw} == {
        k: v for k, v in before.items() if k not in raw
    }, "nothing new reached clean, the training sets or the registry"
    with psycopg.connect(scenario.conninfo) as conn:
        bad = conn.execute(
            "SELECT count(*) FROM clean.listings WHERE period = %s", (BAD_MONTH,)
        ).fetchone()
    assert bad == (0,)


# T16.10
def test_the_prefect_server_runs_the_deployed_flow(
    settings: Settings, first: tuple[Any, dict[str, Any]]
) -> None:
    with urllib.request.urlopen(f"{prefect_url()}/health", timeout=10) as answer:  # noqa: S310
        assert answer.status == 200
    # Its metadata are in the database "prefect" of our Postgres: the flow run above too.
    state, _ = first
    conninfo = settings.postgres_conninfo().replace(
        f"dbname={settings.postgres_db}", f"dbname={flows.DATABASE}"
    )
    with psycopg.connect(conninfo) as conn:
        row = conn.execute(
            "SELECT state_type FROM flow_run WHERE id = %s", (state.state_details.flow_run_id,)
        ).fetchone()
    assert row == ("COMPLETED",)
    # Server and worker run from the train image (D-103).
    train = docker(
        "image",
        "inspect",
        "--format",
        "{{.Id}}",
        os.environ.get("TRAIN_IMAGE", "credit-risk:train"),
    )
    for service in ("prefect", "worker"):
        container = compose("ps", "-q", service).stdout.strip()
        assert docker("inspect", "--format", "{{.Image}}", container) == train

    # The deployment is on the server, and a run sent through it is executed by the
    # worker. The worker has no deliveries in this folder, so the run must end in the
    # first task with that error, after one attempt: a missing file is not transient.
    deadline = time.monotonic() + 60
    run: Any = None
    while run is None:
        try:
            run = run_deployment(
                f"{flows.FLOW}/{flows.FLOW}",
                parameters={
                    "period": PERIOD,
                    "paths": {"landing": "/app/data/no_such_folder"},
                },
                timeout=120,
            )
        except Exception:
            if time.monotonic() > deadline:
                raise
            time.sleep(2)
    assert run.deployment_id is not None
    assert run.state is not None
    assert run.state.is_failed()
    tasks = asyncio.run(_task_runs(run.id))
    assert list(tasks) == ["load"]
    assert tasks["load"][0].run_count == 1
    assert "no_such_folder" in (tasks["load"][0].state.message or "")
