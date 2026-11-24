"""T18.1 to T18.5, T18.7 to T18.10 and T18.12: the API on made-up models (step 5.1).

The models are trained on made-up 36-month loans (60 months is not covered); the
registry is a dictionary and the store keeps its promises in memory. The same checks
against the real Postgres and MLflow are in ``tests/integration/test_api.py``.
"""

import json
import logging
import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from credit_risk import __version__
from credit_risk.alerts import Alert
from credit_risk.api.app import create_app
from credit_risk.api.champions import Holder
from credit_risk.api.scoring import NOT_COVERED, cleaning_errors, score
from credit_risk.api.settings import ApiSettings
from credit_risk.model import LGDModel, PDModel
from tests.api_support import (
    ADMIN_KEY,
    NEXT_PREDICT_KEY,
    PREDICT_KEY,
    FakeRegistry,
    MemoryStore,
    loan,
    raw_frame,
    rule,
    settings,
)
from tests.api_support import toy_models as _toy_models

PREDICT = {"X-API-Key": PREDICT_KEY}
ADMIN = {"X-API-Key": ADMIN_KEY}


@pytest.fixture(scope="module")
def models() -> tuple[PDModel, LGDModel]:
    return _toy_models()


class Api:
    """One application with its registry, store and recorded alerts."""

    def __init__(
        self, models: tuple[PDModel, LGDModel], config: ApiSettings, *, polling: bool = False
    ) -> None:
        self.registry = FakeRegistry()
        self.registry.put("pd", "1", models[0])
        self.registry.put("lgd", "1", models[1])
        self.registry.put("buy_rule", "1", rule())
        self.store = MemoryStore()
        self.alerts: list[Alert] = []
        self.holder = Holder(self.registry, self.alerts.append)
        self.app = create_app(config, self.holder, self.store, polling=polling)


@pytest.fixture
def api(models: tuple[PDModel, LGDModel]) -> Iterator[tuple[Api, TestClient]]:
    a = Api(models, settings(max_batch=5))
    with TestClient(a.app) as client:
        yield a, client


def _strip(prediction: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in prediction.items() if k != "stored_earlier"}


# T18.1
def test_one_listing_gets_its_full_answer(
    api: tuple[Api, TestClient], models: tuple[PDModel, LGDModel]
) -> None:
    a, client = api
    item = loan(1)
    answer = client.post("/predict", json=item, headers=PREDICT)
    assert answer.status_code == 200, answer.text
    body = answer.json()
    raw = raw_frame([item])
    typed, errors = cleaning_errors(raw)
    assert errors == [[]]
    expected = score(a.holder.current, typed, raw)[0]
    assert body["covered"] is True
    assert body["note"] is None
    for field in ("pd", "lgd", "ead", "expected_loss", "el_rate", "expected_return"):
        assert body[field] == getattr(expected, field), field
    assert body["ead"] == 10_000.0
    assert body["expected_loss"] == body["pd"] * body["lgd"] * body["ead"]
    assert body["el_rate"] == body["pd"] * body["lgd"]
    assert body["threshold"] == {
        "available": True,
        "minimum": 0.05,
        "passes": body["expected_return"] >= 0.05,
    }
    assert len(body["reasons"]) == 4
    assert [r["feature"] for r in body["reasons"]] == [r["feature"] for r in expected.reasons]
    assert body["versions"] == {"pd": "1", "lgd": "1", "buy_rule": "1", "api": __version__}
    assert body["stored_earlier"] is False
    assert body["request_id"] == answer.headers["X-Request-ID"]


# T18.2
def test_an_uncovered_term_gets_no_risk_and_is_stored(api: tuple[Api, TestClient]) -> None:
    a, client = api
    body = client.post("/predict", json=loan(2, term=" 60 months"), headers=PREDICT).json()
    assert body["covered"] is False
    assert body["note"] == NOT_COVERED
    for field in ("pd", "lgd", "expected_loss", "el_rate", "expected_return", "threshold"):
        assert body[field] is None, field
    assert body["reasons"] == []
    assert body["ead"] == 10_000.0
    assert (2, "1", "1") in a.store.predictions


