"""The fixed features of the model, the same in training, in the API and in monitoring.

Fixed means they learn nothing from the data (D-062): every value depends only on its own
row. What is learned (filling gaps, encoding categories, scaling) lives inside the model
and is fitted on the training split only (F3). v1 has 30 features (D-063): the listing
columns proven visible at listing (D-014) and filled since 2007 (D-016), without free text
(D-015), state or zip code (D-018) or ``installment`` (funded-amount leak, decided in F3),
plus two transformations a model needs to read the data:

- ``credit_history_months``: months from ``earliest_cr_line`` to ``issue_d``;
- ``fico``: the midpoint of ``fico_range_low`` and ``fico_range_high``.

Missing values stay missing.
"""

from collections.abc import Mapping
from typing import Final

import polars as pl

from credit_risk.cleaning import DTYPES, LISTING_RULES

#: Listing columns used as they are, in this order.
NUMERIC: Final = (
    "loan_amnt",
    "term",
    "int_rate",
    "emp_length",
    "annual_inc",
    "dti",
    "delinq_2yrs",
    "inq_last_6mths",
    "mths_since_last_delinq",
    "mths_since_last_record",
    "open_acc",
    "pub_rec",
    "revol_bal",
    "revol_util",
    "total_acc",
    "collections_12_mths_ex_med",
    "acc_now_delinq",
    "chargeoff_within_12_mths",
    "delinq_amnt",
    "tax_liens",
)
CATEGORICAL: Final = (
    "grade",
    "sub_grade",
    "home_ownership",
    "verification_status",
    "purpose",
    "initial_list_status",
    "application_type",
    "disbursement_method",
)
FICO: Final = "fico"
HISTORY: Final = "credit_history_months"

#: The 30 features, in the order the model receives them.
FEATURES: Final = (*NUMERIC, FICO, HISTORY, *CATEGORICAL)

#: The listing columns each feature is computed from.
SOURCES: Final[Mapping[str, tuple[str, ...]]] = {
    **{c: (c,) for c in (*NUMERIC, *CATEGORICAL)},
    FICO: ("fico_range_low", "fico_range_high"),
    HISTORY: ("issue_d", "earliest_cr_line"),
}
#: Every column the features read, plus the key.
INPUTS: Final = ("id", *sorted({c for cols in SOURCES.values() for c in cols}))

SCHEMA: Final[Mapping[str, pl.DataType]] = {
    "id": pl.Int64(),
    **{c: DTYPES[LISTING_RULES[c]] for c in NUMERIC},
    FICO: pl.Float64(),
    HISTORY: pl.Int32(),
    **{c: DTYPES[LISTING_RULES[c]] for c in CATEGORICAL},
}


def _months(column: str) -> pl.Expr:
    date = pl.col(column)
    return date.dt.year().cast(pl.Int32) * 12 + date.dt.month().cast(pl.Int32)


def build_features(listings: pl.DataFrame) -> pl.DataFrame:
    """``id`` and the 30 features of cleaned listings, one row per listing, same order.

    Works the same on one listing (the API) and on a whole set (training). Columns that
    are not inputs, such as the label, the split or any outcome, never reach the output.
    """
    missing = [c for c in INPUTS if c not in listings.columns]
    if missing:
        raise ValueError(f"listings lack the columns {', '.join(missing)}")
    return listings.select(
        pl.col("id"),
        *(pl.col(c) for c in NUMERIC),
        ((pl.col("fico_range_low") + pl.col("fico_range_high")) / 2).alias(FICO),
        (_months("issue_d") - _months("earliest_cr_line")).alias(HISTORY),
        *(pl.col(c) for c in CATEGORICAL),
    ).cast(pl.Schema(SCHEMA))
