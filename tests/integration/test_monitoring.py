"""T25.1, T25.2, T25.4: the early warning on its cohort (D-143); T26.1: real performance of
a matured cohort (D-144); T27.1, T27.3: the tables of ``monitoring`` and running a month
again (D-145, D-146). Approved by Juan on 2026-11-26.

Postgres only: a few loans are written straight into ``clean`` and ``serving`` with the
months that matter, and :func:`credit_risk.monitoring.store.monitor` measures them. The
training cutoff of a model version lives in MLflow; these tests give it directly.
"""

import json
import uuid
from datetime import date
from typing import Any

import psycopg
import pytest
from psycopg import Connection as PgConnection
from psycopg import errors

from credit_risk.monitoring import outcomes, store
from credit_risk.settings import Settings

from .conftest import database_url, dbmate

pytestmark = pytest.mark.integration

COHORT = date(2010, 1, 1)
EVALUATED = date(2011, 6, 1)  # COHORT + 17 months
MATURED = date(2008, 1, 1)  # 36 months + 5 = 41 months before EVALUATED


@pytest.fixture
def mdb(db: PgConnection, monkeypatch: pytest.MonkeyPatch) -> PgConnection:
    """The migrated database with ``serving`` and ``monitoring`` emptied too."""
    db.execute(
        "TRUNCATE serving.purchases, serving.predictions, serving.requests, "
        "monitoring.drift, monitoring.early_warning, monitoring.performance, "
        "monitoring.reference"
    )
    cutoffs = {"1": date(2009, 1, 1), "2": date(2009, 4, 1)}
    monkeypatch.setattr(store, "cutoff", lambda _conn, _name, version: cutoffs[version])
    return db


def _load(conn: PgConnection, stream: str, period: date) -> int:
    row = conn.execute(
        "INSERT INTO ops.ingest_log (stream, layer, period, status, rows_in_file, rows_loaded)"
        " VALUES (%s, 'clean', %s, 'loaded', 0, 0) RETURNING load_id",
        (stream, period),
    ).fetchone()
    assert row is not None
    return int(row[0])


def _loan(
    conn: PgConnection,
    loan_id: int,
    listed: date,
    *,
    term: int = 36,
    grade: str = "A",
    status: str | None = None,
    delivered: date | None = None,
    last_paid: date | None = None,
    funded: float = 10_000.0,
    paid: float = 0.0,
    principal: float = 0.0,
    recoveries: float = 0.0,
) -> None:
    conn.execute(
        "INSERT INTO clean.listings (period, load_id, id, term, grade, issue_d)"
        " VALUES (%s, %s, %s, %s, %s, %s)",
        (listed, _load(conn, "listings", listed), loan_id, term, grade, listed),
    )
    if status is not None:
        assert delivered is not None
        conn.execute(
            "INSERT INTO clean.outcomes (period, load_id, id, loan_status, last_pymnt_d,"
            " funded_amnt, total_pymnt, total_rec_prncp, recoveries, collection_recovery_fee)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0)",
            (
                delivered, _load(conn, "outcomes", delivered), loan_id, status, last_paid,
                funded, paid, principal, recoveries,
            ),
        )  # fmt: skip


def _predict(
    conn: PgConnection,
    loan_id: int,
    listed: date,
    pd_: float,
    *,
    version: str = "1",
    lgd: float = 0.8,
    term: int = 36,
    grade: str = "A",
) -> int:
    request = uuid.uuid4()
    conn.execute(
        "INSERT INTO serving.requests (request_id, endpoint, status, latency_ms, api_version)"
        " VALUES (%s, '/predict', 200, 1, 'test')",
        (request,),
    )
    row = conn.execute(
        """
        INSERT INTO serving.predictions
            (request_id, loan_id, listed, pd_version, lgd_version, api_version, covered,
             pd, lgd, ead, expected_loss, el_rate, contributions, features, request)
        VALUES (%s, %s, %s, %s, %s, 'test', true, %s, %s, 10000, %s, %s, '{}', %s, '{}')
        RETURNING prediction_id
        """,
        (
            request, loan_id, listed, version, version, pd_, lgd, pd_ * lgd * 10_000,
            pd_ * lgd, json.dumps({"term": term, "grade": grade}),
        ),
    ).fetchone()  # fmt: skip
    assert row is not None
    return int(row[0])


