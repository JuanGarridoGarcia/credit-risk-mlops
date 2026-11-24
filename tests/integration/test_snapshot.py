"""Tests T5 of training set versions in Postgres, approved by Juan on 2026-11-23.

T5.4, T5.5 and T5.12 changed and T5.15 added on Juan's approval of 2026-11-24 (D-069, D-088).

Clean is filled directly (one clean load per month and stream, rows with the columns the
build reads), so each test sets exactly the loans it needs. Decisions D-058 to D-061.
"""

import random
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from credit_risk.contracts import LISTING_COLUMNS, OUTCOME_COLUMNS, OUTCOME_ONLY_COLUMNS
from credit_risk.ingest import file_sha256
from credit_risk.snapshot import (
    EVALUATION,
    FEATURES,
    LABEL,
    LGD,
    RESOLVED,
    SPLIT,
    Manifest,
    SnapshotError,
    build,
    content_hash,
    read_evaluation,
    read_features,
    stale_versions,
)
from credit_risk.storage import LocalStore
from credit_risk.validation.contract import FIRST_PERIOD

from .conftest import PgConnection

pytestmark = pytest.mark.integration

CUTOFF = date(2014, 1, 1)
#: Default month of an outcome in these tests: after every matured listing, before T.
RESOLVED_IN = date(2013, 6, 1)
COMMIT = "0123456789abcdef0123456789abcdef01234567"
OLD_PAID = "Does not meet the credit policy. Status:Fully Paid"
OLD_BAD = "Does not meet the credit policy. Status:Charged Off"

Loads = dict[tuple[str, date], int]


def _month(year: int, month: int) -> date:
    return date(year, month, 1)


def _add(period: date, months: int) -> date:
    index = period.year * 12 + period.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def _months(first: date, last: date) -> list[date]:
    months = [first]
    while months[-1] < last:
        months.append(_add(months[-1], 1))
    return months


@pytest.fixture
def loads(db: PgConnection) -> Loads:
    """One clean load per month and stream, from the first delivery to a month after T."""
    found: Loads = {}
    for period in _months(FIRST_PERIOD, _add(CUTOFF, 1)):
        for stream in ("listings", "outcomes"):
            row = db.execute(
                "INSERT INTO ops.ingest_log (stream, layer, period, status, rows_in_file, "
                "rows_loaded) VALUES (%s, 'clean', %s, 'loaded', 0, 0) RETURNING load_id",
                (stream, period),
            ).fetchone()
            assert row is not None
            found[stream, period] = int(str(row[0]))
    return found


@pytest.fixture
def store(tmp_path: Path) -> LocalStore:
    return LocalStore(tmp_path / "training_sets")


def _listing(db: PgConnection, loads: Loads, id_: int, period: date, term: int = 36) -> None:
    db.execute(
        "INSERT INTO clean.listings (period, load_id, id, term, issue_d, loan_amnt, grade) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (period, loads["listings", period], id_, term, period, 1000.0 + id_, "B"),
    )


#: Amounts of an outcome: funded, principal repaid, recoveries, collection fee.
Amounts = tuple[float, float, float, float]
DEFAULT_AMOUNTS: Amounts = (1000.0, 400.0, 50.0, 10.0)


def _outcome(
    db: PgConnection,
    loads: Loads,
    id_: int,
    period: date,
    status: str,
    amounts: Amounts = DEFAULT_AMOUNTS,
) -> None:
    db.execute(
        "INSERT INTO clean.outcomes (period, load_id, id, loan_status, total_pymnt, "
        "funded_amnt, total_rec_prncp, recoveries, collection_recovery_fee) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (period, loads["outcomes", period], id_, status, 500.0 + id_, *amounts),
    )


def _loan(
    db: PgConnection,
    loads: Loads,
    id_: int,
    period: date,
    status: str | None = "Fully Paid",
    *,
    term: int = 36,
    resolved: date = RESOLVED_IN,
    amounts: Amounts = DEFAULT_AMOUNTS,
) -> None:
    _listing(db, loads, id_, period, term)
    if status is not None:
        _outcome(db, loads, id_, resolved, status, amounts)


