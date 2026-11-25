"""T18.6 to T18.8, T18.11, T18.13 and T18.14: the API against the services of docker compose
(step 5.1, D-110 to D-121), approved by Juan on 2026-11-24.

Each test module registers its own made-up champions in the MLflow server under names of
its own and writes to a migrated database of its own. T18.13 serves the application with
its own process on a free port and loads it at 20 requests a second for a minute.
"""

import math
import os
import socket
import statistics
import threading
import time
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from typing import Any

import httpx
import mlflow
import numpy as np
import psycopg
import pytest
from fastapi.testclient import TestClient
from mlflow import MlflowClient

from credit_risk import __version__, registry
from credit_risk.api.app import create_app
from credit_risk.api.champions import Holder, Registry
from credit_risk.api.scoring import frame_of, score
from credit_risk.api.store import Store
from credit_risk.buy_rule import NAME as RULE
from credit_risk.cleaning import clean_listings
from credit_risk.features import FEATURES, build_features
from credit_risk.model import LGDModel, PDModel, logit
from credit_risk.settings import Settings
from tests.api_support import PREDICT_KEY, loan, rule, settings, toy_models

from .api_process import api_process
from .conftest import IMAGES, compose, docker

pytestmark = pytest.mark.integration

PREDICT = {"X-API-Key": PREDICT_KEY}
#: T18.13 (D-122): an open load of RATE requests a second for LOAD_SECONDS, against the
#: latency objective of problem.md; then the capacity, measured for the record.
RATE, LOAD_SECONDS, P95_MS = 20.0, 60.0, 200.0
POOL, CAPACITY_SECONDS = 20, 20.0


@dataclass(frozen=True)
class Served:
    prefix: str
    conninfo: str
    models: tuple[PDModel, LGDModel]


def _register(name: str, model: Any, *, champion: bool = True) -> str:
    mlflow.set_experiment(name)
    with mlflow.start_run() as run:
        pass
    registry.log_model(run.info.run_id, model)
    version = registry.register(name, run.info.run_id, f"runs:/{run.info.run_id}/model")
    if champion:
        MlflowClient().set_registered_model_alias(name, registry.CHAMPION, version)
    return version


def _remove(prefix: str) -> None:
    client = MlflowClient()
    for target in ("pd", "lgd", RULE):
        name = f"{prefix}{target}"
        if client.search_registered_models(f"name='{name}'"):
            for version in client.search_model_versions(f"name='{name}'"):
                client.delete_model_version(name, version.version)
            client.delete_registered_model(name)
    for experiment in client.search_experiments(filter_string=f"name LIKE '{prefix}%'"):
        client.delete_experiment(experiment.experiment_id)


@pytest.fixture(scope="module")
def served(settings: Settings, migrated_database: str) -> Iterator[Served]:
    """Made-up champions (PD v1, LGD v1, rule v1) in MLflow, and a migrated database."""
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    prefix = f"test-api-{uuid.uuid4().hex[:8]}-"
    models = toy_models()
    try:
        assert _register(f"{prefix}pd", models[0]) == "1"
        assert _register(f"{prefix}lgd", models[1]) == "1"
        assert _register(f"{prefix}{RULE}", rule(0.05, "1", "1")) == "1"
        conninfo = settings.postgres_conninfo().replace(
            f"dbname={settings.postgres_db}", f"dbname={migrated_database}"
        )
        with psycopg.connect(conninfo, autocommit=True) as conn:
            conn.execute("TRUNCATE serving.purchases, serving.predictions, serving.requests")
        yield Served(prefix, conninfo, models)
    finally:
        _remove(prefix)


def _client(served: Served, conninfo: str | None = None, **config: Any) -> TestClient:
    holder = Holder(Registry(served.prefix), alert=lambda _: None)
    store = Store(conninfo or served.conninfo, 4)
    app = create_app(settings(model_prefix=served.prefix, **config), holder, store, polling=False)
    return TestClient(app)


def _rows(served: Served, query: str, *args: Any) -> list[tuple[Any, ...]]:
    with psycopg.connect(served.conninfo) as conn:
        return conn.execute(query, args).fetchall()


# T18.6
def test_the_same_loan_and_pair_is_stored_once(served: Served) -> None:
    item = loan(61_001)
    with _client(served) as client:
        first = client.post("/predict", json=item, headers=PREDICT).json()
        again = client.post("/predict", json=item, headers=PREDICT).json()
        assert first["stored_earlier"] is False
        assert again["stored_earlier"] is True
        assert {k: v for k, v in again.items() if k not in ("stored_earlier", "request_id")} == {
            k: v for k, v in first.items() if k not in ("stored_earlier", "request_id")
        }
        count = "SELECT count(*) FROM serving.predictions WHERE loan_id = %s"
        assert _rows(served, count, 61_001) == [(1,)]
        # A new champion scores the loan again: a new row, with the new versions.
        pd_v2 = _register(f"{served.prefix}pd", served.models[0])
        try:
            assert client.post("/admin/reload", headers={"X-API-Key": "a" * 40}).status_code == 200
            third = client.post("/predict", json=item, headers=PREDICT).json()
        finally:
            MlflowClient().set_registered_model_alias(f"{served.prefix}pd", registry.CHAMPION, "1")
        assert third["stored_earlier"] is False
        assert third["versions"]["pd"] == pd_v2
        assert third["threshold"]["available"] is False  # the rule belongs to pd v1
        assert _rows(served, count, 61_001) == [(2,)]
    # The database itself refuses a duplicate, whoever writes it (D-114).
    with psycopg.connect(served.conninfo) as conn, pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute(
            "INSERT INTO serving.predictions (request_id, loan_id, pd_version, lgd_version,"
            " api_version, covered, features, request)"
            " SELECT request_id, loan_id, pd_version, lgd_version, api_version, false,"
            " '{}'::jsonb, '{}'::jsonb FROM serving.predictions WHERE loan_id = 61001 LIMIT 1"
        )


