"""T4.16: with the base contract alone, the replay stops exactly at the dated changes.

This shows that the stop works and that the list of changes in docs/validation_rules.md
is complete. Needs the deliveries in ``data/landing`` (``make publish PERIOD=2019-03``).
"""

from datetime import date
from pathlib import Path

import polars as pl
import pytest

from credit_risk.cleaning import CLEANERS
from credit_risk.contracts import STREAMS
from credit_risk.ingest import read_delivery
from credit_risk.validation.contract import CHANGES, contract_at
from credit_risk.validation.report import volume_findings
from credit_risk.validation.rules import validate_month

ROOT = Path(__file__).resolve().parents[2]
LANDING = ROOT / "data" / "landing"

pytestmark = pytest.mark.data


# T4.16
def test_the_base_contract_alone_stops_exactly_at_the_recorded_changes() -> None:
    periods = sorted(date.fromisoformat(f"{p.name}-01") for p in LANDING.iterdir())
    assert len(periods) == 142
    stops: set[date] = set()
    volumes: list[int] = []
    for period in periods:
        base = contract_at(period, changes=())
        for stream in STREAMS:
            frame = CLEANERS[stream](
                read_delivery(LANDING / f"{period:%Y-%m}" / f"{stream}.csv.gz", stream)
            )
            findings = validate_month(frame, stream, period, base)
            if stream == "listings":
                found, _ = volume_findings(stream, frame.height, volumes[-12:], expected=True)
                findings += found
                volumes.append(frame.height)
            if any(f.level == "critical" for f in findings):
                stops.add(period)
    # A change stops the replay from its month on; the first stop of each is its month.
    first_stops = {min(p for p in stops if p >= c.in_force) for c in CHANGES}
    assert first_stops == {c.in_force for c in CHANGES}
    assert min(stops) == min(c.in_force for c in CHANGES)
    with_changes = [p for p in stops if not contract_at(p).changes]
    assert with_changes == []
    assert pl.Series(sorted(stops)).dt.year().min() == 2014