# T18.3
@pytest.mark.parametrize(
    ("change", "column"),
    [
        ({"drop": "dti"}, "dti"),
        ({"set": ("term", " 36 monthz")}, "term"),
        ({"set": ("int_rate", "ten")}, "int_rate"),
        ({"set": ("favourite_colour", "blue")}, "favourite_colour"),
        ({"set": ("loan_amnt", 10_000)}, "loan_amnt"),
        ({"set": ("id", None)}, "id"),
    ],
    ids=["missing", "term", "number", "unknown", "not text", "no id"],
)
def test_invalid_input_is_refused_with_its_column_and_recorded(
    api: tuple[Api, TestClient], change: dict[str, Any], column: str
) -> None:
    a, client = api
    item = loan(3)
    if "drop" in change:
        del item[change["drop"]]
    else:
        key, value = change["set"]
        item[key] = value
    answer = client.post("/predict", json=item, headers=PREDICT)
    assert answer.status_code == 422
    errors = answer.json()["errors"]
    assert [e["column"] for e in errors] == [column]
    assert errors[0]["message"]
    assert not a.store.predictions
    row = a.store.requests[-1]
    assert (row.status, row.endpoint, row.loans, row.rejected) == (422, "/predict", 0, 1)
    assert row.client == "replayer"
    assert row.body is not None
    assert row.errors is not None


# T18.4
def test_a_batch_answers_exactly_as_one_by_one(models: tuple[PDModel, LGDModel]) -> None:
    items = [loan(100 + i, term=" 60 months" if i % 4 == 0 else " 36 months") for i in range(5)]
    for i, item in enumerate(items):
        item["int_rate"] = f"{8 + 3 * i}.5"
        item["dti"] = f"{5 + 4 * i}.0"
    single, batch = Api(models, settings()), Api(models, settings())
    with TestClient(single.app) as one, TestClient(batch.app) as many:
        alone = [one.post("/predict", json=x, headers=PREDICT).json() for x in items]
        together = many.post("/predict/batch", json={"loans": items}, headers=PREDICT).json()
    assert [r["index"] for r in together["results"]] == list(range(5))
    for a, r in zip(alone, together["results"], strict=True):
        assert _strip(r["prediction"]) == _strip({k: v for k, v in a.items() if k != "request_id"})


def test_a_batch_answers_each_loan_on_its_own(api: tuple[Api, TestClient]) -> None:
    a, client = api
    items = [loan(200), loan(201, term="ten"), loan(202), {"id": "203"}, loan(204)]
    answer = client.post("/predict/batch", json={"loans": items}, headers=PREDICT)
    assert answer.status_code == 200
    results = answer.json()["results"]
    assert [("prediction" in r, r["index"]) for r in results] == [
        (True, 0), (False, 1), (True, 2), (False, 3), (True, 4)
    ]  # fmt: skip
    assert results[1]["errors"][0]["column"] == "term"
    assert {e["column"] for e in results[3]["errors"]} >= {"dti", "term", "grade"}
    assert {k[0] for k in a.store.predictions} == {200, 202, 204}
    row = a.store.requests[-1]
    assert (row.loans, row.rejected) == (3, 2)
    assert set(row.body["items"]) == {"1", "3"}
    assert set(row.errors) == {"1", "3"}


@pytest.mark.parametrize(
    "body",
    [
        {"loans": [loan(300 + i) for i in range(6)]},
        {"loans": []},
        {"loans": "not a list"},
        {"listings": [loan(300)]},
    ],
    ids=["too many", "empty", "not a list", "wrong key"],
)
def test_a_malformed_batch_is_refused_whole(
    api: tuple[Api, TestClient], body: dict[str, Any]
) -> None:
    a, client = api
    answer = client.post("/predict/batch", json=body, headers=PREDICT)
    assert answer.status_code == 422
    assert not a.store.predictions
    assert a.store.requests[-1].status == 422


def test_broken_json_is_refused(api: tuple[Api, TestClient]) -> None:
    _, client = api
    answer = client.post(
        "/predict/batch",
        content=b'{"loans": [',
        headers={**PREDICT, "Content-Type": "application/json"},
    )
    assert answer.status_code == 422


