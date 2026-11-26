"""T17.4 to T17.8: the simulated clock (D-107), the retraining cadence (D-106) and the
alerts table (D-108) against the services of docker compose, approved by Juan on
2026-11-24; T21.2 to T21.5: the simulated investor inside the clock (D-123 to D-129),
approved by Juan on 2026-11-25; T24.1 to T24.3, T27.2, T27.4 and T27.5: the monitoring of
each month inside the clock (D-138 to D-146), approved by Juan on 2026-11-26.

As in ``test_flows.py``, the flows run in this process on a database of their own and
model names of their own, with the small made-up source of ``tests/synthetic_source.py``;
the API runs in a process of its own on the same database and model names. The clock
starts at 2012-01 (its first retraining month) and the source goes up to 2012-06. One
story runs once for the module: advances of 2012-01 and 02, one on a broken delivery of
2012-03, 03 again, one of 04 with the API out of reach, 04 again; each test checks one
part of it.
"""

import asyncio
import csv
import gzip
import os
import uuid
from collections.abc import Iterator
from contextlib import ExitStack
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import mlflow
import polars as pl
import psycopg
import pytest
from mlflow import MlflowClient
from prefect.client.orchestration import get_client
from psycopg.rows import dict_row

from credit_risk import alerts, flows, registry
from credit_risk.contracts import LISTING_COLUMNS, LISTINGS, delivery_path
from credit_risk.flows import Paths
from credit_risk.ingest import read_delivery
from credit_risk.monitoring import store as monitoring
from credit_risk.settings import Settings
from credit_risk.simulator import clock, replayer
from credit_risk.simulator.clock import World
from tests.api_support import ADMIN_KEY, PREDICT_KEY
from tests.investor_support import check_month
from tests.synthetic_source import write_source
from tests.valid_rows import month_text

from .api_process import api_process, free_port
from .conftest import database_url, dbmate
from .test_flows import ENVIRONMENT, _remove_models, _task_runs

pytestmark = pytest.mark.integration

TRIALS = 3
START = "2012-01"
UNTIL = date(2012, 6, 1)
BAD_MONTH = date(2012, 3, 1)
#: Small batches (a month of the made-up source has about 15 listings), so that each
#: month takes several requests; the API's limit is 1,000.
SMALL_BATCH = 4
INVESTED = [date(2012, m, 1) for m in range(2, 7)]


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
    #: The advance of 2012-04 with the API out of reach, and the clock after it.
    down: Any = None
    down_clock: date | None = None


def _world(folder: Path, name: str, bad: tuple[date, str, str] | None = None) -> World:
    source = folder / f"{name}.csv.gz"
    sha = write_source(source, until=UNTIL, bad=bad)
    return World(source=str(source), source_sha256=sha, cache=str(folder / f"cache_{name}"))


def _advance(story: Story, world: World | None = None, **kwargs: Any) -> Any:
    return clock.advance(world or story.good, story.paths, START, story.prefix, TRIALS, **kwargs)


