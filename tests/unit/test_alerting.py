"""T29.1 to T29.5: the rules that turn a month's measurements into alerts (D-147, D-149,
D-151, D-156); T33.1, unit part: the calibration study refuses data unknown at T0
(D-150); T33.3: the thresholds follow the written rules of the study. Approved by Juan on
2026-11-26.

The thresholds are read from the file shipped with the package, so these tests hold
whatever its values are; only the tests of the file itself build other files.
"""

import copy
import json
import tomllib
from datetime import date
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest

from credit_risk.alerts import KINDS
from credit_risk.monitoring import alerting, calibrate
from credit_risk.monitoring.outcomes import ALL

PERIOD = date(2015, 6, 1)
T = alerting.load()
ROOT = Path(__file__).resolve().parents[2]


def _document() -> dict[str, Any]:
    text = files("credit_risk.monitoring").joinpath("thresholds.toml").read_text()
    return tomllib.loads(text)


def _drift(subject: str, psi: float, kind: str = "numeric") -> dict[str, Any]:
    return {"subject": subject, "kind": kind, "psi": psi, "pd_version": "3", "lgd_version": "1"}


# T29.1
def test_the_thresholds_file_is_complete_in_range_and_explained(tmp_path: Path) -> None:
    assert set(T.psi) == {"pd", "lgd", "el_rate"}
    assert set(T.reasons) == set(alerting.SECTIONS)
    assert all(len(reason) > 40 for reason in T.reasons.values())
    for prediction, value in T.psi.items():
        low, high = alerting.RANGES["psi"]
        assert low <= value <= high, prediction
    # Every new kind of alert is known, with the severity of D-149.
    assert KINDS["prediction_drift"] == KINDS["early_warning"] == "warning"
    assert KINDS["performance_drop"] == "error"
    assert KINDS["lgd_level_shift"] == "warning"

    broken: list[tuple[str, Any]] = []
    missing = _document()
    del missing["early_warning"]
    broken.append(("section \\[early_warning\\] is missing", missing))
    no_value = _document()
    del no_value["prediction_drift"]["lgd"]["psi"]
    broken.append(("prediction_drift.lgd\\] psi is missing", no_value))
    outside = _document()
    outside["performance"]["lgd_level"] = 3.0
    broken.append(("lgd_level = 3.0 is outside", outside))
    unexplained = _document()
    unexplained["lgd_level_shift"]["reason"] = "  "
    broken.append(("has no written reason", unexplained))
    text = _document()
    text["early_warning"]["ratio_low"] = "1.0"
    broken.append(("ratio_low is missing or not a number", text))
    for message, document in broken:
        with pytest.raises(alerting.ThresholdError, match=message):
            alerting.parse(copy.deepcopy(document))
    bad = tmp_path / "thresholds.toml"
    bad.write_text("[early_warning\n")
    with pytest.raises(alerting.ThresholdError, match="does not parse"):
        alerting.load(bad)


# T29.2
def test_only_the_predictions_alert_and_only_above_their_threshold() -> None:
    rows = [
        _drift("int_rate", 9.0),
        _drift("initial_list_status", 2.4, "categorical"),
        _drift("pd", T.psi["pd"] + 0.001, "prediction"),
        _drift("lgd", T.psi["lgd"], "prediction"),  # equal: not above
        _drift("el_rate", T.psi["el_rate"] - 0.001, "prediction"),
    ]
    found = alerting.drift_alerts(PERIOD, rows, T)
    assert [a.kind for a in found] == ["prediction_drift"]
    alert = found[0]
    assert alert.severity == "warning"
    assert alert.period == PERIOD
    assert alert.details["subject"] == "pd"
    assert alert.details["signal"] == "pd|pd=3|lgd=1"
    assert alert.details["threshold"] == T.psi["pd"]
    assert "2015-06" in alert.message
    assert "pd 3, lgd 1" in alert.message


def _early(low: float, ratio: float, high: float) -> dict[str, Any]:
    return {"cohort": date(2014, 1, 1), "term": 36, "pd_version": "2", "ratio": ratio,
            "ratio_low": low, "ratio_high": high}  # fmt: skip


# T29.3
def test_the_early_warning_alerts_only_with_its_whole_interval_above() -> None:
    above = _early(T.ratio_low + 0.05, T.ratio_low + 0.3, T.ratio_low + 0.6)
    crossing = _early(T.ratio_low - 0.2, T.ratio_low + 0.5, T.ratio_low + 1.2)
    at = _early(T.ratio_low, T.ratio_low + 0.3, T.ratio_low + 0.6)
    found = alerting.early_warning_alerts(PERIOD, [above, crossing, at], T)
    assert len(found) == 1
    alert = found[0]
    assert (alert.kind, alert.severity) == ("early_warning", "warning")
    assert alert.details["signal"] == "term=36|pd=2|cohort=2014-01"
    assert alert.details["ratio_low"] == above["ratio_low"]
    assert "cohort 2014-01" in alert.message