# T18.5
def test_keys_decide_who_may_call_what(
    api: tuple[Api, TestClient], caplog: pytest.LogCaptureFixture
) -> None:
    a, client = api
    caplog.set_level(logging.INFO)
    assert client.post("/predict", json=loan(400)).status_code == 401
    assert (
        client.post("/predict", json=loan(400), headers={"X-API-Key": "x" * 40}).status_code == 401
    )
    assert client.post("/predict", json=loan(400), headers=ADMIN).status_code == 403
    assert client.post("/admin/reload", headers=PREDICT).status_code == 403
    assert client.post("/admin/reload", headers=ADMIN).status_code == 200
    # Rotation: the old and the new key are valid at the same time.
    assert client.post("/predict", json=loan(401), headers=PREDICT).status_code == 200
    next_key = {"X-API-Key": NEXT_PREDICT_KEY}
    assert client.post("/predict", json=loan(402), headers=next_key).status_code == 200
    assert client.get("/health").status_code == 200
    clients = [r.client for r in a.store.requests]
    assert clients == [None, None, "flow", "replayer", "flow", "replayer", "replayer-next"]
    seen = caplog.text + repr(a.store.requests) + json.dumps(list(a.store.predictions.values()))
    for key in (PREDICT_KEY, NEXT_PREDICT_KEY, ADMIN_KEY):
        assert key not in seen


def test_short_or_malformed_keys_stop_the_start() -> None:
    from pydantic import SecretStr

    from credit_risk.api.settings import KeysError, parse_keys

    for bad in ("replayer:short", "no-name-" + "k" * 40, f"a:{'k' * 40},b:{'k' * 40}", ""):
        with pytest.raises(KeysError):
            parse_keys(SecretStr(bad))


# T18.7 (in memory; the real Postgres in tests/integration/test_api.py)
def test_no_prediction_leaves_without_being_stored(api: tuple[Api, TestClient]) -> None:
    a, client = api
    a.store.up = False
    answer = client.post("/predict", json=loan(500), headers=PREDICT)
    assert answer.status_code == 503
    assert "pd" not in answer.json()
    many = client.post("/predict/batch", json={"loans": [loan(501)]}, headers=PREDICT)
    assert many.status_code == 503
    assert not a.store.predictions
    assert client.get("/health").status_code == 503


# T18.8 (in memory; loading from the real MLflow in tests/integration/test_api.py)
def test_the_api_is_not_ready_until_it_can_load_the_champions(
    models: tuple[PDModel, LGDModel],
) -> None:
    a = Api(models, settings(reload_seconds=0.1), polling=True)
    a.registry.down = True
    with TestClient(a.app) as client:
        health = client.get("/health")
        assert health.status_code == 503
        assert health.json()["models"] is None
        assert client.get("/health/live").status_code == 200
        assert client.post("/predict", json=loan(600), headers=PREDICT).status_code == 503
        a.registry.down = False
        _wait(lambda: client.get("/health").status_code == 200)
        assert client.get("/health").json()["models"] == {"pd": "1", "lgd": "1", "buy_rule": "1"}
        assert client.post("/predict", json=loan(600), headers=PREDICT).status_code == 200
    assert len(a.alerts) == 1  # the same failure, polled many times, alerts once


def _wait(condition: Any, seconds: float = 5.0) -> None:
    deadline = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < deadline, "condition not met in time"
        time.sleep(0.05)


# T18.9
def test_a_new_champion_is_served_at_once_after_the_notice(
    api: tuple[Api, TestClient], models: tuple[PDModel, LGDModel]
) -> None:
    a, client = api
    a.registry.put("pd", "2", models[0])
    a.registry.put("lgd", "2", models[1])
    a.registry.put("buy_rule", "2", rule(0.07, "2", "2"))
    assert client.post("/predict", json=loan(700), headers=PREDICT).json()["versions"]["pd"] == "1"
    reload = client.post("/admin/reload", headers=ADMIN).json()
    assert reload == {"changed": True, "versions": {"pd": "2", "lgd": "2", "buy_rule": "2"}}
    body = client.post("/predict", json=loan(701), headers=PREDICT).json()
    assert body["versions"]["pd"] == "2"
    assert body["threshold"]["minimum"] == 0.07
    assert client.post("/admin/reload", headers=ADMIN).json()["changed"] is False


def test_polling_finds_a_new_champion_without_the_notice(
    models: tuple[PDModel, LGDModel],
) -> None:
    a = Api(models, settings(reload_seconds=0.1), polling=True)
    with TestClient(a.app) as client:
        a.registry.put("pd", "2", models[0])
        _wait(lambda: client.get("/health").json()["models"]["pd"] == "2")


