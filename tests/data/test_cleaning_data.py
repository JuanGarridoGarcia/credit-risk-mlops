"""T2.11: every real delivery cleans without errors and with the same missing values.

Needs the deliveries in ``data/landing`` (``make publish PERIOD=2019-03``).
"""

from pathlib import Path

import polars as pl
import pytest

from credit_risk.cleaning import CLEANERS

ROOT = Path(__file__).resolve().parents[2]
LANDING = ROOT / "data" / "landing"

pytestmark = pytest.mark.data


@pytest.mark.parametrize("stream", ["listings", "outcomes"])
def test_real_deliveries_clean_with_the_same_missing_values(stream: str) -> None:
    files = sorted(LANDING.glob(f"*/{stream}.csv.gz"))
    if len(files) != 142:
        pytest.fail(f"expected 142 {stream} deliveries in {LANDING}, found {len(files)}")
    for path in files:
        raw = pl.read_csv(path, infer_schema=False)
        cleaned = CLEANERS[stream](raw)
        assert cleaned.height == raw.height, path
        assert cleaned.null_count().row(0) == raw.null_count().row(0), path
