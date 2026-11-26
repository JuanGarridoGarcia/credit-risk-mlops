"""T33.1 (data part), T33.2 and T33.4: the study of the thresholds and their exam (D-150,
D-156). Approved by Juan on 2026-11-26.

They read the database the exam leaves (``make exam``, :mod:`tests.data.exam`): the study
runs on it with the pair of champions trained at T0, and the exam is the simulation
2014-01 to 2018-12 it holds, with the thresholds frozen. The exam takes hours, more than a
test may, so these tests read what it left and fail with what to run when it is missing.
"""

import json
import os
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import mlflow
import psycopg
import pytest
from psycopg.rows import dict_row

from credit_risk.monitoring import calibrate
from credit_risk.settings import Settings
from tests.data import exam

pytestmark = pytest.mark.data

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def conn() -> Iterator[psycopg.Connection[Any]]:
    """The exam's database, past T0; the study reads it as the system does."""
    settings = Settings()
    previous = os.environ.get("POSTGRES_DB")
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    try:
        connection = psycopg.connect(exam.conninfo(settings), autocommit=True)
    except psycopg.OperationalError as error:
        pytest.fail(f"no exam database ({error}): run 'make exam' first")
    os.environ["POSTGRES_DB"] = exam.NAME
    try:
        with connection:
            yield connection
    finally:
        if previous is None:
            os.environ.pop("POSTGRES_DB", None)
        else:
            os.environ["POSTGRES_DB"] = previous


@pytest.fixture(scope="module")
def spied(conn: psycopg.Connection[Any]) -> tuple[dict[str, Any], dict[str, list[date]]]:
    """The study, with every month it asks the database for recorded."""
    asked: dict[str, list[date]] = {"scored": [], "outcomes": [], "frames": [], "shares": []}
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
        result = calibrate.study(conn, calibrate.t0_pair(conn), exam.PREFIX)
    return result, asked


def _month(text: str) -> date:
    return date.fromisoformat(f"{text}-01")


# T33.1 (data part)
def test_the_study_reads_nothing_after_what_was_known_at_t0(
    spied: tuple[dict[str, Any], dict[str, list[date]]],
) -> None:
    result, asked = spied
    for what, months in asked.items():
        assert months, f"the study asked for no {what}"
        assert max(months) <= calibrate.LAST_KNOWN, what
    found = [
        *(_month(r["month"]) for r in result["drift"]),
        *(_month(r["evaluated"]) for r in result["early_warning"]),
        *(_month(r["cohort"]) for r in result["performance"]["cohorts"]),
        *(_month(r["cutoff"]) for r in result["level"]),
    ]
    assert max(found) <= calibrate.LAST_KNOWN
    assert result["last_known"] == f"{calibrate.LAST_KNOWN:%Y-%m}"


# T33.2
def test_the_study_is_reproducible_and_its_published_tables_are_its_own(
    conn: psycopg.Connection[Any], spied: tuple[dict[str, Any], dict[str, list[date]]]
) -> None:
    first, _ = spied
    again = calibrate.study(conn, calibrate.t0_pair(conn), exam.PREFIX)
    assert again == first, "two runs give the same study"
    found = calibrate.summary(first)
    committed = json.loads((ROOT / calibrate.SUMMARY).read_text())
    assert found == committed, "run 'make calibrate' and commit reports/thresholds"
    document = (ROOT / calibrate.DOCUMENT).read_text()
    assert calibrate.published(document) == calibrate.tables(found)


# T33.4
def test_the_exam_runs_every_month_and_raises_the_documented_alerts(
    conn: psycopg.Connection[Any],
) -> None:
    month = conn.execute("SELECT month FROM sim.clock").fetchone()
    assert month is not None, "run 'make exam' first"
    assert month[0] == calibrate.EXAM_LAST, "run 'make exam' to the end"
    with conn.cursor(row_factory=dict_row) as cursor:
        failed = cursor.execute("SELECT * FROM ops.alerts WHERE kind = 'flow_failed'").fetchall()
    assert failed == [], "every month of the exam ran"
    drift = {r[0] for r in conn.execute("SELECT DISTINCT period FROM monitoring.drift")}
    served = {r[0] for r in conn.execute("SELECT DISTINCT listed FROM serving.predictions")}
    assert served, "the investor sent the listings of the exam"
    assert served <= drift, "every month with predictions has its drift"

    found = calibrate.exam(conn)
    committed = json.loads((ROOT / calibrate.EXAM).read_text())["alerts"]
    assert found == committed, "run 'make calibrate' and commit reports/thresholds"
    document = (ROOT / calibrate.DOCUMENT).read_text()
    assert calibrate.published(
        document, calibrate.EXAM_BEGIN, calibrate.EXAM_END
    ) == calibrate.exam_table(found)