def test_a_champion_that_fails_to_load_leaves_the_pair_in_use(
    api: tuple[Api, TestClient], models: tuple[PDModel, LGDModel]
) -> None:
    a, client = api
    a.registry.put("pd", "2", models[0])
    a.registry.put("lgd", "2", models[1])
    a.registry.broken.add(("lgd", "2"))
    answer = client.post("/admin/reload", headers=ADMIN)
    assert answer.status_code == 503
    assert answer.json()["versions"] == {"pd": "1", "lgd": "1", "buy_rule": "1"}
    body = client.post("/predict", json=loan(800), headers=PREDICT).json()
    assert (body["versions"]["pd"], body["versions"]["lgd"]) == ("1", "1")
    assert [x.kind for x in a.alerts] == ["model_load_failed"]
    assert a.alerts[0].severity == "error"


def test_no_request_mixes_two_pairs_during_a_swap(models: tuple[PDModel, LGDModel]) -> None:
    a = Api(models, settings())
    for version in ("2", "3"):
        a.registry.put("pd", version, models[0], champion=False)
        a.registry.put("lgd", version, models[1], champion=False)
    seen: list[tuple[str, str]] = []
    stop = threading.Event()
    with TestClient(a.app) as client:

        def ask() -> None:
            n = 0
            while not stop.is_set():
                n += 1
                body = client.post(
                    "/predict/batch",
                    json={"loans": [loan(10_000 + n * 10 + i) for i in range(3)]},
                    headers=PREDICT,
                ).json()
                for r in body["results"]:
                    v = r["prediction"]["versions"]
                    seen.append((v["pd"], v["lgd"]))

        threads = [threading.Thread(target=ask) for _ in range(4)]
        for t in threads:
            t.start()
        for version in ("2", "3", "1", "2", "3"):
            a.registry.aliases.update(pd=version, lgd=version)
            client.post("/admin/reload", headers=ADMIN)
            time.sleep(0.05)
        stop.set()
        for t in threads:
            t.join()
    assert seen
    assert all(pd == lgd for pd, lgd in seen)


# T18.10
def test_a_rule_of_another_pair_gives_no_threshold(
    models: tuple[PDModel, LGDModel],
) -> None:
    a = Api(models, settings())
    a.registry.put("buy_rule", "2", rule(0.05, pd_version="9"))
    with TestClient(a.app) as client:
        body = client.post("/predict", json=loan(900), headers=PREDICT).json()
    assert body["pd"] is not None
    assert body["expected_return"] is not None
    assert body["threshold"] == {"available": False, "minimum": None, "passes": None}


def test_no_rule_yet_gives_no_threshold(models: tuple[PDModel, LGDModel]) -> None:
    a = Api(models, settings())
    a.registry.aliases["buy_rule"] = None
    with TestClient(a.app) as client:
        body = client.post("/predict", json=loan(901), headers=PREDICT).json()
    assert body["threshold"]["available"] is False
    assert body["versions"]["buy_rule"] is None


# T18.12
def test_one_json_line_per_request_without_keys_or_bodies(
    api: tuple[Api, TestClient], caplog: pytest.LogCaptureFixture
) -> None:
    _, client = api
    caplog.set_level(logging.INFO, logger="credit_risk.api.access")
    client.post("/predict", json=loan(1000, desc="my private story"), headers=PREDICT)
    client.post("/predict", json=loan(1001, term="bad"), headers=PREDICT)
    client.post("/predict", json=loan(1002))
    client.get("/health")
    lines = [r.getMessage() for r in caplog.records if r.name == "credit_risk.api.access"]
    assert len(lines) == 4
    records = [json.loads(line) for line in lines]
    assert [(r["path"], r["status"]) for r in records] == [
        ("/predict", 200), ("/predict", 422), ("/predict", 401), ("/health", 200)
    ]  # fmt: skip
    for r in records:
        assert set(r) >= {"request_id", "path", "status", "latency_ms", "client", "versions"}
        assert r["latency_ms"] >= 0
    assert records[0]["versions"] == {"pd": "1", "lgd": "1", "buy_rule": "1"}
    assert records[0]["client"] == "replayer"
    text = "\n".join(lines)
    assert PREDICT_KEY not in text
    assert "my private story" not in text
    assert "bad" not in text
