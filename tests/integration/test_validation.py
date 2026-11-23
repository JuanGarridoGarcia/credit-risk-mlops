"""Tests T4.10 to T4.14 of validation in Postgres, approved by Juan on 2026-11-23.

The rules that need other months run in SQL inside the load transaction; the month is
the unit (D-055). Catalogue: docs/validation_rules.md.
"""

import gzip
import io
import json
from datetime import date
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from credit_risk.contracts import LISTING_COLUMNS, OUTCOME_COLUMNS, delivery_path
from credit_risk.ingest import ingest
from credit_risk.validation.report import ValidationFailed
from tests import valid_rows
from tests.valid_rows import Row

from .conftest import PgConnection

pytestmark = pytest.mark.integration

FEB = date(2015, 2, 1)
MARCH = date(2015, 3, 1)


def _write(landing: Path, period: date, stream: str, rows: list[Row]) -> None:
    columns = LISTING_COLUMNS if stream == "listings" else OUTCOME_COLUMNS
    frame = pl.DataFrame(rows, schema=dict.fromkeys(columns, pl.String))
    path = delivery_path(landing, period, stream)
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    frame.write_csv(buffer)
    path.write_bytes(gzip.compress(buffer.getvalue(), mtime=0))


def _deliver(
    landing: Path, period: date, listings: list[Row], outcomes: list[Row] | None = None
) -> None:
    _write(landing, period, "listings", listings)
    _write(landing, period, "outcomes", outcomes or [])


def _l(id_: int, period: date = MARCH, /, **values: str | None) -> Row:
    return valid_rows.listing(id_, period, **values)


def _o(id_: int, period: date = MARCH, /, **values: str | None) -> Row:
    return valid_rows.outcome(id_, period, **values)


def _one(conn: PgConnection, query: str, *params: object) -> Any:
    row = conn.execute(query, params).fetchone()
    assert row is not None
    return row[0]


def _fails(conn: PgConnection, landing: Path, period: date) -> set[str]:
    with pytest.raises(ValidationFailed) as info:
        ingest(conn, landing, period)
    return set(info.value.report.failed_rules())


def _warnings(conn: PgConnection, period: date) -> set[str]:
    rows = conn.execute(
        "SELECT rule FROM ops.validation_warnings WHERE period = %s", (period,)
    ).fetchall()
    return {str(r[0]) for r in rows}


def _seed_volume(conn: PgConnection, period: date, rows: int, stream: str = "listings") -> None:
    """Record 12 previous clean months of ``rows`` rows each in the load log (R5)."""
    for back in range(1, 13):
        month = date(
            period.year - (period.month - back <= 0), (period.month - back - 1) % 12 + 1, 1
        )
        conn.execute(
            "INSERT INTO ops.ingest_log (stream, layer, period, status, rows_in_file, rows_loaded) "
            "VALUES (%s, 'clean', %s, 'loaded', %s, %s)",
            (stream, month, rows, rows),
        )


@pytest.fixture
def landing(tmp_path: Path) -> Path:
    """The landing folder of a test; its reports go to ``validation`` next to it."""
    return tmp_path / "landing"


# T4.10: one failing case per SQL rule.
def test_r1_3_a_loan_already_in_another_month(db: PgConnection, landing: Path) -> None:
    load = _one(
        db,
        "INSERT INTO ops.ingest_log (stream, layer, period, status, rows_in_file, rows_loaded) "
        "VALUES ('listings', 'clean', %s, 'loaded', 1, 1) RETURNING load_id",
        FEB,
    )
    db.execute("INSERT INTO clean.listings (period, load_id, id) VALUES (%s, %s, 1)", (FEB, load))
    _deliver(landing, MARCH, [_l(1)])
    assert _fails(db, landing, MARCH) == {"R1.3"}


def test_r1_5_an_outcome_in_the_wrong_month(db: PgConnection, landing: Path) -> None:
    _deliver(landing, FEB, [_l(1, FEB)])
    ingest(db, landing, FEB)
    _deliver(landing, MARCH, [_l(2)], [_o(1, last_pymnt_d="Feb-2015")])
    assert _fails(db, landing, MARCH) == {"R1.5"}