# T18.7
def test_with_postgres_down_nothing_is_predicted(served: Served) -> None:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        closed = s.getsockname()[1]
    nowhere = served.conninfo.replace(
        f"port={Settings().postgres_port}", f"port={closed}"
    )  # fmt: skip
    with _client(served, nowhere) as client:
        answer = client.post("/predict", json=loan(62_001), headers=PREDICT)
        assert answer.status_code == 503
        assert "pd" not in answer.json()
        health = client.get("/health").json()
        assert health["database"] is False
        assert health["status"] == "unavailable"
    assert _rows(served, "SELECT count(*) FROM serving.predictions WHERE loan_id = 62001") == [(0,)]


def test_a_batch_that_fails_halfway_stores_nothing(served: Served) -> None:
    from credit_risk.api.store import RequestRow

    holder = Holder(Registry(served.prefix), alert=lambda _: None)
    holder.refresh()
    items = [loan(63_001), loan(63_002), loan(63_003)]
    raw = frame_of(items)
    scored = score(holder.current, clean_listings(raw), raw)
    scored[1] = replace(scored[1], pd=1.5)  # breaks the CHECK of the second insert
    store = Store(served.conninfo, 2)
    store.open()
    row = RequestRow(uuid.uuid4(), "/predict/batch", __version__, loans=3)
    row.versions = holder.current.versions()
    try:
        with pytest.raises(psycopg.errors.CheckViolation):
            store.save(row, scored)
    finally:
        store.close()
    assert _rows(
        served, "SELECT count(*) FROM serving.predictions WHERE loan_id BETWEEN 63001 AND 63003"
    ) == [(0,)]
    assert _rows(
        served, "SELECT count(*) FROM serving.requests WHERE request_id = %s", row.request_id
    ) == [(0,)]


# T18.8
def test_the_champions_come_from_the_mlflow_registry(served: Served) -> None:
    with _client(served) as client:
        health = client.get("/health")
        assert health.status_code == 200, health.text
        assert health.json()["models"] == {"pd": "1", "lgd": "1", "buy_rule": "1"}
    nothing = Served(f"test-api-none-{uuid.uuid4().hex[:8]}-", served.conninfo, served.models)
    with _client(nothing) as client:
        assert client.get("/health").status_code == 503
        assert client.post("/predict", json=loan(64_001), headers=PREDICT).status_code == 503


# T18.11
def test_what_is_stored_with_each_prediction(served: Served) -> None:
    item = loan(65_001, desc="a private story of the borrower")
    with _client(served) as client:
        body = client.post("/predict", json=item, headers=PREDICT).json()
        bad = client.post("/predict", json=loan(65_002, term="x"), headers=PREDICT)
    (row,) = _rows(
        served,
        "SELECT request_id, listed, pd_version, lgd_version, rule_version, api_version,"
        " covered, pd, lgd, ead, expected_loss, el_rate, expected_return, minimum, passes,"
        " base_value, contributions, reasons, features, request"
        " FROM serving.predictions WHERE loan_id = 65001",
    )
    (request_id, listed, pd_v, lgd_v, rule_v, api_v, covered, pd_, lgd, ead, el, el_rate, er,
     minimum, passes, base, contributions, reasons, features, request) = row  # fmt: skip
    assert str(request_id) == body["request_id"]
    assert listed.isoformat() == "2015-03-01"
    assert (pd_v, lgd_v, rule_v, api_v, covered) == ("1", "1", "1", __version__, True)
    assert (pd_, lgd, ead, el, el_rate, er) == tuple(
        body[k] for k in ("pd", "lgd", "ead", "expected_loss", "el_rate", "expected_return")
    )
    assert (minimum, passes) == (0.05, body["threshold"]["passes"])
    assert request == {k: v for k, v in item.items() if v is not None}
    expected = build_features(clean_listings(frame_of([item]))).to_dicts()[0]
    expected.pop("id")
    assert features == expected
    assert sorted(features) == sorted(FEATURES)  # jsonb keeps no key order
    assert sorted(contributions) == sorted(FEATURES)
    assert math.isclose(base + sum(contributions.values()), float(logit(np.array([pd_]))[0]),
                        abs_tol=1e-9)  # fmt: skip
    assert reasons == body["reasons"]

    requests = {
        str(r[0]): r[1:]
        for r in _rows(
            served,
            "SELECT request_id, endpoint, status, latency_ms, client, loans, rejected, body,"
            " errors, pd_version FROM serving.requests WHERE request_id = ANY(%s::uuid[])",
            [body["request_id"], bad.json()["request_id"]],
        )
    }
    ok = requests[body["request_id"]]
    assert ok[:2] == ("/predict", 200)
    assert ok[2] > 0
    assert ok[3:6] == ("replayer", 1, 0)
    assert ok[6] is None
    assert ok[7] is None
    assert ok[8] == "1"
    refused = requests[bad.json()["request_id"]]
    assert refused[:2] == ("/predict", 422)
    assert refused[4:6] == (0, 1)
    assert refused[6]["term"] == "x"
    assert refused[7][0]["column"] == "term"
    everything = str(_rows(served, "SELECT * FROM serving.requests"))
    assert "a private story" not in everything