def _labels(store: LocalStore, manifest: Manifest) -> dict[int, tuple[int, str]]:
    features = pl.read_parquet(store.local(manifest.version, FEATURES))
    return {i: (lab, s) for i, lab, s in features.select("id", LABEL, SPLIT).iter_rows()}


def _build(db: PgConnection, store: LocalStore) -> Manifest:
    return build(db, CUTOFF, store, commit=COMMIT)


# T5.1
def test_a_loan_enters_once_term_plus_five_months_have_passed(
    db: PgConnection, loads: Loads, store: LocalStore
) -> None:
    _loan(db, loads, 1, _month(2010, 8))  # 36 months, listed 41 months before T
    _loan(db, loads, 2, _month(2010, 9))  # 40 months before T
    _loan(db, loads, 3, _month(2008, 8), term=60)  # 60 months, 65 before T
    _loan(db, loads, 4, _month(2008, 9), term=60)  # 64 before T
    # Loans 1 and 3 are both validation under D-069: one training loan keeps the build valid.
    _loan(db, loads, 5, _month(2009, 1))
    assert set(_labels(store, _build(db, store))) == {1, 3, 5}


# T5.2
def test_the_label_follows_d013_and_leaves_the_old_policy_out(
    db: PgConnection, loads: Loads, store: LocalStore
) -> None:
    statuses = ["Fully Paid", "Charged Off", "Default", OLD_PAID, OLD_BAD]
    for id_, status in enumerate(statuses, start=1):
        _loan(db, loads, id_, _month(2009, 1), status)
    _loan(db, loads, 9, _month(2010, 8))  # a validation month
    manifest = _build(db, store)
    labels = {i: label for i, (label, _) in _labels(store, manifest).items()}
    assert labels == {1: 0, 2: 1, 3: 1, 9: 0}
    assert manifest.excluded_old_policy == 2


# T5.3
def test_an_outcome_unknown_at_t_leaves_the_loan_out(
    db: PgConnection, loads: Loads, store: LocalStore
) -> None:
    _loan(db, loads, 1, _month(2009, 1))
    _loan(db, loads, 2, _month(2009, 1), "Charged Off", resolved=_add(CUTOFF, 1))  # after T
    _loan(db, loads, 3, _month(2009, 1), None)  # no outcome yet
    _loan(db, loads, 9, _month(2010, 8))
    manifest = _build(db, store)
    assert set(_labels(store, manifest)) == {1, 9}
    assert manifest.excluded_unresolved == 2
    evaluation = pl.read_parquet(store.local(manifest.version, EVALUATION))
    assert evaluation["id"].to_list() == [1, 9]


# T5.4
def test_validation_is_the_last_six_matured_months_of_each_term(
    db: PgConnection, loads: Loads, store: LocalStore
) -> None:
    # 36 months: matured up to T-41, so validation is T-46 to T-41 (D-069).
    months_36 = _months(_add(CUTOFF, -50), _add(CUTOFF, -41))
    for id_, period in enumerate(months_36, start=1):
        _loan(db, loads, id_, period, "Charged Off" if id_ % 3 == 0 else "Fully Paid")
    # 60 months: matured up to T-65, so validation is T-70 to T-65.
    months_60 = _months(_add(CUTOFF, -74), _add(CUTOFF, -65))
    for id_, period in enumerate(months_60, start=101):
        _loan(db, loads, id_, period, "Charged Off" if id_ % 3 == 0 else "Fully Paid", term=60)
    manifest = _build(db, store)
    labels = _labels(store, manifest)
    validation = {i for i, (_, split) in labels.items() if split == "validation"}
    listed = {
        **dict(enumerate(months_36, start=1)),
        **dict(enumerate(months_60, start=101)),
    }
    assert {listed[i] for i in validation if i < 100} == set(
        _months(_add(CUTOFF, -46), _add(CUTOFF, -41))
    )
    assert {listed[i] for i in validation if i > 100} == set(
        _months(_add(CUTOFF, -70), _add(CUTOFF, -65))
    )
    # The edges: T-46 and T-70 are validation, T-47 and T-71 are training.
    by_month_36 = {m: i for i, m in enumerate(months_36, start=1)}
    by_month_60 = {m: i for i, m in enumerate(months_60, start=101)}
    assert labels[by_month_36[_add(CUTOFF, -46)]][1] == "validation"
    assert labels[by_month_36[_add(CUTOFF, -47)]][1] == "train"
    assert labels[by_month_60[_add(CUTOFF, -70)]][1] == "validation"
    assert labels[by_month_60[_add(CUTOFF, -71)]][1] == "train"
    assert set(labels) == set(listed)  # every loan once, in one split only
    assert manifest.rows_train == len(labels) - len(validation)
    assert manifest.rows_validation == len(validation)
    assert manifest.bad_train + manifest.bad_validation == sum(lab for lab, _ in labels.values())


