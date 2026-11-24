"""T8.3 (unit part): no run is logged without its required fields (D-079)."""

import dataclasses
import math

import pytest

from credit_risk import tracking
from credit_risk.tracking import Interval, MissingFieldError, RunRecord, check


def _record(**changes: object) -> RunRecord:
    record = RunRecord(
        experiment="pd",
        name="test",
        commit="abc123",
        snapshot="f" * 64,
        seed=7,
        versions=tracking.library_versions(),
        metrics={"auc": Interval(0.68, 0.65, 0.70)},
    )
    return dataclasses.replace(record, **changes)  # type: ignore[arg-type]


# T8.3
def test_a_complete_record_passes() -> None:
    check(_record())


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"commit": ""}, "commit"),
        ({"snapshot": ""}, "snapshot"),
        ({"seed": None}, "seed"),
        ({"versions": {}}, "versions"),
        ({"versions": {"python": "3.12"}}, "versions"),
        ({"metrics": {}}, "metrics"),
        ({"metrics": {"auc": Interval(0.68, math.nan, 0.70)}}, "interval of metric auc"),
        ({"metrics": {"auc": Interval(0.68, 0.70, 0.65)}}, "interval of metric auc"),
    ],
)
def test_a_missing_field_is_refused_by_name(changes: dict[str, object], field: str) -> None:
    with pytest.raises(MissingFieldError, match=field):
        check(_record(**changes))


def test_log_run_checks_before_writing_anything(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []
    monkeypatch.setattr("mlflow.set_experiment", lambda name: called.append(name))
    with pytest.raises(MissingFieldError, match="seed"):
        tracking.log_run(_record(seed=None))
    assert called == []
