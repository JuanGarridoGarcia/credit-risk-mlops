"""T6.8: the features of the training set version at 2018-12, the largest of the replay.

Uses the full real load of the session (tests/data/conftest.py), then builds the version.
"""

from datetime import date
from pathlib import Path

import polars as pl
import psycopg
import pytest

from credit_risk.features import FEATURES, build_features
from credit_risk.snapshot import build, read_features
from credit_risk.storage import LocalStore

pytestmark = pytest.mark.data

#: Allowed range of each numeric feature: (min, max), inclusive.
RANGES = {
    "loan_amnt": (500, 40_000),
    "term": (36, 60),
    "int_rate": (5, 31),
    "emp_length": (0, 10),
    "fico": (600, 850),
    "credit_history_months": (1, 1_000),
    "revol_util": (0, 900),
}


# T6.8
def test_the_features_of_the_largest_version_are_in_range(
    conn: psycopg.Connection[tuple[object, ...]], full_load: Path, tmp_path: Path
) -> None:
    store = LocalStore(tmp_path)
    manifest = build(conn, date(2018, 12, 1), store, commit="data-test")
    listings = read_features(conn, store, manifest.version)
    features = build_features(listings)
    assert features.height == manifest.rows_train + manifest.rows_validation == 522_904
    assert features.columns == ["id", *FEATURES]
    numeric = [c for c, t in features.schema.items() if t.is_numeric() and c != "id"]
    assert features.select(pl.col(numeric).min() >= 0).row(0) == (True,) * len(numeric)
    for column, (low, high) in RANGES.items():
        values = features[column].drop_nulls()
        assert low <= values.min() <= values.max() <= high, column  # type: ignore[operator]
    print("\n" + str(features.select(pl.col(numeric).null_count()).transpose(include_header=True)))