# T5.5
def test_training_sees_no_outcome_column(db: PgConnection, loads: Loads, store: LocalStore) -> None:
    _loan(db, loads, 1, _month(2009, 1))
    _loan(db, loads, 2, _month(2010, 8), "Charged Off")
    manifest = _build(db, store)
    features = pl.read_parquet(store.local(manifest.version, FEATURES))
    evaluation = pl.read_parquet(store.local(manifest.version, EVALUATION))
    assert features.columns == [*LISTING_COLUMNS, LABEL, LGD, SPLIT]
    assert not set(features.columns) & set(OUTCOME_ONLY_COLUMNS)
    assert evaluation.columns == [*OUTCOME_COLUMNS, RESOLVED]
    assert evaluation["id"].to_list() == features["id"].to_list() == [1, 2]
    assert features["term"].dtype == pl.Int16
    assert features["issue_d"].dtype == pl.Date
    assert features[LGD].dtype == pl.Float64


# T5.6
@pytest.mark.parametrize("problem", ["missing", "failed"])
def test_a_month_missing_from_clean_stops_the_build(
    db: PgConnection, loads: Loads, store: LocalStore, problem: str
) -> None:
    _loan(db, loads, 1, _month(2009, 1))
    _loan(db, loads, 2, _month(2010, 8))
    if problem == "missing":
        db.execute("UPDATE ops.ingest_log SET status = 'unchanged' WHERE period = '2012-05-01'")
    else:
        db.execute(
            "INSERT INTO ops.ingest_log (stream, layer, period, status, error) "
            "VALUES ('outcomes', 'clean', '2012-05-01', 'failed', 'R2.1')"
        )
    with pytest.raises(SnapshotError, match=r"2012-05$"):
        _build(db, store)
    assert not store.root.exists()
    assert db.execute("SELECT count(*) FROM ops.training_sets").fetchone() == (0,)


# T5.7
def test_the_manifest_records_where_the_version_came_from(
    db: PgConnection, loads: Loads, store: LocalStore
) -> None:
    _loan(db, loads, 1, _month(2009, 1), "Charged Off")
    _loan(db, loads, 2, _month(2010, 8))
    manifest = _build(db, store)
    folder = store.root / manifest.version
    frames = {name: pl.read_parquet(folder / name) for name in (FEATURES, EVALUATION)}
    assert manifest.version == content_hash(frames)
    assert (manifest.cutoff, manifest.git_commit, manifest.path) == (CUTOFF, COMMIT, str(folder))
    assert manifest.features_sha256 == file_sha256(folder / FEATURES)
    assert manifest.evaluation_sha256 == file_sha256(folder / EVALUATION)
    assert (manifest.rows_train, manifest.bad_train) == (1, 1)
    assert (manifest.rows_validation, manifest.bad_validation) == (1, 0)
    used = db.execute(
        "SELECT load_id FROM ops.training_set_loads WHERE version = %s", (manifest.version,)
    ).fetchall()
    expected = {v for (_, period), v in loads.items() if period <= CUTOFF}
    assert {int(str(v)) for (v,) in used} == expected
    assert len(expected) == 2 * len(_months(FIRST_PERIOD, CUTOFF))


