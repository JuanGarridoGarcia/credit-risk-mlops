"""T3.13: loading every real delivery into Postgres reproduces the audit's counts.

Needs the deliveries in ``data/landing`` (``make publish PERIOD=2019-03``) and the
compose Postgres (``make up``). Also measures COPY against row-by-row INSERT (D-047).
"""

import time
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import psycopg
import pytest

from credit_risk.contracts import LISTING_COLUMNS
from credit_risk.ingest import ingest, read_delivery
from credit_risk.settings import Settings
from tests.integration.conftest import database_url, dbmate

ROOT = Path(__file__).resolve().parents[2]
LANDING = ROOT / "data" / "landing"

pytestmark = pytest.mark.data


@pytest.fixture(scope="module")
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


def _count(conn: psycopg.Connection[tuple[object, ...]], table: str) -> int:
    row = conn.execute(f"SELECT count(*) FROM {table}").fetchone()  # noqa: S608
    assert row is not None
    return int(str(row[0]))


def test_every_delivery_loads_with_the_audit_counts(
    conn: psycopg.Connection[tuple[object, ...]],
) -> None:
    periods = sorted(date.fromisoformat(f"{p.name}-01") for p in LANDING.iterdir())
    assert len(periods) == 142
    start = time.perf_counter()
    for period in periods:
        ingest(conn, LANDING, period)
    elapsed = time.perf_counter() - start
    print(f"\nfull load of {len(periods)} months: {elapsed:.0f} s")
    assert _count(conn, "raw.listings") == 2_260_668
    assert _count(conn, "clean.listings") == 2_260_668
    assert _count(conn, "raw.outcomes") == 1_348_099
    assert _count(conn, "clean.outcomes") == 1_348_099
    failed = _count(conn, "ops.ingest_log WHERE status = 'failed'")
    assert failed == 0


def test_copy_is_faster_than_row_by_row_insert(
    conn: psycopg.Connection[tuple[object, ...]],
) -> None:
    """Measure, on the largest month, what D-047 promised (recorded in technical.md)."""
    frame = read_delivery(LANDING / "2016-03" / "listings.csv.gz", "listings").head(10_000)
    rows = frame.rows()
    cols = ", ".join(f'"{c}"' for c in LISTING_COLUMNS)
    marks = ", ".join(["%s"] * len(LISTING_COLUMNS))
    conn.execute(f"CREATE TEMP TABLE bench AS SELECT {cols} FROM raw.listings LIMIT 0")  # noqa: S608
    start = time.perf_counter()
    with conn.transaction(), conn.cursor() as cur:
        for row in rows:
            cur.execute(f"INSERT INTO bench ({cols}) VALUES ({marks})", row)  # noqa: S608
    insert_s = time.perf_counter() - start
    conn.execute("TRUNCATE bench")
    start = time.perf_counter()
    with (
        conn.transaction(),
        conn.cursor() as cur,
        cur.copy(f"COPY bench ({cols}) FROM STDIN") as copy,
    ):
        for row in rows:
            copy.write_row(row)
    copy_s = time.perf_counter() - start
    print(f"\n10,000 rows: INSERT {insert_s:.2f} s, COPY {copy_s:.2f} s")
    assert copy_s < insert_s
