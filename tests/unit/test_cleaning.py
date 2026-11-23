"""Tests T2 of cleaning, approved by Juan on 2026-11-23 (docs/technical.md, step 2.1)."""

from datetime import date

import polars as pl
import pytest

from credit_risk.cleaning import (
    LISTING_RULES,
    OUTCOME_RULES,
    CleaningError,
    Rule,
    clean,
    clean_listings,
)
from credit_risk.contracts import LISTING_COLUMNS, OUTCOME_COLUMNS


def _one(rule: Rule, values: list[str | None]) -> list[object]:
    frame = pl.DataFrame(
        {"id": [str(i) for i in range(len(values))], "x": values},
        schema={"id": pl.String, "x": pl.String},
    )
    return clean(frame, {"id": Rule.INTEGER, "x": rule})["x"].to_list()


def _fails(rule: Rule, value: str) -> None:
    with pytest.raises(CleaningError):
        _one(rule, [value])


# T2.1
def test_number() -> None:
    assert _one(Rule.NUMBER, ["20000.0", "0.0", "-1.0", "999.0", None]) == [
        20000.0,
        0.0,
        -1.0,
        999.0,
        None,
    ]
    _fails(Rule.NUMBER, "abc")


# T2.2
def test_month() -> None:
    assert _one(Rule.MONTH, ["Dec-2015", None]) == [date(2015, 12, 1), None]
    _fails(Rule.MONTH, "2015-12")
    _fails(Rule.MONTH, "Dic-2015")


# T2.3
def test_term() -> None:
    assert _one(Rule.TERM, [" 36 months", " 60 months"]) == [36, 60]
    for bad in ("36", "36 months", " 48 months"):
        _fails(Rule.TERM, bad)


# T2.4
def test_emp_length() -> None:
    real = ["< 1 year", "1 year", *[f"{n} years" for n in range(2, 10)], "10+ years"]
    assert _one(Rule.EMP_LENGTH, [*real, None]) == [*range(11), None]
    _fails(Rule.EMP_LENGTH, "Retired")


# T2.5
def test_flag() -> None:
    assert _one(Rule.FLAG, ["Y", "y", "N", "n", None]) == [True, True, False, False, None]
    _fails(Rule.FLAG, "Yes")


# T2.6
def test_text_is_unchanged() -> None:
    values = ["  Nurse ", "ANY", 'said "hi",\nthen <br/> left', None]
    assert _one(Rule.TEXT, values) == values


# T2.7
def test_every_contract_column_has_exactly_one_rule() -> None:
    assert tuple(LISTING_RULES) == LISTING_COLUMNS
    assert tuple(OUTCOME_RULES) == OUTCOME_COLUMNS
    assert set(LISTING_RULES.values()) | set(OUTCOME_RULES.values()) <= set(Rule)


def test_a_frame_with_other_columns_is_refused() -> None:
    frame = pl.DataFrame({"id": ["1"], "unknown": ["x"]})
    with pytest.raises(ValueError, match="do not match the contract"):
        clean(frame, {"id": Rule.INTEGER, "x": Rule.TEXT})


# T2.8
def test_error_names_column_loan_and_value() -> None:
    frame = pl.DataFrame({"id": ["7", "8"], "x": ["1.0", "abc"]})
    with pytest.raises(CleaningError) as err:
        clean(frame, {"id": Rule.INTEGER, "x": Rule.NUMBER})
    assert (err.value.column, err.value.loan_id, err.value.value) == ("x", "8", "abc")
    assert "'x'" in str(err.value)
    assert "'8'" in str(err.value)
    assert "'abc'" in str(err.value)


def _listings(n: int) -> pl.DataFrame:
    base = dict.fromkeys(LISTING_COLUMNS)
    rows = []
    for i in range(n):
        row = dict(base)
        row.update(
            id=str(1000 - i),  # descending, to check the order is kept
            loan_amnt=f"{1000 + i}.0",
            term=" 36 months" if i % 2 else " 60 months",
            emp_length=None if i == 2 else "10+ years",
            issue_d="Mar-2015",
            emp_title=f"  title {i} ",
            dti="999.0" if i == 1 else "12.5",
        )
        rows.append(row)
    return pl.DataFrame(rows, schema=dict.fromkeys(LISTING_COLUMNS, pl.String))


# T2.9
def test_rows_and_order_are_kept() -> None:
    raw = _listings(5)
    out = clean_listings(raw)
    assert out.height == raw.height
    assert out["id"].cast(pl.String).to_list() == raw["id"].to_list()


# T2.10
def test_one_row_or_a_month_give_the_same_result() -> None:
    raw = _listings(6)
    month = clean_listings(raw)
    row_by_row = pl.concat([clean_listings(raw.slice(i, 1)) for i in range(raw.height)])
    assert month.equals(row_by_row)