# T5.9
def test_a_rebuild_with_no_change_writes_nothing(
    db: PgConnection, loads: Loads, store: LocalStore
) -> None:
    _loan(db, loads, 1, _month(2009, 1))
    _loan(db, loads, 2, _month(2010, 8))
    first = _build(db, store)
    stamps = {p.name: p.stat().st_mtime_ns for p in (store.root / first.version).iterdir()}
    again = _build(db, store)
    assert again == first
    assert {p.name: p.stat().st_mtime_ns for p in (store.root / first.version).iterdir()} == stamps
    assert [p.name for p in store.root.iterdir()] == [first.version]
    assert db.execute("SELECT count(*) FROM ops.training_sets").fetchone() == (1,)


# T5.10
def test_a_corrected_month_gives_a_new_version_and_flags_the_old(
    db: PgConnection, loads: Loads, store: LocalStore
) -> None:
    _loan(db, loads, 1, _month(2009, 1))
    _loan(db, loads, 2, _month(2010, 8))
    old = _build(db, store)
    old_bytes = {p.name: p.read_bytes() for p in (store.root / old.version).iterdir()}
    assert stale_versions(db) == []
    # A corrected delivery of 2010-08 replaces the month in clean, as ingest does.
    row = db.execute(
        "INSERT INTO ops.ingest_log (stream, layer, period, status, rows_in_file, rows_loaded) "
        "VALUES ('listings', 'clean', '2010-08-01', 'replaced', 1, 1) RETURNING load_id"
    ).fetchone()
    assert row is not None
    db.execute("UPDATE clean.listings SET load_id = %s, loan_amnt = 1500.0 WHERE id = 2", (row[0],))
    new = _build(db, store)
    assert new.version != old.version
    assert {p.name: p.read_bytes() for p in (store.root / old.version).iterdir()} == old_bytes
    assert read_features(db, store, old.version).filter(pl.col("id") == 2)["loan_amnt"][0] == 1002.0
    assert stale_versions(db) == [old.version]


# T5.11
def test_a_stored_file_that_changed_is_refused(
    db: PgConnection, loads: Loads, store: LocalStore
) -> None:
    _loan(db, loads, 1, _month(2009, 1))
    _loan(db, loads, 2, _month(2010, 8))
    manifest = _build(db, store)
    path = store.local(manifest.version, FEATURES)
    # Same data, other bytes: only the checksum can tell.
    pl.read_parquet(path).write_parquet(path, compression="snappy")
    with pytest.raises(SnapshotError, match="checksum"):
        read_features(db, store, manifest.version)
    with pytest.raises(SnapshotError, match="checksum"):
        _build(db, store)
    assert read_evaluation(db, store, manifest.version).height == 2


# T5.12
@pytest.fixture
def many_loans(db: PgConnection, loads: Loads) -> None:
    """2,000 loans with every case at once: terms, statuses, outcomes late or missing."""
    rng = random.Random(20261123)  # noqa: S311 - test data, not security
    statuses = ["Fully Paid"] * 6 + ["Charged Off", "Default", OLD_PAID, OLD_BAD, None]
    months = _months(FIRST_PERIOD, CUTOFF)
    for id_ in range(1, 2001):
        period = rng.choice(months)
        status = rng.choice(statuses)
        term = rng.choice([36, 60])
        latest = _add(CUTOFF, 1)
        resolved = rng.choice(_months(period, latest)) if status else latest
        funded = rng.choice([0.0, 1000.0, 2500.0, 10000.0])  # 0: an LGD with no EAD
        repaid = round(rng.uniform(0, 1.1) * funded, 2)
        recovered = round(rng.uniform(0, 0.3) * funded, 2)
        fee = round(rng.uniform(0, 0.05) * funded, 2)
        _loan(
            db,
            loads,
            id_,
            period,
            status,
            term=term,
            resolved=resolved,
            amounts=(funded, repaid, recovered, fee),
        )


