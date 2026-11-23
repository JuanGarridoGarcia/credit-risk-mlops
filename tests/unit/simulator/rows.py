"""Hand-made source rows for the simulator tests (T1).

Each loan is a dict with only the columns a test cares about; every other source
column is empty, as many columns are in the real file.
"""

import csv
import gzip
from pathlib import Path

import polars as pl

from credit_risk.contracts import LISTING_COLUMNS, OUTCOME_ONLY_COLUMNS

# Source column order: listing columns and outcome columns interleave in the real file,
# but the simulator selects by name, so any fixed order works for the tests.
SOURCE_ORDER = [*LISTING_COLUMNS, *OUTCOME_ONLY_COLUMNS]

Row = dict[str, str | None]


def loan(id_: str, issue: str, status: str, last_payment: str | None, **extra: str | None) -> Row:
    """A loan row with the fields the simulator reads, plus any extra columns."""
    return {
        "id": id_,
        "loan_amnt": "10000.0",
        "term": " 36 months",
        "issue_d": issue,
        "loan_status": status,
        "last_pymnt_d": last_payment,
        **extra,
    }


def summary(text: str) -> Row:
    """A summary row as Lending Club wrote them: text in ``id``, everything else empty."""
    return {"id": text}


def frame(rows: list[Row]) -> pl.DataFrame:
    """Rows as the simulator reads the source: every column present, all text."""
    return pl.DataFrame(
        [{col: row.get(col) for col in SOURCE_ORDER} for row in rows],
        schema=dict.fromkeys(SOURCE_ORDER, pl.String),
    )


def write_source(rows: list[Row], path: Path) -> Path:
    """Write rows as a gzip CSV like the real source file."""
    with gzip.open(path, "wt", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(SOURCE_ORDER)
        for row in rows:
            writer.writerow(["" if row.get(c) is None else row.get(c) for c in SOURCE_ORDER])
    return path


#: Snapshot month of the fixture: the latest last_pymnt_d below.
SNAPSHOT = "Mar-2019"

BASIC: list[Row] = [
    loan("101", "Jan-2015", "Fully Paid", "Jun-2016"),
    loan("102", "Jan-2015", "Charged Off", "Feb-2016"),
    summary("Total amount funded in policy code 1: 123"),
    summary("Total amount funded in policy code 2: 45"),
    loan("103", "Feb-2015", "Charged Off", None),
    loan("104", "Feb-2015", "Current", SNAPSHOT),
    summary("Loans that do not meet the credit policy"),
    loan("105", "Mar-2015", "Default", "Dec-2018"),
    loan("106", "Mar-2015", "In Grace Period", "Feb-2019"),
    loan("107", "Mar-2015", "Late (16-30 days)", "Feb-2019"),
    loan("108", "Mar-2015", "Late (31-120 days)", "Nov-2018"),
    loan("109", "Jan-2015", "Does not meet the credit policy. Status:Fully Paid", "Jan-2017"),
    summary("Total amount funded in policy code 1: 678"),
    summary("Total amount funded in policy code 2: 9"),
]
