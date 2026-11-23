"""T5.13 and T5.14: the first training set on the real data, at T0 = 2014-01 (D-041).

Needs the deliveries in ``data/landing`` (``make publish PERIOD=2019-03``) and the
compose Postgres (``make up``). Loads every month up to T0, with validation, into a
database of its own, then builds the version.
"""

import time
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import polars as pl
import psycopg
import pytest

from credit_risk.ingest import ingest
from credit_risk.settings import Settings
from credit_risk.snapshot import Manifest, build
from credit_risk.storage import LocalStore
from tests.integration.conftest import database_url, dbmate

ROOT = Path(__file__).resolve().parents[2]
LANDING = ROOT / "data" / "landing"
T0 = date(2014, 1, 1)

pytestmark = pytest.mark.data

Connection = psycopg.Connection[tuple[object, ...]]


@pytest.fixture(scope="module")
def conn() -> Iterator[Connection]:
    settings = Settings()
    name = "test_first_snapshot"
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


@pytest.fixture(scope="module")
def first(conn: Connection, tmp_path_factory: pytest.TempPathFactory) -> Manifest:
    reports = tmp_path_factory.mktemp("validation")
    periods = sorted(
        p for p in (date.fromisoformat(f"{d.name}-01") for d in LANDING.iterdir()) if p <= T0
    )
    assert len(periods) == 80
    start = time.perf_counter()
    for period in periods:
        ingest(conn, LANDING, period, reports=reports)
    loaded = time.perf_counter() - start
    start = time.perf_counter()
    store = LocalStore(tmp_path_factory.mktemp("training_sets"))
    manifest = build(conn, T0, store, commit="data-test")
    print(f"\nload up to {T0:%Y-%m}: {loaded:.0f} s; build: {time.perf_counter() - start:.1f} s")
    return manifest


# T5.13
def test_the_first_training_set_has_the_audit_counts(conn: Connection, first: Manifest) -> None:
    """At T0 only what was known then: 21 loans fewer than the audit, which read the
    outcomes of the 2019 snapshot (E-022). Adding them back gives the audit's figures."""
    assert (first.rows_train, first.bad_train) == (7_733, 1_019)
    assert (first.rows_validation, first.bad_validation) == (4_324, 429)
    assert first.excluded_old_policy == 2_226
    # The audit read the final status: count the matured loans resolved after T0 in the
    # later deliveries, which the build never saw.
    matured = conn.execute(
        "SELECT id FROM clean.listings AS l "
        "WHERE l.period <= (%s::date - make_interval(months => l.term + 5))::date",
        (T0,),
    ).fetchall()
    later = pl.concat(
        pl.read_csv(p, columns=["id", "loan_status"], schema_overrides={"id": pl.Int64})
        for p in sorted(LANDING.glob("*/outcomes.csv.gz"))
        if date.fromisoformat(f"{p.parent.name}-01") > T0
    ).filter(pl.col("id").is_in([i for (i,) in matured]))
    old = later["loan_status"].str.starts_with("Does not meet")
    audit_later = (int((~old).sum()), int(old.sum()))
    assert audit_later == (21, 4)
    assert first.rows_train + first.rows_validation + audit_later[0] == 12_078
    assert first.excluded_old_policy + audit_later[1] == 2_230
    assert first.excluded_unresolved == sum(audit_later)


# T5.14
def test_loans_without_a_known_outcome_are_measured(conn: Connection, first: Manifest) -> None:
    row = conn.execute(
        "SELECT count(*) FROM clean.listings AS l "
        "WHERE l.period <= (%s::date - make_interval(months => l.term + 5))::date "
        "AND NOT EXISTS (SELECT 1 FROM clean.outcomes AS o WHERE o.id = l.id AND o.period <= %s)",
        (T0, T0),
    ).fetchone()
    assert row is not None
    print(f"\nmatured at {T0:%Y-%m} with no outcome known: {row[0]}")
    assert first.excluded_unresolved == row[0]
