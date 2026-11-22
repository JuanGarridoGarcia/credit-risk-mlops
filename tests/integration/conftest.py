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


@pytest.fixture(scope="session")
def image() -> str:
    """Name of the application image under test (built by ``make build``)."""
    return os.environ.get("IMAGE", "credit-risk:dev")


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