# T18.13
def test_latency_under_load(served: Served) -> None:
    # The API in a process of its own, as in compose: the clients of this test must not
    # share its interpreter (and its lock) with the server they measure (E-045).
    dbname = served.conninfo.split("dbname=")[1].split()[0]
    with api_process(dbname, served.prefix, API_POOL_SIZE=str(POOL)) as url:
        # Open load (D-122): requests leave at a fixed rate, whatever the answers do, as
        # loans are listed; a pool of clients with their connections sends them.
        latencies: list[float] = []
        failures: list[int] = []
        lock = threading.Lock()
        local = threading.local()
        opened: list[httpx.Client] = []

        def send(n: int) -> None:
            if not hasattr(local, "http"):
                local.http = httpx.Client(base_url=url, trust_env=False, timeout=10)
                with lock:
                    opened.append(local.http)
            started = time.perf_counter()
            answer = local.http.post("/predict", json=loan(1_000_000 + n), headers=PREDICT)
            elapsed = (time.perf_counter() - started) * 1000
            with lock:
                latencies.append(elapsed)
                if answer.status_code != 200:
                    failures.append(answer.status_code)

        total = int(RATE * LOAD_SECONDS)
        with ThreadPoolExecutor(max_workers=POOL) as pool:
            begin = time.perf_counter()
            for n in range(total):
                time.sleep(max(0.0, begin + n / RATE - time.perf_counter()))
                pool.submit(send, n)
        for http_client in opened:
            http_client.close()
        p95 = float(np.percentile(latencies, 95))

        # Capacity, for the record only: clients that never pause, so the API is always
        # busy; the answers per second it reaches (technical.md, D-122).
        done = [0]
        stop = time.monotonic() + CAPACITY_SECONDS

        def busy(k: int) -> None:
            with httpx.Client(base_url=url, trust_env=False, timeout=30) as http:
                n = 0
                while time.monotonic() < stop:
                    n += 1
                    http.post("/predict", json=loan(50_000_000 * (k + 1) + n), headers=PREDICT)
                    with lock:
                        done[0] += 1

        workers = [threading.Thread(target=busy, args=(k,)) for k in range(POOL)]
        for w in workers:
            w.start()
        for w in workers:
            w.join()
        capacity = done[0] / CAPACITY_SECONDS

        with httpx.Client(base_url=url, trust_env=False, timeout=120) as http:
            items = [loan(90_000_000 + i) for i in range(1_000)]
            started = time.perf_counter()
            answer = http.post("/predict/batch", json={"loans": items}, headers=PREDICT)
            batch_seconds = time.perf_counter() - started
        print(
            f"\nT18.13: {len(latencies)} requests at {RATE:.0f} a second for"
            f" {LOAD_SECONDS:.0f} s; p50 {statistics.median(latencies):.1f} ms, p95"
            f" {p95:.1f} ms, max {max(latencies):.1f} ms. Capacity of one process:"
            f" {capacity:.0f} answers a second. Batch of 1,000: {batch_seconds:.2f} s"
        )
        assert len(latencies) == total
        assert not failures, f"{len(failures)} failed requests: {set(failures)}"
        assert p95 < P95_MS
        assert answer.status_code == 200
        assert len(answer.json()["results"]) == 1_000
        assert batch_seconds < 30, "a batch of 1,000 must fit the replayer's timeout"


# T18.14
def test_the_api_runs_in_compose_from_the_serve_image() -> None:
    container = compose("ps", "-q", "api").stdout.strip()
    assert container, "the api service is not running"
    image = docker("image", "inspect", "--format", "{{.Id}}", IMAGES["serve"])
    assert docker("inspect", "--format", "{{.Image}}", container) == image
    health = docker("inspect", "--format", "{{.State.Health.Status}}", container)
    assert health == "healthy"
    port = os.environ.get("API_PORT", "8000")
    with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False, timeout=10) as http:
        assert http.get("/health/live").json()["status"] == "alive"
        ready = http.get("/health")
        assert ready.status_code in (200, 503)
        assert ready.json()["database"] is True
        assert ready.json()["api_version"] == __version__
        assert http.post("/predict", json=loan(1)).status_code == 401
