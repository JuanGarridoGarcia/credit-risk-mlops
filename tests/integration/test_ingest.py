"""Tests T3 of loading into Postgres, approved by Juan on 2026-11-23 (technical.md, 2.1)."""

import gzip
import io
from datetime import date
from pathlib import Path
from typing import Any

import polars as pl
import psycopg
import pytest

from credit_risk.cleaning import clean_listings, clean_outcomes
from credit_risk.contracts import LISTING_COLUMNS, OUTCOME_COLUMNS, delivery_path
from credit_risk.ingest import DeliveryError, build_clean, delete_period, ingest, load_raw
from credit_risk.settings import Settings

from .conftest import PgConnection, database_url, dbmate

pytestmark = pytest.mark.integration

MARCH = date(2015, 3, 1)
APRIL = date(2015, 4, 1)
TRICKY_DESC = 'Line one, with a comma\nline two "quoted" <br/>'
INJECTION = "x'); DROP TABLE raw.listings; --"


def _listing(id_: int, **values: str | None) -> dict[str, str | None]:
    row: dict[str, str | None] = dict.fromkeys(LISTING_COLUMNS)
    defaults = {
        "loan_amnt": "10000.0",
        "term": " 36 months",
        "emp_length": "10+ years",
        "issue_d": "Mar-2015",
        "dti": "12.5",
    }
    row.update({"id": str(id_), **defaults, **values})
    return row


def _outcome(id_: int, **values: str | None) -> dict[str, str | None]:
    row: dict[str, str | None] = dict.fromkeys(OUTCOME_COLUMNS)
    defaults = {
        "funded_amnt": "10000.0",
        "loan_status": "Fully Paid",
        "pymnt_plan": "n",
        "hardship_flag": "N",
        "debt_settlement_flag": "N",
        "last_pymnt_d": "Mar-2015",
    }
    row.update({"id": str(id_), **defaults, **values})
    return row


def _write(landing: Path, period: date, stream: str, rows: list[dict[str, Any]]) -> Path:
    columns = LISTING_COLUMNS if stream == "listings" else OUTCOME_COLUMNS
    frame = pl.DataFrame(rows, schema=dict.fromkeys(columns, pl.String))
    path = delivery_path(landing, period, stream)
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    frame.write_csv(buffer)
    path.write_bytes(gzip.compress(buffer.getvalue(), mtime=0))
    return path


def _month(landing: Path, period: date, ids: list[int], **listing: str | None) -> None:
    _write(landing, period, "listings", [_listing(i, **listing) for i in ids])
    _write(landing, period, "outcomes", [_outcome(i) for i in ids[:1]])


def _one(conn: PgConnection, query: str, *params: object) -> Any:
    row = conn.execute(query, params).fetchone()
    assert row is not None
    return row[0]


def _ids(conn: PgConnection, table: str, period: date) -> list[str]:
    rows = conn.execute(
        f"SELECT id::text FROM {table} WHERE period = %s ORDER BY id::bigint",  # noqa: S608
        (period,),
    ).fetchall()
    return [str(r[0]) for r in rows]


def _log(conn: PgConnection) -> list[tuple[Any, ...]]:
    return conn.execute(
        "SELECT stream, layer, period, status, rows_in_file, rows_loaded, error "
        "FROM ops.ingest_log ORDER BY load_id"
    ).fetchall()


# T3.1
def test_migrations_apply_roll_back_and_apply_again(
    settings: Settings, empty_database: str
) -> None:
    url = database_url(settings, empty_database)
    dbmate(url, "up")
    for _ in range(3):
        dbmate(url, "rollback")
    conninfo = settings.postgres_conninfo().replace(
        f"dbname={settings.postgres_db}", f"dbname={empty_database}"
    )
    with psycopg.connect(conninfo, autocommit=True) as conn:
        left = conn.execute(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name IN ('raw', 'clean', 'ops')"
        ).fetchall()
        assert left == []
    dbmate(url, "up")
    status = dbmate(url, "status").stdout
    assert "Applied: 3" in status
    assert "Pending: 0" in status


# T3.2
def test_a_load_writes_every_row_and_logs_it(db: PgConnection, tmp_path: Path) -> None:
    _month(tmp_path, MARCH, [1, 2, 3])
    result = load_raw(db, tmp_path, MARCH, "listings")
    assert (result.status, result.rows) == ("loaded", 3)
    assert _ids(db, "raw.listings", MARCH) == ["1", "2", "3"]
    stream, layer, period, status, in_file, loaded, error = _log(db)[0]
    assert (stream, layer, period, status, in_file, loaded, error) == (
        "listings", "raw", MARCH, "loaded", 3, 3, None,
    )  # fmt: skip
    sha = _one(db, "SELECT file_sha256 FROM ops.ingest_log WHERE load_id = 1")
    assert len(sha) == 64


