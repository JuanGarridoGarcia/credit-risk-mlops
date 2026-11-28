"""The study of the thresholds (D-150) with every month it asks the database for recorded:
T33.1 runs it on the exam's database, T33.5 on the history of the clock tests (D-157).
"""

from datetime import date
from typing import Any

import pytest

from credit_risk.monitoring import calibrate

#: What the study asks the database for, by the function that asks it.
ASKED = ("scored", "outcomes", "frames", "shares")


def spied_study(
    conn: Any, prefix: str, calendar: calibrate.Calendar = calibrate.REAL
) -> tuple[dict[str, Any], dict[str, list[date]]]:
    """The study of the pair of champions at T0, and the months it asked for."""
    asked: dict[str, list[date]] = {name: [] for name in ASKED}
    original = {
        name: getattr(calibrate, name)
        for name in ("scored_reference", "_outcomes", "build_frames", "first_year_shares")
    }

    def scored(c: Any, champions: Any, months: list[date]) -> Any:
        asked["scored"] += months
        return original["scored_reference"](c, champions, months)

    def outcomes(c: Any, listed: date, at: date) -> Any:
        asked["outcomes"] += [listed, at]
        return original["_outcomes"](c, listed, at)

    def frames(c: Any, cutoff: date, *args: Any, **kwargs: Any) -> Any:
        asked["frames"].append(cutoff)
        return original["build_frames"](c, cutoff, *args, **kwargs)

    def shares(c: Any, last: date) -> Any:
        asked["shares"].append(last)
        return original["first_year_shares"](c, last)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(calibrate, "scored_reference", scored)
        patch.setattr(calibrate, "_outcomes", outcomes)
        patch.setattr(calibrate, "build_frames", frames)
        patch.setattr(calibrate, "first_year_shares", shares)
        result = calibrate.study(conn, calibrate.t0_pair(conn), prefix, calendar)
    return result, asked


def _month(text: str) -> date:
    return date.fromisoformat(f"{text}-01")


def months_found(result: dict[str, Any]) -> list[date]:
    """The months of every row of the study."""
    return [
        *(_month(r["month"]) for r in result["drift"]),
        *(_month(r["evaluated"]) for r in result["early_warning"]),
        *(_month(r["cohort"]) for r in result["performance"]["cohorts"]),
        *(_month(r["cutoff"]) for r in result["level"]),
    ]