def _matured(**metrics: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "cohort": date(2012, 1, 1), "term": 36, "pd_version": "2", "lgd_version": "1",
        "segment": ALL, "auc": 0.70, "auc_low": 0.68, "auc_high": 0.72,
        "calibration_error": 0.004, "calibration_low": 0.001, "calibration_high": 0.008,
        "lgd_level": 0.02,
    }  # fmt: skip
    return {**row, **metrics}


# T29.4
def test_a_matured_cohort_clearly_worse_than_validation_is_an_error() -> None:
    validation = 0.70

    def reference(version: str) -> float:
        assert version == "2"
        return validation

    worse_auc = _matured(auc=0.64, auc_low=0.62, auc_high=validation - T.auc_margin - 0.001)
    noisy_auc = _matured(auc=0.66, auc_low=0.62, auc_high=validation - T.auc_margin + 0.001)
    worse_calibration = _matured(
        calibration_error=0.03, calibration_low=T.calibration_margin + 0.001,
        calibration_high=0.05,
    )  # fmt: skip
    worse_lgd = _matured(lgd_level=-(T.lgd_level + 0.01))
    within = _matured()
    by_grade = _matured(segment="grade=E", auc=0.5, auc_low=None, auc_high=None)
    found = alerting.performance_alerts(
        PERIOD, [worse_auc, noisy_auc, worse_calibration, worse_lgd, within, by_grade],
        T, reference,
    )  # fmt: skip
    assert [a.details["metric"] for a in found] == ["auc", "calibration_error", "lgd_level"]
    assert {(a.kind, a.severity) for a in found} == {("performance_drop", "error")}
    assert found[0].details["validation_auc"] == validation
    assert found[0].details["signal"] == "auc|term=36|pd=2|lgd=1|cohort=2012-01"
    # A PD version with no logged validation AUC cannot be judged on its AUC.
    assert alerting.performance_alerts(PERIOD, [worse_auc], T, lambda _: None) == []


# T29.5
def test_a_large_level_correction_warns_and_leaves_the_verdict_alone() -> None:
    large = alerting.level_shift_alert("lgd", "4", T.lgd_shift + 0.01, True, PERIOD, T)
    assert large is not None
    assert (large.kind, large.severity) == ("lgd_level_shift", "warning")
    assert (large.model, large.version) == ("lgd", "4")
    assert large.details["promoted"] is True
    assert "promoted by the usual rules" in large.message
    negative = alerting.level_shift_alert("lgd", "5", -(T.lgd_shift + 0.01), False, None, T)
    assert negative is not None
    assert "not promoted" in negative.message
    assert alerting.level_shift_alert("lgd", "6", T.lgd_shift, True, PERIOD, T) is None
    assert alerting.level_shift_alert("lgd", "7", 0.05, True, PERIOD, T) is None


# T33.1 (unit part)
def test_the_study_refuses_anything_unknown_at_t0() -> None:
    calibrate.check_known("months", [date(2012, 1, 1), calibrate.REAL.last_known])
    with pytest.raises(calibrate.FutureDataError, match="2014-01 is after 2013-12"):
        calibrate.check_known("months", [date(2013, 6, 1), date(2014, 1, 1)])
    assert calibrate.REAL.last_known < calibrate.REAL.t0


# T33.3
def test_the_thresholds_follow_the_written_rules_of_the_study() -> None:
    found = json.loads((ROOT / calibrate.SUMMARY).read_text())
    document = _document()
    proposed = calibrate.propose(found)
    assert set(proposed) == set(alerting.SECTIONS)
    for name, values in proposed.items():
        section = alerting._section(document, name)
        assert {k: section[k] for k in values} == values, name
    # The rules themselves, on made-up studies: the first value of the grid not exceeded.
    fresh = [{"subject": p, "lag": 0, "max": 0.12} for p in alerting.PREDICTIONS]
    late = calibrate.FRESH_LAGS + 1
    old = [{"subject": p, "lag": late, "max": 9.0} for p in alerting.PREDICTIONS]
    made_up = {"prediction_drift": fresh + old, "level": [{"shift": -0.12}, {"shift": 0.03}]}
    rules = calibrate.propose(made_up)
    assert rules["prediction_drift.pd"] == {"psi": 0.15}, "an old reference does not count"
    assert rules["lgd_level_shift"] == {"shift": 0.15}, "above the largest, either sign"
    with pytest.raises(ValueError, match="above every value of the grid"):
        calibrate.propose({**made_up, "prediction_drift": [{**r, "max": 0.3} for r in fresh]})