# T3.3
def test_the_same_file_twice_changes_nothing(db: PgConnection, tmp_path: Path) -> None:
    _month(tmp_path, MARCH, [1, 2, 3])
    ingest(db, tmp_path, MARCH)
    again = ingest(db, tmp_path, MARCH)
    assert {r.status for results in again.values() for r in results} == {"unchanged"}
    assert _one(db, "SELECT count(*) FROM raw.listings") == 3
    assert _one(db, "SELECT count(*) FROM clean.listings") == 3


# T3.4
def test_a_corrected_delivery_replaces_the_month_with_no_ghost(
    db: PgConnection, tmp_path: Path
) -> None:
    _month(tmp_path, MARCH, [1, 2, 3])
    ingest(db, tmp_path, MARCH)
    rows = [_listing(1, dti="20.0"), _listing(3)]  # loan 2 removed, loan 1 corrected
    _write(tmp_path, MARCH, "listings", rows)
    result = load_raw(db, tmp_path, MARCH, "listings")
    assert result.status == "replaced"
    assert _ids(db, "raw.listings", MARCH) == ["1", "3"]
    assert _one(db, "SELECT dti FROM raw.listings WHERE id = '1'") == "20.0"
    build_clean(db, MARCH, "listings")
    assert _ids(db, "clean.listings", MARCH) == ["1", "3"]
    assert _one(db, "SELECT dti FROM clean.listings WHERE id = 1") == 20.0


# T3.5
def test_a_failed_load_leaves_the_month_as_it_was(db: PgConnection, tmp_path: Path) -> None:
    _month(tmp_path, MARCH, [1, 2, 3])
    ingest(db, tmp_path, MARCH)
    path = delivery_path(tmp_path, MARCH, "listings")
    text = gzip.decompress(path.read_bytes()).decode()
    broken = text + "4,this row has too few fields\n"  # good rows first, the broken one last
    path.write_bytes(gzip.compress(broken.encode(), mtime=0))
    with pytest.raises(DeliveryError, match="record 5 has 2 fields"):
        load_raw(db, tmp_path, MARCH, "listings")
    assert _ids(db, "raw.listings", MARCH) == ["1", "2", "3"]
    last = _log(db)[-1]
    assert last[3] == "failed"
    assert last[6]


def test_a_failure_inside_postgres_rolls_back_the_delete(db: PgConnection, tmp_path: Path) -> None:
    _month(tmp_path, MARCH, [1, 2, 3])
    ingest(db, tmp_path, MARCH)
    # Loan 9 is already in April: the primary key rejects it during COPY, after the DELETE.
    _month(tmp_path, APRIL, [9])
    ingest(db, tmp_path, APRIL)
    _write(tmp_path, MARCH, "listings", [_listing(1), _listing(2), _listing(9)])
    with pytest.raises(psycopg.errors.UniqueViolation):
        load_raw(db, tmp_path, MARCH, "listings")
    assert _ids(db, "raw.listings", MARCH) == ["1", "2", "3"]
    assert _log(db)[-1][3] == "failed"


# T3.6
def test_deleting_a_month_leaves_the_others(db: PgConnection, tmp_path: Path) -> None:
    _month(tmp_path, MARCH, [1, 2])
    _month(tmp_path, APRIL, [3, 4])
    ingest(db, tmp_path, MARCH)
    ingest(db, tmp_path, APRIL)
    delete_period(db, MARCH)
    for table in ("raw.listings", "clean.listings", "raw.outcomes", "clean.outcomes"):
        assert _ids(db, table, MARCH) == []
    assert _ids(db, "raw.listings", APRIL) == ["3", "4"]
    assert _ids(db, "clean.listings", APRIL) == ["3", "4"]
    assert _ids(db, "clean.outcomes", APRIL) == ["3"]
    reloaded = load_raw(db, tmp_path, MARCH, "listings")
    assert reloaded.status == "loaded"


# T3.7
def test_text_survives_postgres(db: PgConnection, tmp_path: Path) -> None:
    _month(tmp_path, MARCH, [1], desc=TRICKY_DESC, emp_title="  Nurse ")
    load_raw(db, tmp_path, MARCH, "listings")
    desc, title, term = db.execute(
        'SELECT "desc", emp_title, term FROM raw.listings WHERE id = %s', ("1",)
    ).fetchone() or (None, None, None)
    assert (desc, title, term) == (TRICKY_DESC, "  Nurse ", " 36 months")


