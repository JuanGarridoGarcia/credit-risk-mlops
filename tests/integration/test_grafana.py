"""T32.1 to T32.6: Grafana of docker compose, its dashboards, its read-only role and the
delivery of the alerts (D-147, D-148, D-152 to D-155). Approved by Juan on 2026-11-26.

Grafana reads the database of ``.env`` (the one compose uses), so the delivery test
migrates it, writes its own alerts there and removes them afterwards. The channel of the
tests is a webhook to a receiver in this process: Grafana is started again with
``GRAFANA_WEBHOOK_URL`` set, and once more without it at the end.
"""

import http.server
import json
import os
import threading
import time
import uuid
from collections.abc import Iterator
from typing import Any, ClassVar

import httpx
import psycopg
import pytest
from psycopg import errors
from pydantic import SecretStr

from credit_risk.monitoring import grafana
from credit_risk.settings import Settings

from .api_process import free_port
from .conftest import compose, database_url, dbmate

pytestmark = pytest.mark.integration

DASHBOARDS = {"credit-risk-system", "credit-risk-data", "credit-risk-model"}
#: How long a new alert may take to reach the receiver (T32.4).
DELIVERY_SECONDS = 120
#: Evaluations of the rule after the first delivery during which nothing must repeat.
QUIET_SECONDS = 35


def _url() -> str:
    return os.environ.get("GRAFANA_URL", "http://localhost:3000")


def _admin() -> httpx.Client:
    password = os.environ["GRAFANA_ADMIN_PASSWORD"]
    return httpx.Client(base_url=_url(), auth=("admin", password), trust_env=False, timeout=10)


def _reader(settings: Settings, dbname: str) -> psycopg.Connection[Any]:
    password = os.environ["GRAFANA_DB_PASSWORD"]
    return psycopg.connect(
        host=settings.postgres_host, port=settings.postgres_port, dbname=dbname,
        user=grafana.READER, password=password, autocommit=True,
    )  # fmt: skip


def _restart_grafana(**env: str) -> None:
    """Start Grafana again with ``env`` (compose recreates it when its environment changed)."""
    previous = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    try:
        compose("up", "-d", "--wait", "grafana")
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _start_log() -> str:
    return compose("logs", "--no-log-prefix", "grafana").stdout


@pytest.fixture
def reader(settings: Settings, migrated_database: str) -> Iterator[psycopg.Connection[Any]]:
    """The read-only role, logged in to the migrated test database."""
    with psycopg.connect(settings.postgres_conninfo(), autocommit=True) as admin:
        grafana.set_login(admin, SecretStr(os.environ["GRAFANA_DB_PASSWORD"]))
    with _reader(settings, migrated_database) as conn:
        yield conn


# T32.1
def test_grafana_starts_with_its_dashboards_source_and_rule_provisioned() -> None:
    with _admin() as client:
        assert client.get("/api/health").json()["database"] == "ok"
        found = {d["uid"] for d in client.get("/api/search", params={"type": "dash-db"}).json()}
        assert found >= DASHBOARDS
        source = client.get("/api/datasources/uid/credit-risk-postgres").json()
        assert (source["type"], source["user"]) == (
            "grafana-postgresql-datasource",
            "grafana_reader",
        )
        rules = client.get("/api/v1/provisioning/alert-rules").json()
        assert [r["uid"] for r in rules] == ["credit-risk-ops-alerts"]
        for uid in DASHBOARDS:
            dashboard = client.get(f"/api/dashboards/uid/{uid}").json()
            assert dashboard["meta"]["provisioned"] is True
            assert {link["url"] for link in dashboard["dashboard"]["links"]} == {
                f"/d/{u}" for u in DASHBOARDS
            }


# T32.2
def test_every_panel_query_runs_as_the_reader(reader: psycopg.Connection[Any]) -> None:
    found = grafana.queries()
    assert {q.dashboard for q in found} == DASHBOARDS
    assert len(found) >= 20
    dashboards = {
        q.dashboard: json.loads(p.read_text())
        for p in grafana.DASHBOARDS.glob("*.json")
        for q in found
        if json.loads(p.read_text())["uid"] == q.dashboard
    }
    for query in found:
        panel = next(
            p for p in dashboards[query.dashboard]["panels"] if p.get("title") == query.panel
        )
        target = next(t for t in panel["targets"] if t["refId"] == query.ref)
        cursor = reader.execute(grafana.runnable(query.sql, {"subject": "int_rate"}))
        assert cursor.description is not None, query.panel
        columns = [c.name for c in cursor.description]
        if target["format"] == "time_series":
            assert columns[0] == "time", query.panel
            assert len(columns) >= 2, query.panel
            assert set(columns) == {"time", "metric", "value"} or "metric" not in columns
        else:
            assert columns, query.panel


