"""T3.13, T3.15 and T4.15: loading every real delivery into Postgres, with validation.

Needs the deliveries in ``data/landing`` (``make publish PERIOD=2019-03``) and the
compose Postgres (``make up``). T3.13 reproduces the audit's counts; T4.15 checks that
no critical rule fails and that warnings fire exactly where docs/validation_rules.md
says. Also measures COPY against row-by-row INSERT (D-047).
"""

import json
import time
from pathlib import Path

import psycopg
import pytest

from credit_risk.contracts import LISTING_COLUMNS
from credit_risk.ingest import read_delivery

ROOT = Path(__file__).resolve().parents[2]
LANDING = ROOT / "data" / "landing"

pytestmark = pytest.mark.data


def _count(conn: psycopg.Connection[tuple[object, ...]], table: str) -> int:
    row = conn.execute(f"SELECT count(*) FROM {table}").fetchone()  # noqa: S608
    assert row is not None
    return int(str(row[0]))


# T3.13
def test_every_delivery_loads_with_the_audit_counts(
    conn: psycopg.Connection[tuple[object, ...]], full_load: Path
) -> None:
    assert _count(conn, "raw.listings") == 2_260_668
    assert _count(conn, "clean.listings") == 2_260_668
    assert _count(conn, "raw.outcomes") == 1_348_099
    assert _count(conn, "clean.outcomes") == 1_348_099
    failed = _count(conn, "ops.ingest_log WHERE status = 'failed'")
    assert failed == 0


def _months(
    conn: psycopg.Connection[tuple[object, ...]], rule: str, since: str = "2007-01"
) -> set[str]:
    rows = conn.execute(
        "SELECT DISTINCT to_char(period, 'YYYY-MM') FROM ops.validation_warnings "
        "WHERE rule = %s AND to_char(period, 'YYYY-MM') BETWEEN %s AND '2018-12'",
        (rule, since),
    ).fetchall()
    return {str(r[0]) for r in rows}


def _rows(conn: psycopg.Connection[tuple[object, ...]], rule: str) -> int:
    row = conn.execute(
        "SELECT coalesce(sum(rows_affected), 0) FROM ops.validation_warnings WHERE rule = %s",
        (rule,),
    ).fetchone()
    assert row is not None
    return int(str(row[0]))


# T4.15
def test_the_real_file_passes_and_warns_where_the_catalogue_says(
    conn: psycopg.Connection[tuple[object, ...]], full_load: Path
) -> None:
    findings = [
        f
        for path in sorted(full_load.glob("*/*.json"))
        for f in json.loads(path.read_text())["findings"]
    ]
    assert [f for f in findings if f["level"] == "critical"] == []
    exceptions = {
        (f["rule"], e[0]) for f in findings if f["level"] == "exception" for e in f["examples"]
    }
    assert exceptions == {
        ("R3.5", 124624),
        ("R3.5", 127213),
        ("R4.2", 63407533),
        ("R4.2", 69266577),
        ("R4.1", 96387212),
    }
    rules = conn.execute("SELECT DISTINCT rule FROM ops.validation_warnings").fetchall()
    assert {str(r[0]) for r in rules} == {
        "R2.10", "R2.11", "R2.12", "R2.13", "R3.14", "R3.15", "R4.6", "R5.2",
    }  # fmt: skip
    assert _rows(conn, "R2.10") == 2 + 2_561
    assert _rows(conn, "R2.11") == 3
    assert _rows(conn, "R2.12") == 3 + 17
    assert _rows(conn, "R3.14") == 4
    assert _rows(conn, "R3.15") == 433
    assert _months(conn, "R2.13", "2014-01") == {"2015-05", "2016-04", "2016-05"}
    assert _months(conn, "R4.6", "2014-01") == {"2014-03", "2014-04", "2015-12", "2016-01"}
    assert _months(conn, "R5.2") == {"2012-08", "2012-09", "2012-10", "2014-10"}


# T3.15
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