# T3.8
def test_sql_injection_is_stored_as_text(db: PgConnection, tmp_path: Path) -> None:
    _month(tmp_path, MARCH, [1], emp_title=INJECTION)
    ingest(db, tmp_path, MARCH)
    assert _one(db, "SELECT emp_title FROM clean.listings WHERE id = 1") == INJECTION
    assert _one(db, "SELECT count(*) FROM raw.listings") == 1


def _clean_from_db(conn: PgConnection, table: str, columns: tuple[str, ...]) -> pl.DataFrame:
    cols = ", ".join(f'"{c}"' for c in columns)
    with conn.cursor() as cur:
        cur.execute(f"SELECT {cols} FROM {table} ORDER BY id")  # noqa: S608
        rows = cur.fetchall()
    return pl.DataFrame(rows, schema=list(columns), orient="row", infer_schema_length=None)


def _types(conn: PgConnection, table: str) -> dict[str, str]:
    rows = conn.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'clean' AND table_name = %s",
        (table,),
    ).fetchall()
    return {str(name): str(kind) for name, kind in rows}


# T3.9
def test_clean_holds_exactly_the_cleaned_delivery_with_postgres_types(
    db: PgConnection, tmp_path: Path
) -> None:
    rows = [
        _listing(1, desc=TRICKY_DESC, earliest_cr_line="Sep-1980", int_rate="13.56"),
        _listing(2, emp_length=None, dti="999.0", installment="321.987654321"),
        _listing(3, term=" 60 months", emp_length="< 1 year", revol_util="0.0"),
    ]
    _write(tmp_path, MARCH, "listings", rows)
    _write(tmp_path, MARCH, "outcomes", [_outcome(1, hardship_flag="Y", total_pymnt="1.1")])
    ingest(db, tmp_path, MARCH)
    for stream, columns, cleaner in (
        ("listings", LISTING_COLUMNS, clean_listings),
        ("outcomes", OUTCOME_COLUMNS, clean_outcomes),
    ):
        expected = cleaner(pl.read_csv(delivery_path(tmp_path, MARCH, stream), infer_schema=False))
        got = _clean_from_db(db, f"clean.{stream}", columns)
        assert got.to_dicts() == expected.to_dicts()
    types = _types(db, "listings")
    assert types["loan_amnt"] == "double precision"
    assert types["issue_d"] == "date"
    assert types["term"] == "smallint"
    assert types["id"] == "bigint"
    out_types = _types(db, "outcomes")
    assert out_types["hardship_flag"] == "boolean"


# T3.10
def test_clean_is_rebuilt_from_raw_without_the_delivery(db: PgConnection, tmp_path: Path) -> None:
    _month(tmp_path, MARCH, [1, 2, 3], desc=TRICKY_DESC)
    ingest(db, tmp_path, MARCH)
    before = _clean_from_db(db, "clean.listings", LISTING_COLUMNS)
    delivery_path(tmp_path, MARCH, "listings").unlink()
    db.execute("DELETE FROM clean.listings")
    db.execute("DELETE FROM ops.ingest_log WHERE layer = 'clean' AND stream = 'listings'")
    result = build_clean(db, MARCH, "listings")
    assert result.status == "loaded"
    assert _clean_from_db(db, "clean.listings", LISTING_COLUMNS).equals(before)


# T3.11
def test_a_missing_delivery_names_the_expected_file(db: PgConnection, tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match=r"2015-03/listings\.csv\.gz"):
        load_raw(db, tmp_path, MARCH, "listings")


# T3.12
def test_a_loan_in_two_months_is_rejected_by_the_primary_key(
    db: PgConnection, tmp_path: Path
) -> None:
    _month(tmp_path, MARCH, [1, 2])
    _month(tmp_path, APRIL, [2, 3])
    ingest(db, tmp_path, MARCH)
    with pytest.raises(psycopg.errors.UniqueViolation):
        load_raw(db, tmp_path, APRIL, "listings")
    assert _ids(db, "raw.listings", APRIL) == []


def test_ingestion_refuses_a_connection_without_autocommit(
    settings: Settings, migrated_database: str, tmp_path: Path
) -> None:
    conninfo = settings.postgres_conninfo().replace(
        f"dbname={settings.postgres_db}", f"dbname={migrated_database}"
    )
    with (
        psycopg.connect(conninfo) as conn,
        pytest.raises(ValueError, match="autocommit"),
    ):
        load_raw(conn, tmp_path, MARCH, "listings")
