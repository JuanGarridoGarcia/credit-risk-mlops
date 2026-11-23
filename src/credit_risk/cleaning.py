"""Cleaning: from delivered text to typed values, with no opinions (D-045, D-046, D-051).

One implementation for every path: the monthly load cleans a whole month with these
functions and the API will clean a single listing with the same ones.

Cleaning may only convert types, normalise documented formats and decode documented
"unknown" codes (none are documented in Lending Club's dictionary, so none are
decoded). It never removes rows, fills gaps, caps values or merges categories. A value
that does not fit its rule stops the load with the column, the loan and the value; it
is never turned into a missing value. A missing value stays missing.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Final

import polars as pl

from credit_risk.contracts import LISTING_COLUMNS, OUTCOME_COLUMNS


class Rule(Enum):
    """The six kinds of cleaning rule."""

    INTEGER = "integer"  # loan id: digits to a 64-bit integer
    NUMBER = "number"  # text to a float; odd values (-1, 999, 0) stay as they are
    MONTH = "month"  # "Dec-2015" to 2015-12-01
    TERM = "term"  # " 36 months" to 36
    EMP_LENGTH = "emp_length"  # "< 1 year" to 0 ... "10+ years" to 10
    FLAG = "flag"  # "Y"/"y" to True, "N"/"n" to False
    TEXT = "text"  # unchanged, spaces included


TERMS: Final[Mapping[str, int]] = {" 36 months": 36, " 60 months": 60}
EMP_LENGTHS: Final[Mapping[str, int]] = {
    "< 1 year": 0,
    "1 year": 1,
    **{f"{n} years": n for n in range(2, 10)},
    "10+ years": 10,
}
FLAGS: Final[Mapping[str, bool]] = {"Y": True, "y": True, "N": False, "n": False}

DTYPES: Final[Mapping[Rule, pl.DataType]] = {
    Rule.INTEGER: pl.Int64(),
    Rule.NUMBER: pl.Float64(),
    Rule.MONTH: pl.Date(),
    Rule.TERM: pl.Int16(),
    Rule.EMP_LENGTH: pl.Int16(),
    Rule.FLAG: pl.Boolean(),
    Rule.TEXT: pl.String(),
}


def _convert(rule: Rule, col: str) -> pl.Expr:
    """Lenient conversion; failures become null and are caught by ``clean``."""
    c = pl.col(col)
    match rule:
        case Rule.INTEGER:
            return pl.when(c.str.contains(r"^\d+$")).then(c).cast(pl.Int64, strict=False)
        case Rule.NUMBER:
            return c.cast(pl.Float64, strict=False)
        case Rule.MONTH:
            return ("01-" + c).str.strptime(pl.Date, "%d-%b-%Y", strict=False)
        case Rule.TERM:
            return c.replace_strict(TERMS, default=None, return_dtype=pl.Int16)
        case Rule.EMP_LENGTH:
            return c.replace_strict(EMP_LENGTHS, default=None, return_dtype=pl.Int16)
        case Rule.FLAG:
            return c.replace_strict(FLAGS, default=None, return_dtype=pl.Boolean)
        case Rule.TEXT:
            return c


_TEXT_COLUMNS: Final = frozenset(
    {
        "member_id",
        "grade",
        "sub_grade",
        "emp_title",
        "home_ownership",
        "verification_status",
        "url",
        "desc",
        "purpose",
        "title",
        "zip_code",
        "addr_state",
        "initial_list_status",
        "application_type",
        "verification_status_joint",
        "disbursement_method",
        "loan_status",
        "hardship_type",
        "hardship_reason",
        "hardship_status",
        "hardship_loan_status",
        "settlement_status",
    }
)
_MONTH_COLUMNS: Final = frozenset(
    {
        "issue_d",
        "earliest_cr_line",
        "sec_app_earliest_cr_line",
        "last_pymnt_d",
        "next_pymnt_d",
        "last_credit_pull_d",
        "hardship_start_date",
        "hardship_end_date",
        "payment_plan_start_date",
        "debt_settlement_flag_date",
        "settlement_date",
    }
)
_SPECIAL: Final[Mapping[str, Rule]] = {
    "id": Rule.INTEGER,
    "term": Rule.TERM,
    "emp_length": Rule.EMP_LENGTH,
    "pymnt_plan": Rule.FLAG,
    "hardship_flag": Rule.FLAG,
    "debt_settlement_flag": Rule.FLAG,
}


def _rule_for(col: str) -> Rule:
    if col in _SPECIAL:
        return _SPECIAL[col]
    if col in _TEXT_COLUMNS:
        return Rule.TEXT
    if col in _MONTH_COLUMNS:
        return Rule.MONTH
    return Rule.NUMBER


#: One rule per column of each delivery, in contract order (test T2.7).
LISTING_RULES: Final[Mapping[str, Rule]] = {c: _rule_for(c) for c in LISTING_COLUMNS}
OUTCOME_RULES: Final[Mapping[str, Rule]] = {c: _rule_for(c) for c in OUTCOME_COLUMNS}


@dataclass(frozen=True)
class ColumnFailure:
    """The values of one column that do not fit its rule."""

    column: str
    rule: Rule
    loan_id: str | None
    value: str
    count: int

    def __str__(self) -> str:
        return (
            f"column {self.column!r} ({self.rule.value}): {self.count} value(s) do not fit; "
            f"first one: loan id {self.loan_id!r}, value {self.value!r}"
        )


@dataclass(frozen=True)
class CleaningError(ValueError):
    """Delivered values do not fit the rules of their columns.

    Every failing column of the frame is in ``failures`` (D-053: all failures at once);
    the fields name the first one.
    """

    column: str
    rule: Rule
    loan_id: str | None
    value: str
    count: int
    failures: tuple[ColumnFailure, ...] = ()

    def __str__(self) -> str:
        return "; ".join(str(f) for f in self.failures) or str(
            ColumnFailure(self.column, self.rule, self.loan_id, self.value, self.count)
        )


def clean(frame: pl.DataFrame, rules: Mapping[str, Rule]) -> pl.DataFrame:
    """Apply one rule per column. Same rows, same order, same columns, typed."""
    if list(frame.columns) != list(rules):
        missing = [c for c in rules if c not in frame.columns]
        extra = [c for c in frame.columns if c not in rules]
        raise ValueError(f"columns do not match the contract: missing {missing}, extra {extra}")
    out = frame.select(_convert(rule, col).alias(col) for col, rule in rules.items())
    failures = []
    for col, rule in rules.items():
        broken = frame[col].is_not_null() & out[col].is_null()
        if broken.any():
            first = frame.filter(broken).row(0, named=True)
            failures.append(
                ColumnFailure(col, rule, first.get("id"), first[col], int(broken.sum()))
            )
    if failures:
        f = failures[0]
        raise CleaningError(f.column, f.rule, f.loan_id, f.value, f.count, tuple(failures))
    return out


def clean_listings(frame: pl.DataFrame) -> pl.DataFrame:
    """Clean a ``listings`` delivery (a month, or a single listing)."""
    return clean(frame, LISTING_RULES)


def clean_outcomes(frame: pl.DataFrame) -> pl.DataFrame:
    """Clean an ``outcomes`` delivery."""
    return clean(frame, OUTCOME_RULES)


CLEANERS: Final[Mapping[str, Callable[[pl.DataFrame], pl.DataFrame]]] = {
    "listings": clean_listings,
    "outcomes": clean_outcomes,
}