# T32.3
def test_the_reader_reads_the_dashboards_tables_and_nothing_else(
    reader: psycopg.Connection[Any],
) -> None:
    for table in (
        "monitoring.drift", "monitoring.early_warning", "monitoring.performance",
        "monitoring.reference", "ops.alerts", "ops.task_runs", "ops.training_sets",
        "serving.requests",
    ):  # fmt: skip
        reader.execute(f"SELECT * FROM {table} LIMIT 1")  # noqa: S608 - fixed names
    for table in ("raw.listings", "clean.listings", "clean.outcomes", "serving.predictions",
                  "serving.purchases", "ops.ingest_log"):  # fmt: skip
        with pytest.raises(errors.InsufficientPrivilege):
            reader.execute(f"SELECT * FROM {table} LIMIT 1")  # noqa: S608
    # Read only by default; and even when it asks to write, it has no right to.
    with pytest.raises(errors.ReadOnlySqlTransaction):
        reader.execute("DELETE FROM ops.alerts")
    reader.execute("SET default_transaction_read_only = off")
    for statement in (
        "INSERT INTO ops.alerts (kind, severity, message) VALUES ('promoted', 'info', 'x')",
        "UPDATE ops.alerts SET message = 'x'",
        "DELETE FROM monitoring.drift",
        "TRUNCATE ops.task_runs",
    ):
        with pytest.raises(errors.InsufficientPrivilege):
            reader.execute(statement)


class _Receiver(http.server.BaseHTTPRequestHandler):
    received: ClassVar[list[dict[str, Any]]] = []

    def do_POST(self) -> None:  # the name http.server calls
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        type(self).received.append(json.loads(body))
        self.send_response(200)
        self.end_headers()

    def log_message(self, *_args: Any) -> None:
        pass


@pytest.fixture(scope="module")
def receiver(settings: Settings) -> Iterator[list[dict[str, Any]]]:
    """Grafana started again with a webhook to a receiver in this process."""
    dbmate(database_url(settings, settings.postgres_db), "up")
    with psycopg.connect(settings.postgres_conninfo(), autocommit=True) as admin:
        grafana.set_login(admin, SecretStr(os.environ["GRAFANA_DB_PASSWORD"]))
    port = free_port()
    server = http.server.ThreadingHTTPServer(("0.0.0.0", port), _Receiver)  # noqa: S104
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _Receiver.received = []
    try:
        _restart_grafana(
            GRAFANA_WEBHOOK_URL=f"http://host.docker.internal:{port}/alerts",
            TELEGRAM_BOT_TOKEN="",
            TELEGRAM_CHAT_ID="",
        )
        yield _Receiver.received
    finally:
        server.shutdown()
        server.server_close()
        _restart_grafana(GRAFANA_WEBHOOK_URL="")


def _sent(received: list[dict[str, Any]], alert_id: int) -> list[dict[str, Any]]:
    return [
        alert
        for message in received
        for alert in message["alerts"]
        if alert["labels"].get("alert_id") == str(alert_id) and alert["status"] == "firing"
    ]


# T32.4
def test_a_new_warning_reaches_the_channel_once(
    settings: Settings, receiver: list[dict[str, Any]]
) -> None:
    tag = uuid.uuid4().hex[:8]
    with psycopg.connect(settings.postgres_conninfo(), autocommit=True) as conn:
        warning, info = (
            conn.execute(
                "INSERT INTO ops.alerts (kind, severity, period, message, details)"
                " VALUES (%s, %s, '2015-03-01', %s, %s) RETURNING alert_id",
                (kind, severity, f"test of delivery {tag} {kind}", json.dumps(details)),
            ).fetchone()[0]  # type: ignore[index]
            for kind, severity, details in (
                ("early_warning", "warning", {"signal": f"test-{tag}"}),
                ("rejected", "info", {}),
            )
        )
        try:
            deadline = time.monotonic() + DELIVERY_SECONDS
            while not _sent(receiver, warning):
                assert time.monotonic() < deadline, "the warning never reached the channel"
                time.sleep(1)
            (sent,) = _sent(receiver, warning)
            assert sent["labels"]["kind"] == "early_warning"
            assert sent["labels"]["severity"] == "warning"
            assert f"test of delivery {tag}" in sent["annotations"]["summary"]
            time.sleep(QUIET_SECONDS)  # three more evaluations of the rule
            assert len(_sent(receiver, warning)) == 1, "sent once, not at every evaluation"
            assert _sent(receiver, info) == [], "an info is only shown, never sent"
        finally:
            conn.execute("DELETE FROM ops.alerts WHERE alert_id IN (%s, %s)", (warning, info))


# T32.5
def test_without_telegram_grafana_starts_and_the_other_channel_works(
    receiver: list[dict[str, Any]],
) -> None:
    assert "start.sh: contact point with webhook" in _start_log()
    with _admin() as client:
        assert client.get("/api/health").status_code == 200
        points = client.get("/api/v1/provisioning/contact-points").json()
        types = {p["type"] for p in points if p["name"] == "credit-risk"}
        assert types == {"webhook"}, "no Telegram without its secrets"
        found = {d["uid"] for d in client.get("/api/search", params={"type": "dash-db"}).json()}
        assert found >= DASHBOARDS
    assert receiver is not None  # the delivery itself: T32.4, in this same state


# T32.6
def test_nothing_is_shown_without_logging_in() -> None:
    with httpx.Client(base_url=_url(), trust_env=False, timeout=10) as anonymous:
        assert anonymous.get("/api/search").status_code == 401
        assert anonymous.get("/api/dashboards/uid/credit-risk-model").status_code == 401
        assert anonymous.get("/api/datasources").status_code == 401
        page = anonymous.get("/d/credit-risk-model", follow_redirects=False)
        assert page.status_code == 302
    assert "/login" in page.headers["location"]
