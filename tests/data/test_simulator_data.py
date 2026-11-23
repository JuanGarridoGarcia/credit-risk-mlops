"""T1.12: the simulator reproduces the audit's counts on the real file.

Needs ``data/raw/accepted_2007_to_2018Q4.csv.gz`` (downloaded by the audit notebook or
by ``make data``), so it does not run in CI. Run with ``make test-data``.
"""

from datetime import date
from pathlib import Path

import polars as pl
import pytest

from credit_risk.simulator.publish import load_prepared, publish

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data" / "raw" / "accepted_2007_to_2018Q4.csv.gz"
CACHE = ROOT / "data" / "simulator"

pytestmark = pytest.mark.data


@pytest.fixture(scope="module")
def published(tmp_path_factory: pytest.TempPathFactory) -> Path:
    if not SOURCE.exists():
        pytest.fail(f"{SOURCE} is missing: run 'make data' first")
    landing = tmp_path_factory.mktemp("landing")
    publish(load_prepared(SOURCE, CACHE), landing, until=date(2019, 3, 1))
    return landing


def _rows(landing: Path, stream: str) -> pl.DataFrame:
    return pl.concat(
        [
            pl.read_csv(p, infer_schema=False, columns=["id"]).with_columns(
                delivery=pl.lit(p.parent.name)
            )
            for p in sorted(landing.glob(f"*/{stream}.csv.gz"))
        ]
    )


# T1.12
def test_counts_match_the_audit(published: Path) -> None:
    prepared = load_prepared(SOURCE, CACHE)
    assert prepared.summary_rows_dropped == 33
    assert prepared.snapshot == date(2019, 3, 1)
    listings = _rows(published, "listings")
    outcomes = _rows(published, "outcomes")
    assert listings.height == 2_260_668
    assert listings["id"].n_unique() == 2_260_668
    assert outcomes.height == 1_345_350 + 2_749
    assert outcomes["id"].n_unique() == outcomes.height
    assert listings["delivery"].min() == "2007-06"
    assert listings["delivery"].max() == "2018-12"
    assert outcomes["delivery"].max() == "2019-03"


def test_no_outcome_before_its_listing_on_the_real_file(published: Path) -> None:
    listed = _rows(published, "listings").rename({"delivery": "listed"})
    resolved = _rows(published, "outcomes").rename({"delivery": "resolved"})
    joined = resolved.join(listed, on="id", how="left")
    assert joined["listed"].null_count() == 0
    assert (joined["resolved"] >= joined["listed"]).all()
