"""Turn the 2019 snapshot into monthly deliveries.

Pure functions on polars frames; file input and output live in ``io.py``.
"""

from datetime import date
from typing import Final

import polars as pl

from credit_risk.contracts import LISTING_COLUMNS, OUTCOME_COLUMNS

#: Months between the last payment (or the issue date, for loans that never paid) and
#: the estimated charge-off. Supported by the data: loans leave the late states about
#: 5 months after their last payment (data_audit.md section 4.2, E-013).
CHARGE_OFF_LAG_MONTHS: Final = 5

GOOD_STATUSES: Final = frozenset(
    {"Fully Paid", "Does not meet the credit policy. Status:Fully Paid"}
)
BAD_STATUSES: Final = frozenset(
    {"Charged Off", "Default", "Does not meet the credit policy. Status:Charged Off"}
)
RUNNING_STATUSES: Final = frozenset(
    {"Current", "In Grace Period", "Late (16-30 days)", "Late (31-120 days)"}
)
KNOWN_STATUSES: Final = GOOD_STATUSES | BAD_STATUSES | RUNNING_STATUSES

#: Column holding the delivery month of each row (first day of the month).
PERIOD: Final = "period"


class SourceError(ValueError):
    """The source file does not look like the one the simulator was built for."""


def _month(col: str) -> pl.Expr:
    """Parse Lending Club month text such as ``Dec-2015`` to the first day of the month."""
    return ("01-" + pl.col(col)).str.strptime(pl.Date, "%d-%b-%Y", strict=True)


def drop_summary_rows(source: pl.DataFrame) -> tuple[pl.DataFrame, int]:
    """Remove the summary rows Lending Club wrote between its files (E-004).

    A summary row has a non-numeric ``id`` and an empty ``loan_amnt``. Any other row
    that is not a loan stops the simulator instead of being dropped silently (T1.9 d).
    """
    is_summary = ~pl.col("id").str.contains(r"^\d+$") & pl.col("loan_amnt").is_null()
    summary = source.filter(is_summary)
    loans = source.filter(~is_summary)
    bad_rows = loans.filter(~pl.col("id").str.contains(r"^\d+$") | pl.col("issue_d").is_null())
    if bad_rows.height:
        first = bad_rows.row(0, named=True)
        raise SourceError(
            f"{bad_rows.height} rows are neither loans nor summary rows; "
            f"first one: id={first['id']!r}, issue_d={first['issue_d']!r}"
        )
    return loans, summary.height


def snapshot_month(loans: pl.DataFrame) -> date:
    """Date of the snapshot: the latest payment month in the file (2019-03)."""
    value = loans.select(_month("last_pymnt_d").max()).item()
    if not isinstance(value, date):
        raise SourceError("no payment dates in the source: cannot place the snapshot")
    return value


def add_periods(loans: pl.DataFrame, snapshot: date) -> pl.DataFrame:
    """Add the listing month and, for resolved loans, the resolution month.

    Resolution month (data_audit.md 4.2): good loans resolve in the month of their last
    payment; bad loans ``CHARGE_OFF_LAG_MONTHS`` after their last payment, or after
    issue if they never paid, capped at the snapshot. Running loans have none.
    """
    unknown = set(loans["loan_status"].unique().to_list()) - KNOWN_STATUSES
    if unknown:
        raise SourceError(f"unknown loan_status values: {sorted(map(str, unknown))}")
    lag = f"{CHARGE_OFF_LAG_MONTHS}mo"
    status = pl.col("loan_status")
    return loans.with_columns(
        listing_period=_month("issue_d"),
        resolution_period=pl.when(status.is_in(GOOD_STATUSES))
        .then(_month("last_pymnt_d"))
        .when(status.is_in(BAD_STATUSES))
        .then(
            pl.min_horizontal(
                pl.coalesce(
                    _month("last_pymnt_d").dt.offset_by(lag),
                    _month("issue_d").dt.offset_by(lag),
                ),
                pl.lit(snapshot),
            )
        )
        .otherwise(None),
    )


def _sorted(frame: pl.DataFrame) -> pl.DataFrame:
    """Fixed row order (numeric id) so the same input always gives the same bytes."""
    return frame.sort(pl.col("id").cast(pl.Int64))


def listings_for(prepared: pl.LazyFrame, period: date) -> pl.DataFrame:
    """The ``listings`` delivery of a month: loans listed that month, listing columns only."""
    rows = prepared.filter(pl.col("listing_period") == period).select(LISTING_COLUMNS)
    return _sorted(rows.collect())


def outcomes_for(prepared: pl.LazyFrame, period: date) -> pl.DataFrame:
    """The ``outcomes`` delivery of a month: loans resolved that month, outcome columns only."""
    rows = prepared.filter(pl.col("resolution_period") == period).select(OUTCOME_COLUMNS)
    return _sorted(rows.collect())


def all_periods(prepared: pl.LazyFrame) -> list[date]:
    """Every month with at least one listing or one outcome, in order."""
    months = pl.concat(
        [
            prepared.select(pl.col("listing_period").alias("p")),
            prepared.select(pl.col("resolution_period").alias("p")),
        ]
    )
    return sorted(months.drop_nulls().unique().collect()["p"].to_list())
