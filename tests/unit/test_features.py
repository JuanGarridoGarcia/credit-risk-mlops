"""Tests T6 of the fixed features, approved by Juan on 2026-11-23 (D-062, D-063)."""

from pathlib import Path

import polars as pl
import pytest

from credit_risk.cleaning import clean_listings
from credit_risk.contracts import OUTCOME_ONLY_COLUMNS
from credit_risk.features import FEATURES, SCHEMA, SOURCES, build_features
from tests import valid_rows

ROOT = Path(__file__).resolve().parents[2]


def _listings(*rows: dict[str, str | None]) -> pl.DataFrame:
    frame = pl.DataFrame(list(rows), schema=dict.fromkeys(rows[0], pl.String))
    return clean_listings(frame)


def _one(**values: str | None) -> dict[str, object]:
    return build_features(_listings(valid_rows.listing(1, **values))).row(0, named=True)


# T6.1
@pytest.mark.parametrize(
    ("issue", "earliest", "months"),
    [
        ("Mar-2015", "Mar-2015", 0),
        ("Mar-2015", "Feb-2015", 1),
        ("Mar-2015", "Sep-1990", 294),
        ("Jan-2016", "Dec-2015", 1),
        ("Mar-2015", None, None),
    ],
)
def test_credit_history_in_months(issue: str, earliest: str | None, months: int | None) -> None:
    assert _one(issue_d=issue, earliest_cr_line=earliest)["credit_history_months"] == months


# T6.2
@pytest.mark.parametrize(
    ("low", "high", "fico"),
    [("700.0", "704.0", 702.0), ("660.0", "665.0", 662.5), ("700.0", None, None)],
)
def test_fico_midpoint(low: str, high: str | None, fico: float | None) -> None:
    assert _one(fico_range_low=low, fico_range_high=high)["fico"] == fico


# T6.3
def test_the_output_is_id_and_the_30_features_with_their_types() -> None:
    out = build_features(_listings(valid_rows.listing(1)))
    assert len(FEATURES) == 30
    assert out.columns == ["id", *FEATURES]
    assert dict(out.schema) == dict(SCHEMA)


# T6.4
def test_no_forbidden_column_reaches_the_output() -> None:
    listings = _listings(valid_rows.listing(1)).with_columns(
        *(pl.lit(1.0).alias(c) for c in OUTCOME_ONLY_COLUMNS),
        pl.lit(1).alias("label"),
        pl.lit("train").alias("split"),
    )
    forbidden = {
        *OUTCOME_ONLY_COLUMNS,
        "label",
        "split",
        "installment",
        "emp_title",
        "desc",
        "title",
        "addr_state",
        "zip_code",
        "url",
        "member_id",
        "issue_d",
        "pub_rec_bankruptcies",
    }
    assert not set(build_features(listings).columns) & forbidden


# T6.5
def test_every_source_is_visible_at_listing_and_filled_since_2007() -> None:
    dictionary = pl.read_csv(ROOT / "reports/data_audit/data_dictionary.csv").filter(
        pl.col("available_at_listing") == "yes"
    )
    proven = {
        c
        for c, year in dictionary.select("column", "first_year_reported").iter_rows()
        if year == 2007
    }
    sources = {c for cols in SOURCES.values() for c in cols} - {"issue_d"}
    assert sources <= proven, sources - proven
    candidates = set(dictionary.filter(pl.col("use") == "feature candidate")["column"])
    assert sources <= candidates, sources - candidates


# T6.6
def test_one_row_gives_the_same_as_a_whole_month_in_any_order() -> None:
    rows = [
        valid_rows.listing(1),
        valid_rows.listing(2, earliest_cr_line="Jan-2001", fico_range_high="705.0"),
        valid_rows.listing(3, emp_length=None, dti=None, purpose="car", term=" 60 months"),
        valid_rows.listing(4, home_ownership="OWN", revol_util=None),
    ]
    month = build_features(_listings(*rows)).sort("id")
    backwards = build_features(_listings(*reversed(rows))).sort("id")
    one_by_one = pl.concat([build_features(_listings(r)) for r in rows])
    assert month.equals(backwards)
    assert month.equals(one_by_one)


# T6.7
def test_missing_values_stay_missing() -> None:
    rows = [
        valid_rows.listing(1),
        valid_rows.listing(
            2, emp_length=None, dti=None, revol_util=None, mths_since_last_delinq=None
        ),
        valid_rows.listing(3, fico_range_low=None, earliest_cr_line=None, purpose=None),
    ]
    listings = _listings(*rows)
    out = build_features(listings)
    for feature, sources in SOURCES.items():
        source_missing = listings.select(pl.any_horizontal(pl.col(s).is_null() for s in sources))
        assert out[feature].is_null().to_list() == source_missing.to_series().to_list(), feature