def _buy(conn: PgConnection, prediction_id: int, loan_id: int, amount: float) -> None:
    request = uuid.uuid4()
    conn.execute(
        "INSERT INTO serving.requests (request_id, endpoint, status, latency_ms, api_version)"
        " VALUES (%s, '/purchases', 200, 1, 'test')",
        (request,),
    )
    conn.execute(
        "INSERT INTO serving.purchases"
        " (request_id, client, order_id, prediction_id, loan_id, amount, policy)"
        " VALUES (%s, 'investor', %s, %s, %s, %s, 'passes')",
        (request, f"order-{loan_id}", prediction_id, loan_id, amount),
    )


def _rows(conn: PgConnection, table: str) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cursor:
        return cursor.execute(f"SELECT * FROM monitoring.{table} ORDER BY 1, 2, 3").fetchall()  # noqa: S608


def _month(year: int, month: int) -> date:
    return date(year, month, 1)


# T25.1
def test_the_first_year_share_is_measured_on_the_cohorts_matured_at_the_cutoff(
    mdb: PgConnection,
) -> None:
    cutoff = date(2012, 1, 1)
    old = date(2008, 6, 1)  # matured at the cutoff: 36 + 5 = 41 months before is 2008-08
    loan = 1
    # Grade A: 60 defaults, 24 of them stopped paying within 12 months of issue.
    for i in range(60):
        last = None if i < 4 else (_month(2009, 5) if i < 24 else _month(2009, 6))
        _loan(mdb, loan, old, grade="A", status="Charged Off", delivered=_month(2010, 1),
              last_paid=last)  # fmt: skip
        loan += 1
    # Grade G: 10 defaults, all early: fewer than 50, it takes the share of the term.
    for _ in range(10):
        _loan(mdb, loan, old, grade="G", status="Charged Off", delivered=_month(2009, 1))
        loan += 1
    # Not counted: a good loan, a default delivered after the cutoff, a loan listed too
    # late to have matured, and one of the old credit policy.
    _loan(mdb, loan, old, grade="A", status="Fully Paid", delivered=_month(2011, 6))
    _loan(mdb, loan + 1, old, grade="A", status="Charged Off", delivered=_month(2012, 2))
    _loan(mdb, loan + 2, _month(2008, 9), grade="A", status="Charged Off",
          delivered=_month(2009, 3))  # fmt: skip
    _loan(mdb, loan + 3, old, grade="A",
          status="Does not meet the credit policy. Status:Charged Off",
          delivered=_month(2009, 3))  # fmt: skip
    shares = store.first_year_shares(mdb, cutoff)
    # Last payment 2009-05 = issue + 11: first missed payment at issue + 12, early.
    assert shares.share(36, "A") == pytest.approx(24 / 60)
    assert shares.share(36, "G") == pytest.approx((24 + 10) / 70)
    assert shares.by_grade.keys() == {(36, "A")}


def _early_cohort(conn: PgConnection) -> None:
    """Seven loans listed in COHORT, as known 17 months later."""
    loans = [
        # Stopped paying in 2010-07 (last payment 2010-06): early, delivered in time.
        ("Charged Off", _month(2010, 11), _month(2010, 6)),
        # Never paid: early.
        ("Charged Off", _month(2010, 6), None),
        # Last payment 2010-12 = issue + 11: first missed at issue + 12, still early.
        ("Charged Off", _month(2011, 5), _month(2010, 12)),
        # Last payment 2011-01: first missed at issue + 13, not early.
        ("Charged Off", _month(2011, 6), _month(2011, 1)),
        # Early, but its outcome arrives after the month measured: not known yet.
        ("Charged Off", _month(2011, 7), _month(2010, 3)),
        # Paid off early: not a default.
        ("Fully Paid", _month(2010, 9), _month(2010, 9)),
        # Still running.
        (None, None, None),
    ]
    for i, (status, delivered, last) in enumerate(loans, start=100):
        _loan(conn, i, COHORT, status=status, delivered=delivered, last_paid=last)
        _predict(conn, i, COHORT, 0.2)


