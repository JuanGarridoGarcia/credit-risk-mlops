"""T19.1 and T19.2: the buy rule in the monthly flow and the reload notice to the API
(D-111, D-120), approved by Juan on 2026-11-24.

The flow runs in this process against a database of its own and the MLflow server, on
the small made-up source of ``tests/synthetic_source.py``, as in ``test_flows.py``. The
API is replaced by a small HTTP server that records what it receives.
"""

import json
import os
import socket
import threading
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import mlflow
import psycopg
import pytest
from mlflow import MlflowClient
from psycopg.rows import dict_row

from credit_risk import buy_rule, flows, registry
from credit_risk.business import GRID
from credit_risk.flows import Paths, monthly
from credit_risk.settings import Settings
from credit_risk.snapshot import read_evaluation, read_features
from credit_risk.storage import LocalStore
from tests.synthetic_source import CUTOFF

from .conftest import database_url, dbmate
from .test_flows import ENVIRONMENT, PERIOD, TRIALS, _publish, _remove_models

pytestmark = pytest.mark.integration

ADMIN_KEY = "k" * 40


@dataclass
class FakeApi:
    """Records every request it receives and answers 200."""

    calls: list[tuple[str, str, str | None]] = field(default_factory=list)
    url: str = ""


@dataclass(frozen=True)
class Scenario:
    paths: Paths
    prefix: str
    conninfo: str
    api: FakeApi


