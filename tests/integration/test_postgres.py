"""B3: our code connects to the Postgres started by docker compose."""

import pytest

from tests.integration.conftest import PgConnection

pytestmark = pytest.mark.integration


# B3
def test_postgres_accepts_connection(pg_connection: PgConnection) -> None:
    result = pg_connection.execute("SELECT 1").fetchone()

    assert result == (1,)


def test_postgres_major_version_is_18(pg_connection: PgConnection) -> None:
    # Same major version as AWS RDS in production (decision A9). server_version: 180007 = 18.7.
    version = pg_connection.info.server_version

    assert version // 10_000 == 18