def test_r1_6_an_outcome_without_its_listing(db: PgConnection, landing: Path) -> None:
    _deliver(landing, MARCH, [_l(1)], [_o(7)])
    assert _fails(db, landing, MARCH) == {"R1.6"}


def test_r3_11_funded_above_the_request(db: PgConnection, landing: Path) -> None:
    funded = {"funded_amnt": "20000.0", "funded_amnt_inv": "20000.0", "total_rec_prncp": "20000.0"}
    _deliver(landing, MARCH, [_l(1)], [_o(1, total_pymnt="20500.0", **funded)])
    assert _fails(db, landing, MARCH) == {"R3.11"}


def test_r3_12_a_payment_before_the_loan(db: PgConnection, landing: Path) -> None:
    charged_off = {"loan_status": "Charged Off", "last_pymnt_d": "Oct-2014"}
    _deliver(landing, MARCH, [_l(1)], [_o(1, **charged_off)])
    assert _fails(db, landing, MARCH) == {"R3.12"}


def test_r2_13_a_rate_above_every_rate_seen(db: PgConnection, landing: Path) -> None:
    _deliver(landing, FEB, [_l(1, FEB)])
    ingest(db, landing, FEB)
    _deliver(landing, MARCH, [_l(2, int_rate="12.0", installment="332.14")])
    ingest(db, landing, MARCH)
    assert _warnings(db, MARCH) == {"R2.13"}


def test_r3_15_an_instalment_off_the_formula(db: PgConnection, landing: Path) -> None:
    _deliver(landing, MARCH, [_l(1, installment="400.0")], [_o(1)])
    ingest(db, landing, MARCH)
    assert _warnings(db, MARCH) == {"R3.15"}


def test_r4_6_a_jump_in_missing_values(db: PgConnection, landing: Path) -> None:
    _deliver(landing, FEB, [_l(1, FEB)])
    ingest(db, landing, FEB)
    _deliver(landing, MARCH, [_l(2, desc="Paying off cards")])
    ingest(db, landing, MARCH)
    found = db.execute(
        "SELECT rule, column_name FROM ops.validation_warnings WHERE period = %s", (MARCH,)
    ).fetchall()
    assert found == [("R4.6", "desc")]


def test_r5_1_a_month_far_below_its_median(db: PgConnection, landing: Path) -> None:
    _seed_volume(db, MARCH, 1000)
    _deliver(landing, MARCH, [_l(i) for i in range(1, 51)])
    assert _fails(db, landing, MARCH) == {"R5.1"}


def test_r5_2_a_month_well_below_its_median(db: PgConnection, landing: Path) -> None:
    _seed_volume(db, MARCH, 1000)
    _deliver(landing, MARCH, [_l(i) for i in range(1, 301)])
    ingest(db, landing, MARCH)
    assert _warnings(db, MARCH) == {"R5.2"}


def test_r5_3_no_volume_rule_below_a_median_of_1000(db: PgConnection, landing: Path) -> None:
    _seed_volume(db, MARCH, 999)
    _deliver(landing, MARCH, [_l(1)])
    ingest(db, landing, MARCH)
    assert _warnings(db, MARCH) == set()


# T4.11
def test_a_critical_failure_stops_the_whole_month(db: PgConnection, landing: Path) -> None:
    _deliver(landing, MARCH, [_l(1), _l(2)], [_o(1)])
    ingest(db, landing, MARCH)
    before = db.execute("SELECT id, load_id FROM clean.listings ORDER BY id").fetchall()
    # A new delivery: one listing more, and an outcome with an unknown status.
    _deliver(landing, MARCH, [_l(1), _l(2), _l(3)], [_o(1, loan_status="Current")])
    assert _fails(db, landing, MARCH) == {"R2.1"}
    assert db.execute("SELECT id, load_id FROM clean.listings ORDER BY id").fetchall() == before
    assert _one(db, "SELECT count(*) FROM clean.outcomes") == 1
    assert _one(db, "SELECT count(*) FROM raw.listings") == 3
    failed = db.execute(
        "SELECT stream, error FROM ops.ingest_log WHERE status = 'failed' ORDER BY stream"
    ).fetchall()
    assert [s for s, _ in failed] == ["listings", "outcomes"]
    assert all("R2.1" in str(e) for _, e in failed)