def _reference(db: PgConnection) -> pl.DataFrame:
    """The training set rule (D-040, D-013, D-069, D-088) written again in polars."""
    listings = pl.DataFrame(
        db.execute("SELECT id, period, term FROM clean.listings").fetchall(),
        schema=["id", "period", "term"],
        orient="row",
    )
    outcomes = pl.DataFrame(
        db.execute(
            "SELECT id, period, loan_status, funded_amnt, total_rec_prncp, recoveries, "
            "collection_recovery_fee FROM clean.outcomes"
        ).fetchall(),
        schema=["id", "resolved", "loan_status", "funded", "repaid", "recovered", "fee"],
        orient="row",
    )

    def month_index(column: str) -> pl.Expr:
        return pl.col(column).dt.year() * 12 + pl.col(column).dt.month() - 1

    cutoff = CUTOFF.year * 12 + CUTOFF.month - 1
    age = cutoff - month_index("period")
    labels = {"Fully Paid": 0, "Charged Off": 1, "Default": 1}
    kept = (
        listings.filter(age >= pl.col("term") + 5)
        .join(outcomes.filter(pl.col("resolved") <= CUTOFF), on="id", how="inner")
        .filter(pl.col("loan_status").is_in(list(labels)))
        .with_columns(pl.col("loan_status").replace_strict(labels).alias(LABEL))
    )
    split = (
        pl.when(age <= pl.col("term") + 5 + 5)  # the last 6 matured months of the term
        .then(pl.lit("validation"))
        .otherwise(pl.lit("train"))
    )
    old_enough = cutoff - month_index("resolved") >= 12
    loss = (pl.col("funded") - pl.col("repaid") - (pl.col("recovered") - pl.col("fee"))) / pl.when(
        pl.col("funded") != 0
    ).then(pl.col("funded"))
    lgd = pl.when((pl.col(LABEL) == 1) & old_enough).then(loss)
    return kept.select("id", pl.col(LABEL).cast(pl.Int16), lgd.alias(LGD), split.alias(SPLIT)).sort(
        "id"
    )


@pytest.mark.usefixtures("many_loans")
def test_the_sql_build_matches_an_independent_polars_version(
    db: PgConnection, store: LocalStore
) -> None:
    manifest = _build(db, store)
    got = read_features(db, store, manifest.version).select("id", LABEL, LGD, SPLIT)
    expected = _reference(db)
    # Enough of every case to mean something: 456 loans with this seed.
    assert expected.height > 400
    assert expected[LABEL].unique().sort().to_list() == [0, 1]
    assert expected[SPLIT].unique().sort().to_list() == ["train", "validation"]
    assert expected.filter(pl.col(LGD).is_not_null()).height > 20
    for term in (36, 60):  # both terms in validation (D-069)
        ids = set(
            pl.DataFrame(
                db.execute("SELECT id FROM clean.listings WHERE term = %s", (term,)).fetchall(),
                schema=["id"],
                orient="row",
            )["id"].to_list()
        )
        assert (
            expected.filter((pl.col(SPLIT) == "validation") & pl.col("id").is_in(list(ids))).height
            > 0
        )
    assert got.to_dicts() == expected.to_dicts()


# T5.15
def test_the_lgd_label_follows_d017_and_d088(
    db: PgConnection, loads: Loads, store: LocalStore
) -> None:
    month = _month(2009, 1)
    at_12 = _add(CUTOFF, -12)
    _loan(db, loads, 1, month, "Charged Off", resolved=at_12, amounts=(1000.0, 400.0, 50.0, 10.0))
    _loan(db, loads, 2, month, "Default", resolved=_add(CUTOFF, -11))  # too recent
    _loan(db, loads, 3, month, "Fully Paid", resolved=at_12)  # a good loan has no LGD
    _loan(db, loads, 4, month, "Charged Off", resolved=at_12, amounts=(1000.0, 900.0, 700.0, 0.0))
    _loan(db, loads, 9, _month(2010, 8))  # a validation month
    manifest = _build(db, store)
    features = pl.read_parquet(store.local(manifest.version, FEATURES))
    lgd = dict(features.select("id", LGD).iter_rows())
    # (1000 - 400 - (50 - 10)) / 1000
    assert lgd[1] == pytest.approx(0.56)
    assert lgd[2] is None
    assert lgd[3] is None
    assert lgd[9] is None
    # Recoveries above what was owed: kept as computed, below zero (D-088).
    assert lgd[4] == pytest.approx(-0.6)
