"""T20.5: purchases against the real Postgres (D-124, D-129, D-121), approved by Juan on
2026-11-25.

Made-up champions in the MLflow server, as in ``test_api.py``, and a migrated database
of this module's own. What the API decides is checked in ``tests/unit/test_purchases.py``;
here, what only the database can keep: its constraint, its locks and its transactions.
"""

import os
import threading
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import mlflow
import psycopg
import pytest
from fastapi.testclient import TestClient

from credit_risk import __version__
from credit_risk.api.app import create_app
from credit_risk.api.champions import Holder, Registry
from credit_risk.api.purchases import Order, Outcome
from credit_risk.api.store import RequestRow, Store
from credit_risk.buy_rule import NAME as RULE
from credit_risk.settings import Settings
from tests.api_support import PREDICT_KEY, loan, rule, settings, toy_models

from .conftest import database_url, dbmate
from .test_api import _register, _remove

pytestmark = pytest.mark.integration

PREDICT = {"X-API-Key": PREDICT_KEY}


@dataclass(frozen=True)
class Shop:
    prefix: str
    conninfo: str


@pytest.fixture(scope="module")
def shop(settings: Settings) -> Iterator[Shop]:
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    prefix = f"test-buy-{uuid.uuid4().hex[:8]}-"
    name = f"test_buy_{uuid.uuid4().hex[:8]}"
    models = toy_models()
    with psycopg.connect(settings.postgres_conninfo(), autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{name}"')
    try:
        dbmate(database_url(settings, name), "up")
        _register(f"{prefix}pd", models[0])
        _register(f"{prefix}lgd", models[1])
        _register(f"{prefix}{RULE}", rule(0.05, "1", "1"))
        conninfo = settings.postgres_conninfo().replace(
            f"dbname={settings.postgres_db}", f"dbname={name}"
        )
        yield Shop(prefix, conninfo)
    finally:
        _remove(prefix)
        with psycopg.connect(settings.postgres_conninfo(), autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def _client(shop: Shop) -> TestClient:
    holder = Holder(Registry(shop.prefix), alert=lambda _: None)
    app = create_app(
        settings(model_prefix=shop.prefix), holder, Store(shop.conninfo, 4), polling=False
    )
    return TestClient(app)


def _rows(shop: Shop, query: str, *args: Any) -> list[tuple[Any, ...]]:
    with psycopg.connect(shop.conninfo) as conn:
        return conn.execute(query, args).fetchall()


def _predicted(shop: Shop, id_: int) -> int:
    with _client(shop) as client:
        answer = client.post("/predict", json=loan(id_), headers=PREDICT)
    assert answer.status_code == 200, answer.text
    prediction_id: int = answer.json()["prediction_id"]
    return prediction_id


def _row() -> RequestRow:
    row = RequestRow(uuid.uuid4(), "/purchases", __version__)
    row.client = "replayer"
    return row


def _at_once(shop: Shop, orders: list[Order]) -> list[Outcome]:
    """Each order by its own request and connection, all released at the same moment."""
    store = Store(shop.conninfo, len(orders) + 1)
    store.open()
    gate = threading.Barrier(len(orders))
    outcomes: list[Outcome] = []
    lock = threading.Lock()

    def send(order: Order) -> None:
        gate.wait()
        [o] = store.purchase(_row(), [order], lambda _: None)
        with lock:
            outcomes.append(o)

    threads = [threading.Thread(target=send, args=(o,)) for o in orders]
    try:
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    finally:
        store.close()
    return outcomes


# T20.5
def test_the_database_keeps_one_row_per_order_and_whole_requests(shop: Shop) -> None:
    p = _predicted(shop, 71_001)
    with _client(shop) as client:
        body = {"purchases": [{"order_id": "a-1", "prediction_id": p, "amount": 25}]}
        first = client.post("/purchases", json=body, headers=PREDICT).json()
        client.post("/purchases", json=body, headers=PREDICT)
    assert first["results"][0]["status"] == "created"
    assert _rows(shop, "SELECT count(*) FROM serving.purchases WHERE order_id = 'a-1'") == [(1,)]
    # Each request has its row, with the client and its counts (D-115).
    requests = _rows(
        shop,
        "SELECT client, status, loans, rejected FROM serving.requests"
        " WHERE endpoint = '/purchases' ORDER BY at",
    )
    assert requests[-2:] == [("replayer", 200, 1, 0), ("replayer", 200, 1, 0)]

    # The constraint is in the database, whoever writes.
    with psycopg.connect(shop.conninfo) as conn, pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute(
            "INSERT INTO serving.purchases (request_id, client, order_id, prediction_id,"
            " loan_id, amount, policy) SELECT request_id, client, order_id, prediction_id,"
            " loan_id, amount, policy FROM serving.purchases WHERE order_id = 'a-1'"
        )


def test_two_requests_at_once_cannot_duplicate_an_order_or_overfill_a_loan(shop: Shop) -> None:
    p = _predicted(shop, 71_002)
    same = _at_once(shop, [Order(order_id="b-1", prediction_id=p, amount=25)] * 2)
    assert sorted(o.status for o in same) == ["created", "stored_earlier"]
    assert _rows(shop, "SELECT count(*) FROM serving.purchases WHERE order_id = 'b-1'") == [(1,)]

    # Two orders that each fill the rest of the 10,000 dollar loan: only one fits.
    q = _predicted(shop, 71_003)
    full = _at_once(
        shop,
        [Order(order_id=f"c-{i}", prediction_id=q, amount=10_000) for i in range(2)],
    )
    assert sorted((o.status, o.code) for o in full) == [("created", 200), ("refused", 422)]
    held = _rows(shop, "SELECT sum(amount) FROM serving.purchases WHERE loan_id = 71003")
    assert held == [(10_000,)]


def test_a_request_that_fails_halfway_records_nothing(shop: Shop) -> None:
    p = _predicted(shop, 71_004)
    good = Order(order_id="d-1", prediction_id=p, amount=25)
    # Past the API's own checks, the second breaks a CHECK of the table.
    broken = Order.model_construct(order_id="d" * 101, prediction_id=p, amount=25)
    store = Store(shop.conninfo, 2)
    store.open()
    row = _row()
    try:
        with pytest.raises(psycopg.errors.CheckViolation):
            store.purchase(row, [good, broken], lambda _: None)
    finally:
        store.close()
    assert _rows(shop, "SELECT count(*) FROM serving.purchases WHERE loan_id = 71004") == [(0,)]
    assert _rows(
        shop, "SELECT count(*) FROM serving.requests WHERE request_id = %s", row.request_id
    ) == [(0,)]
