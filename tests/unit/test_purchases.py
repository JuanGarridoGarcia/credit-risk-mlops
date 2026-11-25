"""T20.1 to T20.4: what the investor bought, reported to the API (D-124 to D-129).

As in ``test_api.py``: made-up models, a registry in a dictionary and a store in memory
that keeps the promises of Postgres. The same API against the real Postgres, with its
constraint and its locks, is in ``tests/integration/test_purchases.py`` (T20.5).
"""

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from credit_risk.api.app import create_app
from credit_risk.api.champions import Holder
from credit_risk.model import LGDModel, PDModel
from tests.api_support import (
    ADMIN_KEY,
    NEXT_PREDICT_KEY,
    PREDICT_KEY,
    FakeRegistry,
    MemoryStore,
    loan,
    rule,
    settings,
    toy_models,
)

PREDICT = {"X-API-Key": PREDICT_KEY}
OTHER = {"X-API-Key": NEXT_PREDICT_KEY}  # another client: "replayer-next"


@pytest.fixture(scope="module")
def models() -> tuple[PDModel, LGDModel]:
    return toy_models()


class Shop:
    """An application whose buy rule has the given minimum."""

    def __init__(self, models: tuple[PDModel, LGDModel], minimum: float | None) -> None:
        self.registry = FakeRegistry()
        self.registry.put("pd", "1", models[0])
        self.registry.put("lgd", "1", models[1])
        if minimum is not None:
            self.registry.put("buy_rule", "1", rule(minimum))
        self.store = MemoryStore()
        holder = Holder(self.registry, lambda _: None)
        self.app = create_app(settings(max_batch=5), holder, self.store, polling=False)


@pytest.fixture
def shop(models: tuple[PDModel, LGDModel]) -> Iterator[tuple[Shop, TestClient]]:
    s = Shop(models, 0.05)
    with TestClient(s.app) as client:
        yield s, client


def _predict(client: TestClient, id_: int, term: str = " 36 months") -> dict[str, Any]:
    answer = client.post("/predict", json=loan(id_, term=term), headers=PREDICT)
    assert answer.status_code == 200, answer.text
    body: dict[str, Any] = answer.json()
    return body


def _buy(
    client: TestClient, *orders: dict[str, Any], headers: dict[str, str] = PREDICT
) -> list[dict[str, Any]]:
    answer = client.post("/purchases", json={"purchases": list(orders)}, headers=headers)
    assert answer.status_code == 200, answer.text
    results: list[dict[str, Any]] = answer.json()["results"]
    return results


def _order(order_id: str, prediction_id: int, amount: Any = 25) -> dict[str, Any]:
    return {"order_id": order_id, "prediction_id": prediction_id, "amount": amount}


# T20.1
def test_a_purchase_of_a_stored_prediction_is_recorded(shop: tuple[Shop, TestClient]) -> None:
    s, client = shop
    first, second = _predict(client, 101), _predict(client, 102)
    assert isinstance(first["prediction_id"], int)
    assert first["prediction_id"] != second["prediction_id"]
    [result] = _buy(client, _order("2015-03-101", first["prediction_id"]))
    assert result["status"] == "created"
    bought = result["purchase"]
    assert {k: bought[k] for k in ("order_id", "prediction_id", "loan_id", "amount")} == {
        "order_id": "2015-03-101",
        "prediction_id": first["prediction_id"],
        "loan_id": 101,
        "amount": 25.0,
    }
    stored = s.store.purchases[("replayer", "2015-03-101")]
    assert (stored.client, stored.loan_id) == ("replayer", 101)
    assert stored.amount == Decimal(25)
    assert s.store.requests[-1].endpoint == "/purchases"
    assert s.store.requests[-1].client == "replayer"


