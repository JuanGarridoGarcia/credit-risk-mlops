"""T5.13 and T5.14: the first training set on the real data, at T0 = 2014-01 (D-041).

Needs the deliveries in ``data/landing`` (``make publish PERIOD=2019-03``) and the
compose Postgres (``make up``). The fixtures of ``conftest.py`` load every month up to
T0, with validation, into a database of their own, then build the version.
"""

from datetime import date

import polars as pl
import psycopg
import pytest

from credit_risk.snapshot import FEATURES, LGD, SPLIT, Manifest
from credit_risk.storage import LocalStore
from tests.data.conftest import LANDING, T0

pytestmark = pytest.mark.data

Connection = psycopg.Connection[tuple[object, ...]]


# T5.13
def test_the_first_training_set_has_the_audit_counts(
    t0_conn: Connection, first: Manifest, t0_store: LocalStore
) -> None:
    """At T0 only what was known then: 21 loans fewer than the audit, which read the
    outcomes of the 2019 snapshot (E-022). Adding them back gives the audit's figures.
    The split per term (D-069) gives the same counts: no 60-month loan is matured at T0."""
    assert (first.rows_train, first.bad_train) == (7_733, 1_019)
    assert (first.rows_validation, first.bad_validation) == (4_324, 429)
    assert first.excluded_old_policy == 2_226
    features = pl.read_parquet(t0_store.local(first.version, FEATURES))
    assert features["term"].unique().to_list() == [36]
    # The LGD label (D-088): bad loans charged off at least 12 months before T0.
    with_lgd = features.filter(pl.col(LGD).is_not_null())
    assert with_lgd.height == 1_336
    assert with_lgd.group_by(SPLIT).len().sort(SPLIT).rows() == [
        ("train", 992),
        ("validation", 344),
    ]
    # The audit read the final status: count the matured loans resolved after T0 in the
    # later deliveries, which the build never saw.
    matured = t0_conn.execute(
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
def test_loans_without_a_known_outcome_are_measured(t0_conn: Connection, first: Manifest) -> None:
    row = t0_conn.execute(
        "SELECT count(*) FROM clean.listings AS l "
        "WHERE l.period <= (%s::date - make_interval(months => l.term + 5))::date "
        "AND NOT EXISTS (SELECT 1 FROM clean.outcomes AS o WHERE o.id = l.id AND o.period <= %s)",
        (T0, T0),
    ).fetchone()
    assert row is not None
    print(f"\nmatured at {T0:%Y-%m} with no outcome known: {row[0]}")
    assert first.excluded_unresolved == row[0]
