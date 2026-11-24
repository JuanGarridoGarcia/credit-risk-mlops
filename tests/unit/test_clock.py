"""T17.1 to T17.3: retraining cadence (D-106), the alert of a failed flow (D-108) and the
simulated clock kept out of the system (D-107), approved by Juan on 2026-11-24.

No Docker: the failed flow runs on a temporary Prefect server. The clock itself, with
Postgres, MLflow and the Prefect server of docker compose, is tested in
``tests/integration/test_clock.py`` (T17.4 to T17.8).
"""

import re
from datetime import date
from pathlib import Path

import pytest
from prefect import task
from prefect.testing.utilities import prefect_test_harness

import credit_risk
from credit_risk import alerts, flows


# T17.1
def test_the_cadence_retrains_in_its_months_only() -> None:
    year = [date(2014, m, 1) for m in range(1, 13)]

    quarterly = [d.month for d in year if flows.retrains(d, "quarterly")]
    assert quarterly == [1, 4, 7, 10]
    assert flows.CADENCE == "quarterly"
    assert [d.month for d in year if flows.retrains(d)] == quarterly
    assert all(flows.retrains(d, "monthly") for d in year)
    assert [d.month for d in year if flows.retrains(d, "yearly")] == [1]
    with pytest.raises(ValueError, match="unknown cadence 'weekly'"):
        flows.retrains(year[0], "weekly")


# T17.2
def test_a_failed_flow_records_one_alert_with_its_month_task_and_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @task(name="load")
    def broken_load(period: str, paths: flows.Paths) -> int:
        raise FileNotFoundError(f"no delivery for {period} in the landing folder")

    recorded: list[alerts.Alert] = []
    monkeypatch.setattr(flows, "load_task", broken_load)
    monkeypatch.setattr(alerts, "record", recorded.append)

    with prefect_test_harness():
        state = flows.monthly("2014-02", return_state=True)

    assert state.is_failed()
    assert len(recorded) == 1
    alert = recorded[0]
    assert alert.kind == "flow_failed"
    assert alert.severity == "error"
    assert alert.flow == flows.FLOW
    assert alert.period == date(2014, 2, 1)
    assert alert.task == "load"
    assert "no delivery for 2014-02" in alert.message
    assert alert.details["flow_run"] == str(state.state_details.flow_run_id)


# T17.3
def test_system_code_never_touches_the_clock_schema() -> None:
    # The installed package, as in T1.11, so the test also works in the image.
    package = Path(credit_risk.__file__).parent
    offenders = [
        str(path)
        for path in package.rglob("*")
        if path.is_file()
        and path.suffix in {".py", ".sql"}
        and "simulator" not in path.relative_to(package).parts
        and re.search(r"\bsim\.\w", path.read_text())
    ]
    assert not offenders