# T25.2
def test_the_early_warning_counts_only_the_outcomes_delivered_by_its_month(
    mdb: PgConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    _early_cohort(mdb)
    shares = outcomes.FirstYear({}, {36: 0.5})
    monkeypatch.setattr(store, "first_year_shares", lambda _conn, _at: shares)

    before = store.monitor(mdb, _month(2011, 5))
    assert before.early_warning == 0, "the cohort is not measured before COHORT + 17"
    assert _rows(mdb, "early_warning") == []

    month = store.monitor(mdb, EVALUATED)
    assert month.early_warning == 1
    (row,) = _rows(mdb, "early_warning")
    assert (row["cohort"], row["evaluated"], row["term"]) == (COHORT, EVALUATED, 36)
    assert (row["loans"], row["defaults"]) == (7, 3)
    assert row["expected_defaults"] == pytest.approx(7 * 0.2 * 0.5)
    assert row["ratio"] == pytest.approx((3 / 7) / 0.1)
    assert row["ratio_low"] <= row["ratio"] <= row["ratio_high"]


# T25.4
def test_each_cohort_is_measured_with_the_model_version_that_predicted_it(
    mdb: PgConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    by_cutoff = {date(2009, 1, 1): 0.5, date(2009, 4, 1): 0.25}
    monkeypatch.setattr(
        store, "first_year_shares", lambda _conn, at: outcomes.FirstYear({}, {36: by_cutoff[at]})
    )
    for i in range(10):
        _loan(mdb, 200 + i, COHORT, status="Charged Off", delivered=_month(2010, 8))
        _predict(mdb, 200 + i, COHORT, 0.1, version="1" if i < 6 else "2")
    # Scored again later by version 2 (a new champion): the first answer is the one kept.
    _predict(mdb, 200, COHORT, 0.9, version="2")

    store.monitor(mdb, EVALUATED)

    found = {r["pd_version"]: r for r in _rows(mdb, "early_warning")}
    assert set(found) == {"1", "2"}
    assert (found["1"]["loans"], found["2"]["loans"]) == (6, 4)
    # Each with the first-year share at the cutoff of its own version.
    assert found["1"]["expected_defaults"] == pytest.approx(6 * 0.1 * 0.5)
    assert found["2"]["expected_defaults"] == pytest.approx(4 * 0.1 * 0.25)


def _matured_cohort(conn: PgConnection) -> None:
    """Loans listed in MATURED (36 months) and one of 60 months, measured at EVALUATED."""
    _loan(conn, 300, MATURED, grade="A", status="Fully Paid", delivered=_month(2011, 1),
          funded=10_000, paid=11_500, principal=10_000)  # fmt: skip
    # Charged off 13 months before: its loss is known (D-017).
    _loan(conn, 301, MATURED, grade="B", status="Charged Off", delivered=_month(2010, 5),
          funded=10_000, paid=4_000, principal=3_500, recoveries=500)  # fmt: skip
    # Charged off 5 months before: a default, but its loss is not final yet.
    _loan(conn, 302, MATURED, grade="B", status="Charged Off", delivered=_month(2011, 1),
          funded=10_000, paid=6_000, principal=5_000)  # fmt: skip
    # Its outcome arrives next month: unresolved now.
    _loan(conn, 303, MATURED, grade="A", status="Fully Paid", delivered=_month(2011, 7))
    # 60 months: matures only at MATURED + 65.
    _loan(conn, 304, MATURED, term=60, grade="A", status="Fully Paid",
          delivered=_month(2011, 2))  # fmt: skip
    for loan, pd_, grade, term in (
        (300, 0.1, "A", 36), (301, 0.3, "B", 36), (302, 0.4, "B", 36), (303, 0.1, "A", 36),
        (304, 0.2, "A", 60),
    ):  # fmt: skip
        prediction = _predict(conn, loan, MATURED, pd_, lgd=0.7, term=term, grade=grade)
        if loan == 300:
            _buy(conn, prediction, loan, 50.0)


# T26.1
def test_a_cohort_is_measured_when_it_matures_with_the_outcomes_known_then(
    mdb: PgConnection,
) -> None:
    _matured_cohort(mdb)

    assert store.monitor(mdb, _month(2011, 5)).performance == 0, "not yet matured"
    month = store.monitor(mdb, EVALUATED)

    rows = {r["segment"]: r for r in _rows(mdb, "performance")}
    assert month.performance == len(rows) == 3  # all, grade=A, grade=B
    overall = rows["all"]
    assert (overall["cohort"], overall["term"], overall["evaluated"]) == (MATURED, 36, EVALUATED)
    assert (overall["loans"], overall["defaults"], overall["unresolved"]) == (3, 2, 1)
    assert overall["lgd_loans"] == 1
    loss = (10_000 - 3_500 - 500) / 10_000
    assert overall["lgd_rmse"] == pytest.approx(abs(0.7 - loss))
    assert overall["lgd_level"] == pytest.approx(0.7 - loss)
    assert (overall["purchases"], overall["invested"]) == (1, 50.0)
    assert overall["realised_return"] == pytest.approx(11_500 / 10_000 - 1)
    assert (rows["grade=A"]["loans"], rows["grade=A"]["unresolved"]) == (1, 1)
    assert rows["grade=B"]["defaults"] == 2
    assert all(r["term"] == 36 for r in rows.values()), "the 60-month loan is not mature"


# T27.1
def test_the_monitoring_tables_migrate_and_refuse_impossible_rows(
    settings: Settings, empty_database: str
) -> None:
    url = database_url(settings, empty_database)
    for action in ("up", "down", "up"):
        result = dbmate(url, action)
        assert result.returncode == 0, result.stderr
    conninfo = settings.postgres_conninfo().replace(
        f"dbname={settings.postgres_db}", f"dbname={empty_database}"
    )
    with psycopg.connect(conninfo, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO monitoring.reference (pd_version, lgd_version, subject, kind, cutoff,"
            " first_month, last_month, rows, nulls, edges, shares)"
            " VALUES ('1', '1', 'dti', 'numeric', '2014-01-01', '2013-01-01', '2013-12-01',"
            " 10, 0, '{1,2}', '{0.5,0.3,0.2,0}')"
        )
        drift = (
            "INSERT INTO monitoring.drift (period, pd_version, lgd_version, subject, kind,"
            " rows, psi, null_share, new_values)"
            " VALUES ('2014-02-01', '1', '1', 'dti', 'numeric', 10, %s, 0, 0)"
        )
        conn.execute(drift, (0.02,))
        with pytest.raises(errors.CheckViolation):
            conn.execute(drift.replace("2014-02-01", "2014-03-01"), (-0.1,))
        with pytest.raises(errors.ForeignKeyViolation):
            conn.execute(drift.replace("'dti'", "'fico'", 1), (0.1,))
        warning = (
            "INSERT INTO monitoring.early_warning (cohort, term, pd_version, evaluated, loans,"
            " defaults, expected_defaults, observed_rate, expected_rate, ratio, ratio_low,"
            " ratio_high) VALUES ('2014-02-01', 36, '1', %s, 100, 5, 4, 0.05, 0.04, 1.25,"
            " %s, %s)"
        )
        conn.execute(warning, (date(2015, 7, 1), 0.6, 2.0))
        with pytest.raises(errors.CheckViolation):  # the low end above the ratio
            conn.execute(
                warning.replace("'2014-02-01'", "'2014-03-01'"), (date(2015, 8, 1), 1.3, 2.0)
            )
        with pytest.raises(errors.CheckViolation):  # measured before cohort + 17 months
            conn.execute(
                warning.replace("'2014-02-01'", "'2014-04-01'"), (date(2015, 8, 1), 0.6, 2.0)
            )


# T27.3
def test_measuring_a_month_again_replaces_its_rows(mdb: PgConnection) -> None:
    _matured_cohort(mdb)
    first = store.monitor(mdb, EVALUATED)
    stored = _rows(mdb, "performance")
    again = store.monitor(mdb, EVALUATED)
    assert (again.performance, len(_rows(mdb, "performance"))) == (first.performance, len(stored))
    assert [
        {k: v for k, v in r.items() if k != "computed_at"} for r in _rows(mdb, "performance")
    ] == [{k: v for k, v in r.items() if k != "computed_at"} for r in stored]
    # The month again after an outcome changed: its rows are replaced, not added.
    mdb.execute("DELETE FROM clean.outcomes WHERE id = 302")
    store.monitor(mdb, EVALUATED)
    overall = [r for r in _rows(mdb, "performance") if r["segment"] == "all"]
    assert len(overall) == 1
    assert (overall[0]["defaults"], overall[0]["unresolved"]) == (1, 2)
