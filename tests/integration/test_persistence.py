"""B4: data survives destroying and recreating the Postgres container.

`docker compose restart` would keep the same container (and its writable layer),
so it would pass even with a wrong volume. `down` + `up` creates a new container:
if the row is still there, it can only come from the volume. `down -v` (which
deletes the volume) is never used here.
"""

import uuid
from collections.abc import Iterator

import psycopg
import pytest
from psycopg import sql

from credit_risk.settings import Settings
from tests.integration.conftest import compose

pytestmark = [pytest.mark.integration, pytest.mark.destructive]


@pytest.fixture
def table_name(settings: Settings) -> Iterator[str]:
    """A table name never used before; the table is dropped afterwards, pass or fail."""
    name = f"test_persistence_{uuid.uuid4().hex}"
    yield name
    with psycopg.connect(settings.postgres_conninfo(), autocommit=True) as conn:
        conn.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(name)))


def test_postgres_data_survives_container_recreation(settings: Settings, table_name: str) -> None:
    value = uuid.uuid4().hex
    table = sql.Identifier(table_name)
    with psycopg.connect(settings.postgres_conninfo(), autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE TABLE {} (value text NOT NULL)").format(table))
        conn.execute(sql.SQL("INSERT INTO {} (value) VALUES (%s)").format(table), (value,))
        old_container = compose("ps", "-q", "postgres").stdout.strip()

    compose("down")
    compose("up", "-d", "--wait", "postgres")

    new_container = compose("ps", "-q", "postgres").stdout.strip()
    assert new_container != old_container, "the container was not recreated"
    with psycopg.connect(settings.postgres_conninfo(), autocommit=True) as conn:
        rows = conn.execute(sql.SQL("SELECT value FROM {}").format(table)).fetchall()
    assert rows == [(value,)]