# T20.2
def test_an_order_number_makes_a_repeat_harmless_and_allows_repurchases(
    shop: tuple[Shop, TestClient],
) -> None:
    s, client = shop
    p = _predict(client, 201)["prediction_id"]
    [created] = _buy(client, _order("o-1", p))
    [again] = _buy(client, _order("o-1", p))
    assert again["status"] == "stored_earlier"
    assert again["purchase"] == created["purchase"]
    assert len(s.store.purchases) == 1
    # The same order number for another purchase is a conflict, not a new purchase.
    [conflict] = _buy(client, _order("o-1", p, 50))
    assert (conflict["status"], conflict["code"]) == ("refused", 409)
    assert conflict["errors"][0]["column"] == "order_id"
    # A new order on the same loan adds to the share: a repurchase.
    [more] = _buy(client, _order("o-2", p, 975))
    assert more["status"] == "created"
    held = [x.amount for x in s.store.purchases.values() if x.client == "replayer"]
    assert sum(held) == 1_000
    # Another client buys the same loan, with the same order number of its own.
    [theirs] = _buy(client, _order("o-1", p), headers=OTHER)
    assert theirs["status"] == "created"
    assert s.store.purchases[("replayer-next", "o-1")].loan_id == 201


# T20.3
@pytest.mark.parametrize(
    ("order", "column"),
    [
        (_order("x-1", 10_000), "prediction_id"),
        (_order("x-2", 1, 30), "amount"),
        (_order("x-3", 1, 0), "amount"),
        (_order("x-4", 1, -25), "amount"),
        (_order("x-5", 1, 10_025), "amount"),
        (_order("x-6", 1, 25.0), "amount"),
        ({"order_id": "x-7", "prediction_id": 1}, "amount"),
        ({**_order("x-8", 1), "note": "extra"}, "note"),
        (_order("", 1), "order_id"),
    ],
    ids=["unknown", "not 25s", "zero", "negative", "above loan", "float", "no amount",
         "unknown field", "empty order"],
)  # fmt: skip
def test_a_wrong_purchase_is_refused_on_its_own(
    shop: tuple[Shop, TestClient], order: dict[str, Any], column: str
) -> None:
    s, client = shop
    assert _predict(client, 301)["prediction_id"] == 1  # a loan of 10,000 dollars
    good = _order("ok", 1)
    results = _buy(client, order, good)
    assert (results[0]["status"], results[0]["code"]) == ("refused", 422)
    assert results[0]["errors"][0]["column"] == column
    assert results[1]["status"] == "created"
    assert list(s.store.purchases) == [("replayer", "ok")]
    row = s.store.requests[-1]
    assert (row.loans, row.rejected) == (1, 1)
    assert row.body == {"items": {"0": order}}
    assert row.errors["0"][0]["column"] == column


@pytest.mark.parametrize(
    "body",
    [
        {"purchases": [_order(f"m-{i}", 1) for i in range(6)]},
        {"purchases": []},
        {"purchases": "not a list"},
        {"orders": [_order("m-1", 1)]},
    ],
    ids=["too many", "empty", "not a list", "wrong key"],
)
def test_a_malformed_request_is_refused_whole(
    shop: tuple[Shop, TestClient], body: dict[str, Any]
) -> None:
    s, client = shop
    _predict(client, 302)
    answer = client.post("/purchases", json=body, headers=PREDICT)
    assert answer.status_code == 422
    assert s.store.purchases == {}
    assert s.store.requests[-1].status == 422


def test_purchases_need_a_predict_key(shop: tuple[Shop, TestClient]) -> None:
    s, client = shop
    body = {"purchases": [_order("k-1", _predict(client, 303)["prediction_id"])]}
    assert client.post("/purchases", json=body).status_code == 401
    assert client.post("/purchases", json=body, headers={"X-API-Key": "z" * 40}).status_code == 401
    assert client.post("/purchases", json=body, headers={"X-API-Key": ADMIN_KEY}).status_code == 403
    assert s.store.purchases == {}


# T20.4
@pytest.mark.parametrize(
    ("minimum", "term", "policy"),
    [
        (-1.0, " 36 months", "passes"),
        (0.99, " 36 months", "below_minimum"),
        (None, " 36 months", "no_threshold"),
        (0.05, " 60 months", "not_covered"),
    ],
)
def test_exceptions_to_the_rule_are_recorded_not_refused(
    models: tuple[PDModel, LGDModel], minimum: float | None, term: str, policy: str
) -> None:
    s = Shop(models, minimum)
    with TestClient(s.app) as client:
        answer = _predict(client, 401, term=term)
        [result] = _buy(client, _order("e-1", answer["prediction_id"]))
    assert result["status"] == "created"
    assert result["purchase"]["policy"] == policy
    assert s.store.purchases[("replayer", "e-1")].policy == policy
