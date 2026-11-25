"""T17.4 to T17.8: the simulated clock (D-107), the retraining cadence (D-106) and the
alerts table (D-108) against the services of docker compose, approved by Juan on
2026-11-24.

As in ``test_flows.py``, the flows run in this process on a database of their own and
model names of their own, with the small made-up source of ``tests/synthetic_source.py``.
The clock starts at 2012-01 (its first retraining month) and the source goes up to
2012-06. One story runs once for the module: four advances, one of them on a broken
delivery of 2012-03; each test checks one part of it.
"""

import asyncio
import os
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import mlflow
import psycopg
import pytest
from mlflow import MlflowClient
from prefect.client.orchestration import get_client
from psycopg.rows import dict_row

from credit_risk import alerts, flows, registry
from credit_risk.flows import Paths
from credit_risk.settings import Settings
from credit_risk.simulator import clock
from credit_risk.simulator.clock import World
from tests.synthetic_source import write_source

from .conftest import database_url, dbmate
from .test_flows import ENVIRONMENT, _remove_models, _task_runs

pytestmark = pytest.mark.integration

TRIALS = 3
START = "2012-01"
UNTIL = date(2012, 6, 1)
BAD_MONTH = date(2012, 3, 1)


@dataclass
class Story:
    """What the clock did, step by step, and where."""

    paths: Paths
    prefix: str
    conninfo: str
    good: World
    clocks: list[date | None] = field(default_factory=list)
    summaries: dict[str, dict[str, Any]] = field(default_factory=dict)
    failed: Any = None


def _world(folder: Path, name: str, bad: tuple[date, str, str] | None = None) -> World:
    source = folder / f"{name}.csv.gz"
    sha = write_source(source, until=UNTIL, bad=bad)
    return World(source=str(source), source_sha256=sha, cache=str(folder / f"cache_{name}"))


def _advance(story: Story, world: World | None = None, **kwargs: Any) -> Any:
    return clock.advance(world or story.good, story.paths, START, story.prefix, TRIALS, **kwargs)