def test_a_new_month_that_fails_leaves_nothing_in_clean(db: PgConnection, landing: Path) -> None:
    _deliver(landing, MARCH, [_l(1, grade="H", sub_grade="H1")], [_o(1)])
    assert _fails(db, landing, MARCH) == {"R2.1"}
    assert _one(db, "SELECT count(*) FROM clean.listings") == 0
    assert _one(db, "SELECT count(*) FROM clean.outcomes") == 0


def test_a_failing_sql_rule_rolls_back_the_month(db: PgConnection, landing: Path) -> None:
    _deliver(landing, MARCH, [_l(1)], [_o(7)])
    assert _fails(db, landing, MARCH) == {"R1.6"}
    assert _one(db, "SELECT count(*) FROM clean.listings") == 0
    assert _one(db, "SELECT count(*) FROM ops.column_profile") == 0


# T4.12
def test_warnings_are_stored_once_per_month(db: PgConnection, landing: Path) -> None:
    _deliver(landing, MARCH, [_l(1, dti="150.0"), _l(2)])
    ingest(db, landing, MARCH)
    ingest(db, landing, MARCH)  # same files: unchanged
    _deliver(landing, MARCH, [_l(1, dti="150.0"), _l(3)])
    ingest(db, landing, MARCH)  # corrected delivery: the month is replaced
    stored = db.execute(
        "SELECT stream, rule, column_name, rows_affected, examples FROM ops.validation_warnings"
    ).fetchall()
    assert stored == [("listings", "R2.10", "dti", 1, [[1, "150.0"]])]
    live = _one(db, "SELECT max(load_id) FROM ops.ingest_log WHERE layer = 'clean'")
    assert _one(db, "SELECT max(load_id) FROM ops.validation_warnings") == live - 1


# T4.13
def test_a_month_that_failed_enters_once_fixed(db: PgConnection, landing: Path) -> None:
    _deliver(landing, MARCH, [_l(1, grade="H", sub_grade="H1")])
    _fails(db, landing, MARCH)
    _deliver(landing, MARCH, [_l(1)])
    results = ingest(db, landing, MARCH)
    assert results["listings"][1].status == "loaded"
    assert _one(db, "SELECT count(*) FROM clean.listings") == 1
    statuses = db.execute(
        "SELECT status FROM ops.ingest_log WHERE layer = 'clean' AND stream = 'listings' "
        "ORDER BY load_id"
    ).fetchall()
    assert [s for (s,) in statuses] == ["failed", "loaded"]


# T4.14
def test_every_run_writes_its_report(db: PgConnection, landing: Path) -> None:
    _deliver(landing, MARCH, [_l(1, dti="150.0")])
    ingest(db, landing, MARCH)
    _deliver(landing, MARCH, [_l(1, grade="H", sub_grade="H1")])
    _fails(db, landing, MARCH)
    reports = sorted((landing.parent / "validation" / "2015-03").glob("*.json"))
    assert len(reports) == 2
    passed, failed = (json.loads(p.read_text()) for p in reports)
    assert passed["status"] == "passed"
    assert passed["contract_changes"] == ["C9", "C1"]  # in force by 2015-03, in date order
    assert passed["rows"] == {"listings": 1, "outcomes": 0}
    assert [(f["rule"], f["level"]) for f in passed["findings"]] == [("R2.10", "warning")]
    assert failed["status"] == "failed"
    assert {(f["rule"], f["level"], f["column"]) for f in failed["findings"]} == {
        ("R2.1", "critical", "grade"),
        ("R2.1", "critical", "sub_grade"),
    }
    summary = reports[1].with_suffix(".md").read_text()
    assert summary.startswith("# Validation 2015-03: FAILED")
    assert "| R2.1 | listings | grade | 1 | loan 1, value H |" in summary
