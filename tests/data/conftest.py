"""Shared fixtures of the data tests: each real load is done once per session.

Needs the deliveries in ``data/landing`` (``make publish PERIOD=2019-03``) and the
compose Postgres (``make up``).
"""

import time
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import psycopg
import pytest

from credit_risk.ingest import ingest
from credit_risk.settings import Settings
from credit_risk.snapshot import Manifest, build
from credit_risk.storage import LocalStore
from tests.integration.conftest import database_url, dbmate

ROOT = Path(__file__).resolve().parents[2]
LANDING = ROOT / "data" / "landing"
T0 = date(2014, 1, 1)

Connection = psycopg.Connection[tuple[object, ...]]


@pytest.fixture(scope="session")
def conn() -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    settings = Settings()
    name = "test_full_load"
    with psycopg.connect(settings.postgres_conninfo(), autocommit=True) as admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        admin.execute(f'CREATE DATABASE "{name}"')
    dbmate(database_url(settings, name), "up")
    conninfo = settings.postgres_conninfo().replace(
        f"dbname={settings.postgres_db}", f"dbname={name}"
    )
    try:
        with psycopg.connect(conninfo, autocommit=True) as connection:
            yield connection
    finally:
        with psycopg.connect(settings.postgres_conninfo(), autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


@pytest.fixture(scope="session")
def full_load(
    conn: psycopg.Connection[tuple[object, ...]], tmp_path_factory: pytest.TempPathFactory
) -> Path:
    """Load every delivery in month order; return the folder of the validation reports."""
    reports = tmp_path_factory.mktemp("validation")
    periods = sorted(date.fromisoformat(f"{p.name}-01") for p in LANDING.iterdir())
    assert len(periods) == 142
    start = time.perf_counter()
    for period in periods:
        ingest(conn, LANDING, period, reports=reports)
    print(
        f"\nfull load of {len(periods)} months with validation: {time.perf_counter() - start:.0f} s"
    )
    return reports


# ---------------------------------------------------------------- the first training set


@pytest.fixture(scope="session")
def t0_conn() -> Iterator[Connection]:
    """A database of its own for the months up to T0 (shared by the snapshot and the
    training data tests, so the load is done once)."""
    settings = Settings()
    name = "test_first_snapshot"
    with psycopg.connect(settings.postgres_conninfo(), autocommit=True) as admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        admin.execute(f'CREATE DATABASE "{name}"')
    dbmate(database_url(settings, name), "up")
    conninfo = settings.postgres_conninfo().replace(
        f"dbname={settings.postgres_db}", f"dbname={name}"
    )
    try:
        with psycopg.connect(conninfo, autocommit=True) as connection:
            yield connection
    finally:
        with psycopg.connect(settings.postgres_conninfo(), autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


@pytest.fixture(scope="session")
def t0_store(tmp_path_factory: pytest.TempPathFactory) -> LocalStore:
    return LocalStore(tmp_path_factory.mktemp("training_sets"))


@pytest.fixture(scope="session")
def first(
    t0_conn: Connection, t0_store: LocalStore, tmp_path_factory: pytest.TempPathFactory
) -> Manifest:
    """The first training set version, at T0 = 2014-01 (D-041)."""
    reports = tmp_path_factory.mktemp("validation")
    periods = sorted(
        p for p in (date.fromisoformat(f"{d.name}-01") for d in LANDING.iterdir()) if p <= T0
    )
    assert len(periods) == 80
    start = time.perf_counter()
    for period in periods:
        ingest(t0_conn, LANDING, period, reports=reports)
    loaded = time.perf_counter() - start
    start = time.perf_counter()
    manifest = build(t0_conn, T0, t0_store, commit="data-test")
    print(f"\nload up to {T0:%Y-%m}: {loaded:.0f} s; build: {time.perf_counter() - start:.1f} s")
    return manifest