@pytest.fixture(scope="module")
def story(settings: Settings, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Story]:
    """An empty clock advanced four times: 2012-01, 02, a failed 03, 03 again, 04."""
    folder = tmp_path_factory.mktemp("clock")
    name = f"test_clock_{uuid.uuid4().hex[:8]}"
    prefix = f"test-clock-{uuid.uuid4().hex[:8]}-"
    with psycopg.connect(settings.postgres_conninfo(), autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{name}"')
    previous = {k: os.environ.get(k) for k in ENVIRONMENT}
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    try:
        dbmate(database_url(settings, name), "up")
        for key in ("API_URL", "API_ADMIN_KEY"):  # not the API of compose (test_flows)
            os.environ.pop(key, None)
        os.environ["POSTGRES_DB"] = name
        os.environ["CREDIT_RISK_COMMIT"] = "e" * 40
        story = Story(
            paths=Paths(
                landing=str(folder / "landing"),
                reports=str(folder / "validation"),
                training_sets=str(folder / "training_sets"),
            ),
            prefix=prefix,
            conninfo=settings.postgres_conninfo().replace(
                f"dbname={settings.postgres_db}", f"dbname={name}"
            ),
            good=_world(folder, "good"),
        )
        bad = _world(folder, "bad", bad=(BAD_MONTH, "grade", "Z"))
        story.clocks.append(clock.now())
        for _ in range(2):
            summary = _advance(story)
            story.summaries[summary["period"]] = summary
            story.clocks.append(clock.now())
        story.failed = _advance(story, bad, return_state=True)
        story.clocks.append(clock.now())
        for _ in range(2):
            summary = _advance(story)
            story.summaries[summary["period"]] = summary
            story.clocks.append(clock.now())
        yield story
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        _remove_models(prefix)
        _remove_toy(f"{prefix}toy")
        with psycopg.connect(settings.postgres_conninfo(), autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def _remove_toy(name: str) -> None:
    client = MlflowClient()
    if client.search_registered_models(f"name='{name}'"):
        client.delete_registered_model(name)


def _alerts(story: Story) -> list[dict[str, Any]]:
    with psycopg.connect(story.conninfo, row_factory=dict_row) as conn:
        return conn.execute("SELECT * FROM ops.alerts ORDER BY alert_id").fetchall()


def _month(text: str) -> date:
    return date.fromisoformat(f"{text}-01")


# T17.4
def test_advance_moves_one_month_at_a_time_from_an_empty_clock(story: Story) -> None:
    assert story.clocks[:3] == [None, _month("2012-01"), _month("2012-02")]
    assert list(story.summaries) == ["2012-01", "2012-02", "2012-03", "2012-04"]
    # The first advance delivers the history; each later one, its own month only.
    landing = sorted(p.name for p in Path(story.paths.landing).iterdir())
    assert landing[0] == "2007-06"
    assert landing[-1] == "2012-04", "nothing published beyond the clock"
    assert story.summaries["2012-01"]["months_loaded"] == 56  # 2007-06 to 2012-01
    assert story.summaries["2012-02"]["months_loaded"] == 57
    with psycopg.connect(story.conninfo) as conn:
        loaded = conn.execute(
            "SELECT count(DISTINCT period) FROM clean.listings WHERE period > '2012-01-01'"
        ).fetchone()
    assert loaded == (3,), "02, 03 and 04 each loaded, none skipped"


# T17.5
def test_a_failed_advance_leaves_the_clock_and_the_next_one_repeats_the_month(
    story: Story,
) -> None:
    assert story.failed.is_failed()
    assert story.clocks[3] == _month("2012-02"), "the clock did not move"
    assert story.clocks[4] == _month("2012-03"), "the same month again, with the fix"
    assert story.clocks[5] == _month("2012-04")
    with psycopg.connect(story.conninfo) as conn:
        grades = conn.execute(
            "SELECT count(*) FROM clean.listings WHERE period = %s AND grade = 'Z'",
            (BAD_MONTH,),
        ).fetchone()
    assert grades == (0,)


# T17.6
def test_only_the_cadence_months_retrain(story: Story) -> None:
    expected = {"2012-01": True, "2012-02": False, "2012-03": False, "2012-04": True}
    for period, retrained in expected.items():
        summary = story.summaries[period]
        assert summary["retrained"] is retrained, period
        tasks = asyncio.run(_task_runs(summary["flow_run"]))
        names = ["load"]
        if retrained:
            names += ["version", "train-pd", "train-lgd", "buy-rule"]
            # The API is told only when a champion changed (D-111).
            if summary["pd"].changed or summary["lgd"].changed or summary["buy_rule_moved"]:
                names.append("reload")
        assert sorted(tasks) == sorted(names), period
        assert all(t.state.is_completed() for runs in tasks.values() for t in runs)
    assert story.summaries["2012-04"]["training_set"] != story.summaries["2012-01"]["training_set"]


# T17.7
def test_every_event_is_in_the_alerts_table_once(story: Story) -> None:
    found = _alerts(story)
    failed = [a for a in found if a["kind"] == "flow_failed"]
    assert len(failed) == 1
    assert failed[0]["severity"] == "error"
    assert failed[0]["flow"] == flows.FLOW
    assert failed[0]["period"] == BAD_MONTH
    assert failed[0]["task"] == "load"
    assert "ValidationFailed" in failed[0]["message"]

    # Every verdict on a challenger is there, as MLflow recorded it.
    client = MlflowClient()
    verdicts = 0
    for target in ("pd", "lgd"):
        name = f"{story.prefix}{target}"
        for version in client.search_model_versions(f"name='{name}'"):
            if version.tags.get(registry.ROLE) != "challenger":
                continue
            verdicts += 1
            tags = client.get_run(str(version.run_id)).data.tags
            rejected = [
                a for a in found
                if a["kind"] == "rejected" and a["model"] == name
                and a["version"] == version.version
            ]  # fmt: skip
            if tags[registry.DECISION] == "rejected":
                assert len(rejected) == 1
                assert rejected[0]["details"]["reasons"] == tags["promotion.reasons"].split(", ")
            else:
                assert rejected == []
        promoted = [a for a in found if a["kind"] == "promoted" and a["model"] == name]
        assert promoted, f"{name} got its first champion"
        assert promoted[0]["previous"] is None
        assert promoted[-1]["version"] == registry.champion(name)
    assert verdicts == 4  # two targets, two retraining months
    assert any(a["kind"] == "rejected" for a in found)

    # The same month again records no verdict twice.
    summary = flows.monthly("2012-04", story.paths, story.prefix, TRIALS)
    assert summary["pd"].reused
    assert summary["lgd"].reused
    assert _alerts(story) == found

    # A rollback, on a toy model with two champions in turn.
    name = f"{story.prefix}toy"
    mlflow.set_experiment(name)
    with mlflow.start_run() as run:
        mlflow.log_dict({"toy": True}, "toy/model.json")
    first, second = (
        registry.register(name, run.info.run_id, f"{run.info.artifact_uri}/toy") for _ in range(2)
    )
    MlflowClient().set_registered_model_alias(name, registry.CHAMPION, first)
    registry._move(name, second, first, "promoted")

    registry.rollback(name, notify=lambda c, p: alerts.record(alerts.rolled_back(name, c, p)))

    rolled = [a for a in _alerts(story) if a["kind"] == "rolled_back"]
    assert len(rolled) == 1
    assert (rolled[0]["model"], rolled[0]["previous"], rolled[0]["version"]) == (
        name, second, first,
    )  # fmt: skip
    assert rolled[0]["severity"] == "warning"


# T17.8
def test_the_clock_is_deployed_paused_and_replay_loops_months(story: Story) -> None:
    async def deployments() -> dict[str, Any]:
        async with get_client() as client:
            return {
                name: await client.read_deployment_by_name(f"{name}/{name}")
                for name in ("advance", "replay")
            }

    found = asyncio.run(deployments())
    advance = found["advance"]
    assert advance.paused
    assert [s.schedule.interval.total_seconds() for s in advance.schedules] == [
        clock.INTERVAL_SECONDS
    ]
    assert found["replay"].schedules == []

    months = clock.replay(f"{UNTIL:%Y-%m}", story.good, story.paths, START, story.prefix, TRIALS)

    assert months == ["2012-05", "2012-06"]
    assert clock.now() == UNTIL