def _serve(api: FakeApi) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            api.calls.append(("POST", self.path, self.headers.get("X-API-Key")))
            body = json.dumps({"changed": True}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_: Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    api.url = f"http://127.0.0.1:{server.server_address[1]}"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@pytest.fixture(scope="module")
def scenario(settings: Settings, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Scenario]:
    folder = tmp_path_factory.mktemp("rule")
    _publish(folder / "source.csv.gz", folder / "landing", CUTOFF)
    paths = Paths(
        landing=str(folder / "landing"),
        reports=str(folder / "validation"),
        training_sets=str(folder / "training_sets"),
    )
    name = f"test_rule_{uuid.uuid4().hex[:8]}"
    prefix = f"test-rule-{uuid.uuid4().hex[:8]}-"
    api = FakeApi()
    server = _serve(api)
    with psycopg.connect(settings.postgres_conninfo(), autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{name}"')
    previous = {k: os.environ.get(k) for k in ENVIRONMENT}
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    try:
        dbmate(database_url(settings, name), "up")
        os.environ.update(
            POSTGRES_DB=name, CREDIT_RISK_COMMIT="d" * 40, API_URL=api.url, API_ADMIN_KEY=ADMIN_KEY
        )
        conninfo = settings.postgres_conninfo().replace(
            f"dbname={settings.postgres_db}", f"dbname={name}"
        )
        yield Scenario(paths, prefix, conninfo, api)
    finally:
        server.shutdown()
        server.server_close()
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        _remove_models(prefix)
        with psycopg.connect(settings.postgres_conninfo(), autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


@pytest.fixture(scope="module")
def first(scenario: Scenario) -> dict[str, Any]:
    summary: dict[str, Any] = monthly(PERIOD, scenario.paths, scenario.prefix, TRIALS)
    return summary


def _versions(name: str) -> list[str]:
    return sorted(v.version for v in MlflowClient().search_model_versions(f"name='{name}'"))


# T19.1
def test_the_flow_registers_the_rule_of_the_champion_pair(
    scenario: Scenario, first: dict[str, Any]
) -> None:
    name = f"{scenario.prefix}{buy_rule.NAME}"
    pd_v = registry.champion(f"{scenario.prefix}pd")
    lgd_v = registry.champion(f"{scenario.prefix}lgd")
    version = registry.champion(name)
    assert first["buy_rule_moved"] is True
    assert pd_v is not None
    assert lgd_v is not None
    assert version is not None
    rule = buy_rule.load(name, version)
    assert rule.matches(pd_v, lgd_v)
    assert rule.training_set == first["training_set"]
    assert rule.minimum in GRID
    # The minimum is the one D-084 chooses on validation with this very pair.
    store = LocalStore(Path(scenario.paths.training_sets))
    with psycopg.connect(scenario.conninfo) as conn:
        features = read_features(conn, store, rule.training_set)
        evaluation = read_evaluation(conn, store, rule.training_set)
        listed = buy_rule.listed(conn)
    again = buy_rule.choose(
        registry.load(f"{scenario.prefix}pd", pd_v),
        registry.load(f"{scenario.prefix}lgd", lgd_v),
        features,
        evaluation,
        listed,
    )
    assert again.minimum == rule.minimum
    # Its run carries every required field (D-079).
    run = MlflowClient().get_run(str(MlflowClient().get_model_version(name, version).run_id))
    assert run.data.tags["snapshot"] == rule.training_set
    assert run.data.tags["commit"] == "d" * 40
    assert {"net_return", "net_return.low", "net_return.high"} <= set(run.data.metrics)
    with psycopg.connect(scenario.conninfo, row_factory=dict_row) as conn:
        promoted = conn.execute(
            "SELECT * FROM ops.alerts WHERE kind = 'promoted' AND model = %s", (name,)
        ).fetchall()
    assert [(a["version"], a["previous"]) for a in promoted] == [(version, None)]

    # The same month again: nothing new.
    before = _versions(name)
    summary = monthly(PERIOD, scenario.paths, scenario.prefix, TRIALS)
    assert summary["buy_rule_moved"] is False
    assert _versions(name) == before

    # A new champion PD makes a new rule; going back reuses the old one (D-101).
    pd_name = f"{scenario.prefix}pd"
    source = MlflowClient().get_model_version(pd_name, pd_v)
    new_pd = registry.register(pd_name, str(source.run_id), str(source.source))
    MlflowClient().set_registered_model_alias(pd_name, registry.CHAMPION, new_pd)
    try:
        moved, changed = buy_rule.update(
            rule.training_set, features, evaluation, listed,
            prefix=scenario.prefix, commit="d" * 40,
        )  # fmt: skip
        assert changed
        assert moved not in before
        assert buy_rule.load(name, str(moved)).matches(new_pd, lgd_v)
    finally:
        MlflowClient().set_registered_model_alias(pd_name, registry.CHAMPION, pd_v)
    back, changed = buy_rule.update(
        rule.training_set, features, evaluation, listed, prefix=scenario.prefix, commit="d" * 40
    )
    assert (back, changed) == (version, True)
    assert len(_versions(name)) == len(before) + 1


# T19.2
def test_the_flow_tells_the_api_after_a_promotion(
    scenario: Scenario, first: dict[str, Any]
) -> None:
    calls = [c for c in scenario.api.calls if c[1] == "/admin/reload"]
    assert calls[0] == ("POST", "/admin/reload", ADMIN_KEY)
    assert first["api_reloaded"] is True
    # The rerun of T19.1 changed no champion: it sent no notice.
    assert len(calls) == 1

    # An API that does not answer: the flow goes on, and an alert says so.
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        closed = s.getsockname()[1]
    os.environ["API_URL"] = f"http://127.0.0.1:{closed}"
    try:
        assert flows.reload_task.fn(PERIOD) is False
    finally:
        os.environ["API_URL"] = scenario.api.url
    with psycopg.connect(scenario.conninfo, row_factory=dict_row) as conn:
        failed = conn.execute("SELECT * FROM ops.alerts WHERE kind = 'reload_failed'").fetchall()
    assert len(failed) == 1
    assert failed[0]["severity"] == "warning"
    assert failed[0]["period"] == CUTOFF
    assert failed[0]["task"] == "reload"
    assert ADMIN_KEY not in json.dumps(failed[0], default=str)