@pytest.fixture(scope="module")
def story(settings: Settings, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Story]:
    """An empty clock advanced: 2012-01, 02, a failed 03, 03 again, a failed 04, 04."""
    folder = tmp_path_factory.mktemp("clock")
    name = f"test_clock_{uuid.uuid4().hex[:8]}"
    prefix = f"test-clock-{uuid.uuid4().hex[:8]}-"
    with psycopg.connect(settings.postgres_conninfo(), autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{name}"')
    previous = {k: os.environ.get(k) for k in (*ENVIRONMENT, "API_PREDICT_KEY")}
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    patch = pytest.MonkeyPatch()
    servers = ExitStack()
    try:
        dbmate(database_url(settings, name), "up")
        os.environ["POSTGRES_DB"] = name
        os.environ["CREDIT_RISK_COMMIT"] = "e" * 40
        url = servers.enter_context(api_process(name, prefix, ready=False))
        # The API of this story, not the one of compose; the flow tells it of new
        # champions (D-111) and the investor buys through it (D-124).
        os.environ.update(API_URL=url, API_ADMIN_KEY=ADMIN_KEY, API_PREDICT_KEY=PREDICT_KEY)
        patch.setattr(replayer, "BATCH", SMALL_BATCH)
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
        summary = _advance(story)
        story.summaries[summary["period"]] = summary
        story.clocks.append(clock.now())
        # 2012-04 with the API out of reach: the investor tries 1 + 3 times (no waits
        # here) and the clock stays (D-125); then 2012-04 again with the API back.
        os.environ["API_URL"] = f"http://127.0.0.1:{free_port()}"
        patch.setattr(
            clock, "invest_task", replayer.invest_task.with_options(retry_delay_seconds=0)
        )
        story.down = _advance(story, return_state=True)
        story.down_clock = clock.now()
        os.environ["API_URL"] = url
        patch.setattr(clock, "invest_task", replayer.invest_task)
        summary = _advance(story)
        story.summaries[summary["period"]] = summary
        story.clocks.append(clock.now())
        yield story
    finally:
        servers.close()
        patch.undo()
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
        names = ["load", "monitor"]
        if retrained:
            names += ["version", "train-pd", "train-lgd", "buy-rule", "reference"]
            # The API is told only when a champion changed (D-111).
            if summary["pd"].changed or summary["lgd"].changed or summary["buy_rule_moved"]:
                names.append("reload")
        assert sorted(tasks) == sorted(names), period
        assert all(t.state.is_completed() for runs in tasks.values() for t in runs)
    assert story.summaries["2012-04"]["training_set"] != story.summaries["2012-01"]["training_set"]


# T27.2
def test_monitor_runs_every_month_after_load_and_before_training(story: Story) -> None:
    for period in ("2012-01", "2012-04"):
        tasks = asyncio.run(_task_runs(story.summaries[period]["flow_run"]))
        order = [
            name
            for name, _ in sorted(
                ((n, r[0].start_time) for n, r in tasks.items()), key=lambda item: item[1]
            )
        ]
        assert order[:3] == ["load", "monitor", "version"], (period, order)
    # T0 has no predictions yet (the investor starts the month after): noted, not failed.
    first = story.summaries["2012-01"]["monitoring"]
    assert first["drift"] == 0
    assert first["notes"] == ["no predictions for the loans listed in 2012-01: no drift"]


# T27.5
def test_every_month_with_predictions_keeps_its_drift(story: Story) -> None:
    with psycopg.connect(story.conninfo) as conn:
        found: dict[date, int] = dict(
            conn.execute(
                "SELECT period, count(*) FROM monitoring.drift GROUP BY period ORDER BY period"
            ).fetchall()
        )
        pairs = conn.execute(
            "SELECT listed, count(DISTINCT (pd_version, lgd_version)) FROM serving.predictions"
            " GROUP BY listed"
        ).fetchall()
    per_month = len(monitoring.SUBJECTS)  # 30 features and 3 predictions
    for listed, n_pairs in pairs:
        if listed <= date(2012, 4, 1):
            assert found[listed] == per_month * n_pairs, listed
    assert date(2012, 1, 1) not in found
    assert set(found) >= {date(2012, m, 1) for m in (2, 3, 4)}


# T24.1
def test_each_pair_of_champions_has_the_reference_of_the_12_months_before_its_cutoff(
    story: Story,
) -> None:
    with psycopg.connect(story.conninfo) as conn:
        references = conn.execute(
            "SELECT pd_version, lgd_version, min(cutoff), max(cutoff), min(first_month),"
            " max(last_month), count(*) FROM monitoring.reference"
            " GROUP BY pd_version, lgd_version"
        ).fetchall()
        used = set(conn.execute("SELECT DISTINCT pd_version, lgd_version FROM serving.predictions"))
        found = {(r[0], r[1]): r[2:] for r in references}
        current = monitoring.current_pair(story.prefix)
        assert current is not None
        # The pair in service and every pair that answered have one; none is deleted.
        assert used | {current} <= set(found)
        for pair, (low, high, first, last, rows) in found.items():
            at = monitoring.pair_cutoff(conn, pair, story.prefix)
            assert low == high == at, pair
            assert (first, last) == (monitoring.add_months(at, -12), monitoring.add_months(at, -1))
            assert rows == len(monitoring.SUBJECTS)
    # The first champions were trained at T0 (2012-01): their reference is 2011.
    first_pair = sorted(found, key=lambda p: found[p][0])[0]
    assert found[first_pair][:2] == (date(2012, 1, 1), date(2012, 1, 1))
    assert found[first_pair][2:4] == (date(2011, 1, 1), date(2011, 12, 1))


# T24.2
def test_the_reference_scores_a_loan_exactly_as_the_api_did(story: Story) -> None:
    month = date(2012, 2, 1)
    with psycopg.connect(story.conninfo) as conn:
        answered = conn.execute(
            "SELECT loan_id, pd_version, lgd_version, pd, lgd, el_rate"
            " FROM serving.predictions WHERE listed = %s AND covered ORDER BY loan_id",
            (month,),
        ).fetchall()
        assert answered
        pair = (answered[0][1], answered[0][2])
        frame = monitoring.scored_reference(
            conn, monitoring._champions(pair, story.prefix), [month]
        )
    ours = {
        r["loan_id"]: (r["pd"], r["lgd"], r["el_rate"])
        for r in frame.filter(pl.col("pd").is_not_null()).iter_rows(named=True)
    }
    assert ours == {loan: (pd_, lgd, el) for loan, _, _, pd_, lgd, el in answered}


# T24.3
def test_building_a_reference_writes_nothing_to_the_predictions(story: Story) -> None:
    client = MlflowClient()
    pd_versions = [v.version for v in client.search_model_versions(f"name='{story.prefix}pd'")]
    lgd_versions = [v.version for v in client.search_model_versions(f"name='{story.prefix}lgd'")]
    with psycopg.connect(story.conninfo, autocommit=True) as conn:
        pair = next(
            (p, q)
            for p in pd_versions
            for q in lgd_versions
            if not monitoring.has_reference(conn, (p, q))
        )
        tables = ("serving.predictions", "serving.requests", "serving.purchases")
        before = [conn.execute(f"SELECT count(*) FROM {t}").fetchone() for t in tables]  # noqa: S608
        assert monitoring.ensure_reference(conn, pair, story.prefix)
        assert not monitoring.ensure_reference(conn, pair, story.prefix), "built once"
        after = [conn.execute(f"SELECT count(*) FROM {t}").fetchone() for t in tables]  # noqa: S608
        assert monitoring.has_reference(conn, pair)
    assert after == before


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


# ---------------------------------------------------------------- the investor (T21)


def _count(story: Story, query: str, *args: Any) -> int:
    with psycopg.connect(story.conninfo) as conn:
        row = conn.execute(query, args).fetchone()
    assert row is not None
    return int(row[0])


# T21.2
def test_the_investor_sends_every_listing_after_t0_once(story: Story) -> None:
    # Nothing up to T0, the month the first models are trained (D-127).
    assert story.summaries["2012-01"]["investor"] == {"period": "2012-01", "invested": False}
    assert (
        _count(story, "SELECT count(*) FROM serving.predictions WHERE listed <= %s", _month(START))
        == 0
    )
    with psycopg.connect(story.conninfo) as conn:
        months = [m for (m,) in conn.execute("SELECT month FROM sim.invested ORDER BY month")]
        batches = [
            n for (n,) in conn.execute(
                "SELECT loans + rejected FROM serving.requests"
                " WHERE endpoint = '/predict/batch' AND status = 200"
            )
        ]  # fmt: skip
    assert months[: len(INVESTED)] == INVESTED
    # In batches, never more than the limit, several a month.
    assert max(batches) <= SMALL_BATCH
    assert len(batches) > len(INVESTED)
    # Every listing of each month once: one prediction per loan (D-114, D-129).
    for month in INVESTED:
        listed = read_delivery(delivery_path(Path(story.paths.landing), month, LISTINGS), LISTINGS)
        assert (
            _count(story, "SELECT count(*) FROM serving.predictions WHERE listed = %s", month)
            == listed.height
        ), month
        assert (
            _count(
                story,
                "SELECT count(DISTINCT loan_id) FROM serving.predictions WHERE listed = %s",
                month,
            )
            == listed.height
        ), month


# T21.3
def test_a_month_is_scored_by_the_champions_of_the_month_before(story: Story) -> None:
    found = _alerts(story)

    def champion_before(target: str, month: date) -> str:
        name = f"{story.prefix}{target}"
        promoted = [
            a for a in found
            if a["kind"] == "promoted" and a["model"] == name and a["period"] < month
        ]  # fmt: skip
        return str(promoted[-1]["version"])

    # April retrains: its loans are scored before, by the champions of March (D-123).
    for month in (date(2012, 4, 1), date(2012, 5, 1)):
        with psycopg.connect(story.conninfo) as conn:
            pairs = conn.execute(
                "SELECT DISTINCT pd_version, lgd_version FROM serving.predictions"
                " WHERE listed = %s",
                (month,),
            ).fetchall()
        assert pairs == [(champion_before("pd", month), champion_before("lgd", month))], month


# T21.5
def test_what_was_bought_is_what_the_rule_gives_on_the_predictions(story: Story) -> None:
    print("\nT21.5:")
    for month in INVESTED:
        counts = check_month(story.conninfo, story.paths.landing, month)
        print(f"  {month:%Y-%m}: {counts}")
    assert _count(story, "SELECT count(*) FROM serving.purchases") == _count(
        story, "SELECT count(DISTINCT loan_id) FROM serving.purchases"
    ), "no loan bought twice"
    assert _count(story, "SELECT count(*) FROM serving.purchases") > 0


def _write_delivery(landing: Path, month: date, frame: Any) -> None:
    path = delivery_path(landing, month, LISTINGS)
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(LISTING_COLUMNS)
        for row in frame.iter_rows():
            writer.writerow(["" if v is None else v for v in row])


# T21.4
def test_the_investor_retries_a_missing_api_and_never_buys_twice(
    story: Story, tmp_path: Path
) -> None:
    # The API out of reach: four attempts, then the advance fails and the clock stays.
    assert story.down.is_failed()
    assert story.down_clock == date(2012, 3, 1)
    tasks = asyncio.run(_task_runs(story.down.state_details.flow_run_id))
    assert tasks["invest"][0].run_count == 1 + replayer.RETRIES
    assert story.clocks[-1] == date(2012, 4, 1), "the next advance did the month"
    # March again after the system's flow failed: the investor had already acted.
    assert story.summaries["2012-03"]["investor"].get("earlier") is True

    # An investor that stopped after buying, before recording its month: sending the
    # month again stores no prediction and no purchase twice.
    april = date(2012, 4, 1)
    before = (
        _count(story, "SELECT count(*) FROM serving.predictions"),
        _count(story, "SELECT count(*) FROM serving.purchases"),
    )
    with psycopg.connect(story.conninfo) as conn:
        conn.execute("DELETE FROM sim.invested WHERE month = %s", (april,))
    again = replayer.invest("2012-04", story.paths.landing, START)
    assert again["bought"] == story.summaries["2012-04"]["investor"]["bought"]
    assert (
        _count(story, "SELECT count(*) FROM serving.predictions"),
        _count(story, "SELECT count(*) FROM serving.purchases"),
    ) == before

    # A listing the API refuses: not bought, counted, and the month completes.
    landing = tmp_path / "landing"
    source = Path(story.paths.landing)
    for month, copy in (
        (date(2013, 1, 1), date(2012, 6, 1)),
        (date(2012, 12, 1), date(2012, 5, 1)),
    ):
        frame = read_delivery(delivery_path(source, copy, LISTINGS), LISTINGS)
        frame = frame.with_columns(
            id=(frame["id"].cast(int) + 90_000_000).cast(str),
            issue_d=frame["issue_d"].str.replace(r".*", month_text(month)),
        )
        if month == date(2013, 1, 1):
            frame = frame.with_columns(int_rate=frame["int_rate"].scatter(0, "not a rate"))
            refused = int(frame["id"][0])
        _write_delivery(landing, month, frame)
    summary = replayer.invest("2013-01", str(landing), START)
    assert summary["invested"] is True
    assert summary["refused"] == 1
    assert summary["scored"] == summary["listings"] - 1
    assert (
        _count(story, "SELECT count(*) FROM serving.predictions WHERE loan_id = %s", refused) == 0
    )
    assert _count(story, "SELECT count(*) FROM serving.purchases WHERE loan_id = %s", refused) == 0
    assert _count(story, "SELECT refused FROM sim.invested WHERE month = %s", date(2013, 1, 1)) == 1


# T27.4
def test_a_failed_monitor_fails_the_month_and_the_clock_stays(
    story: Story, monkeypatch: pytest.MonkeyPatch
) -> None:
    last = clock.now()
    assert last is not None
    back = monitoring.add_months(last, -1)
    with psycopg.connect(story.conninfo, autocommit=True) as conn:
        conn.execute("UPDATE sim.clock SET month = %s", (back,))

    def broken(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("monitor broken on purpose")

    monkeypatch.setattr(monitoring, "monitor", broken)
    state = _advance(story, return_state=True)
    assert state.is_failed()
    assert clock.now() == back, "the clock did not move"
    failed = [a for a in _alerts(story) if a["kind"] == "flow_failed" and a["period"] == last]
    assert len(failed) == 1
    assert failed[0]["task"] == "monitor"
    assert "monitor broken on purpose" in failed[0]["message"]

    monkeypatch.undo()
    _advance(story)
    assert clock.now() == last
