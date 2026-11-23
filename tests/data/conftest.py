"""Shared fixtures of the data tests: the full real load is done once per session.

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
from tests.integration.conftest import database_url, dbmate

ROOT = Path(__file__).resolve().parents[2]
LANDING = ROOT / "data" / "landing"


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
