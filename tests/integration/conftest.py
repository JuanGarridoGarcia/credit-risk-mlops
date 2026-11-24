"""Shared fixtures for the integration tests.

These tests need the services of docker compose and the built image. They never
skip when Docker is missing: a missing service is a failure, not a pass.
Run them with ``make test-integration``, which starts compose and loads ``.env``.
"""

import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest

from credit_risk.settings import Settings

REPO_ROOT = Path(__file__).parents[2]

PgConnection = psycopg.Connection[tuple[object, ...]]


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings()


@pytest.fixture
def pg_connection(settings: Settings) -> Iterator[PgConnection]:
    """A new connection per test, closed afterwards even if the test fails.

    One connection per test (never shared) so that the destructive test, which
    recreates the Postgres container, cannot break the connection of another test.
    """
    with psycopg.connect(settings.postgres_conninfo(), autocommit=True) as conn:
        yield conn


#: The two images of D-078, by target, as ``make build`` tags them.
IMAGES = {
    "serve": os.environ.get("SERVE_IMAGE", "credit-risk:serve"),
    "train": os.environ.get("TRAIN_IMAGE", "credit-risk:train"),
}


@pytest.fixture(scope="session", params=sorted(IMAGES))
def image(request: pytest.FixtureRequest) -> str:
    """Each application image in turn (both built by ``make build``)."""
    return IMAGES[request.param]


def compose(*args: str) -> subprocess.CompletedProcess[str]:
    """Run ``docker compose`` from the repository root and fail loudly on error."""
    return subprocess.run(
        ["docker", "compose", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def docker(*args: str) -> str:
    """Run a ``docker`` command and return its standard output."""
    return subprocess.run(
        ["docker", *args], check=True, capture_output=True, text=True
    ).stdout.strip()


# ---------------------------------------------------------------- step 2.1: ingestion

DBMATE_IMAGE = (
    "amacneil/dbmate:2.38.2@sha256:fb4fe7cabfe98cf864d63ce083867f3c303a8c1a022fcd69081439425706e909"
)


#: Number of schema migrations in the repository.
MIGRATIONS = len(list((REPO_ROOT / "db" / "migrations").glob("*.sql")))


def database_url(settings: Settings, dbname: str) -> str:
    """URL for dbmate, pointing at a given database of the compose Postgres."""
    password = settings.postgres_password.get_secret_value()
    return (
        f"postgres://{settings.postgres_user}:{password}@127.0.0.1:{settings.postgres_port}"
        f"/{dbname}?sslmode=disable"
    )


def dbmate(url: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Run dbmate from its pinned image against ``url`` (passed as an environment variable)."""
    return subprocess.run(
        [
            "docker", "run", "--rm", "--network", "host", "-e", "DATABASE_URL",
            "-v", f"{REPO_ROOT / 'db'}:/db:ro", DBMATE_IMAGE,
            "--migrations-dir", "/db/migrations", "--no-dump-schema", *args,
        ],
        env={**os.environ, "DATABASE_URL": url},
        check=True,
        capture_output=True,
        text=True,
    )  # fmt: skip


@pytest.fixture
def empty_database(settings: Settings) -> Iterator[str]:
    """A brand-new database, dropped afterwards; yields its name."""
    name = f"test_{os.urandom(4).hex()}"
    with psycopg.connect(settings.postgres_conninfo(), autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{name}"')
    try:
        yield name
    finally:
        with psycopg.connect(settings.postgres_conninfo(), autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


@pytest.fixture(scope="session")
def migrated_database(settings: Settings) -> Iterator[str]:
    """One database with every migration applied, shared by the ingestion tests."""
    name = f"test_ingest_{os.urandom(4).hex()}"
    with psycopg.connect(settings.postgres_conninfo(), autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{name}"')
    try:
        dbmate(database_url(settings, name), "up")
        yield name
    finally:
        with psycopg.connect(settings.postgres_conninfo(), autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


@pytest.fixture
def db(settings: Settings, migrated_database: str) -> Iterator[PgConnection]:
    """An autocommit connection to the migrated database, emptied before each test."""
    conninfo = settings.postgres_conninfo().replace(
        f"dbname={settings.postgres_db}", f"dbname={migrated_database}"
    )
    with psycopg.connect(conninfo, autocommit=True) as conn:
        conn.execute(
            "TRUNCATE raw.listings, raw.outcomes, clean.listings, clean.outcomes, "
            "ops.validation_warnings, ops.column_profile, ops.training_set_loads, "
            "ops.training_sets, ops.ingest_log RESTART IDENTITY"
        )
        yield conn
