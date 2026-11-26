"""Which measurements of a month become alerts, and how serious (D-147, D-149, D-156).

The rules live here, in the flow, not in Grafana (D-147): they are tested like the rest,
run inside the simulated clock, and the triggered retraining of 6.3 reads the same
alerts. Grafana only shows the measurements and delivers the alerts of ``ops.alerts``.

The layers of D-149:

- the drift of an input variable never alerts; the dashboard shows it, to explain;
- the drift of a prediction (PD, LGD, expected loss rate) above its threshold is a
  ``prediction_drift`` warning: the models are seeing another population;
- an early warning whose whole interval is above its threshold is an ``early_warning``
  warning: more first-year defaults than expected, for sure;
- a matured cohort clearly worse than the champion's validation, or with an LGD level
  error above its threshold, is a ``performance_drop`` error;
- a new LGD whose level correction is above its threshold is an ``lgd_level_shift``
  warning; its promotion goes on as the rules say (D-151).

A value equal to its threshold does not alert: only above. Every alert carries a
``signal`` (what was measured, on which models) so that a month run again records it
once (D-145).
"""

import math
import tomllib
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from importlib.resources import files
from pathlib import Path
from typing import Any, Final

from credit_risk.alerts import Alert
from credit_risk.monitoring.outcomes import ALL

#: The predictions whose drift alerts, as named in the drift rows.
PREDICTIONS: Final = ("pd", "lgd", "el_rate")
#: What each value may be: (lowest, highest), both included.
RANGES: Final[Mapping[str, tuple[float, float]]] = {
    "psi": (0.01, 5.0),
    "ratio_low": (0.5, 5.0),
    "auc_margin": (0.0, 0.2),
    "calibration_margin": (0.0, 0.2),
    "lgd_level": (0.01, 1.0),
    "shift": (0.01, 1.0),
}
#: Every section of the file and the values it must hold.
SECTIONS: Final[Mapping[str, tuple[str, ...]]] = {
    **{f"prediction_drift.{p}": ("psi",) for p in PREDICTIONS},
    "early_warning": ("ratio_low",),
    "performance": ("auc_margin", "calibration_margin", "lgd_level"),
    "lgd_level_shift": ("shift",),
}


class ThresholdError(ValueError):
    """The thresholds file is incomplete or holds an impossible value."""


@dataclass(frozen=True)
class Thresholds:
    psi: Mapping[str, float]
    ratio_low: float
    auc_margin: float
    calibration_margin: float
    lgd_level: float
    lgd_shift: float
    reasons: Mapping[str, str]


def _section(document: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    found: Any = document
    for part in name.split("."):
        found = found.get(part) if isinstance(found, Mapping) else None
    if not isinstance(found, Mapping):
        raise ThresholdError(f"section [{name}] is missing")
    return found


def parse(document: Mapping[str, Any]) -> Thresholds:
    """Check every section and value of a parsed thresholds file (T29.1)."""
    values: dict[str, dict[str, float]] = {}
    reasons: dict[str, str] = {}
    for name, keys in SECTIONS.items():
        section = _section(document, name)
        reason = section.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ThresholdError(f"[{name}] has no written reason")
        reasons[name] = reason.strip()
        values[name] = {}
        for key in keys:
            value = section.get(key)
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise ThresholdError(f"[{name}] {key} is missing or not a number")
            low, high = RANGES[key]
            if not (low <= value <= high) or math.isnan(value):
                raise ThresholdError(f"[{name}] {key} = {value} is outside [{low}, {high}]")
            values[name][key] = float(value)
    performance = values["performance"]
    return Thresholds(
        psi={p: values[f"prediction_drift.{p}"]["psi"] for p in PREDICTIONS},
        ratio_low=values["early_warning"]["ratio_low"],
        auc_margin=performance["auc_margin"],
        calibration_margin=performance["calibration_margin"],
        lgd_level=performance["lgd_level"],
        lgd_shift=values["lgd_level_shift"]["shift"],
        reasons=reasons,
    )


def load(path: Path | None = None) -> Thresholds:
    """The thresholds of ``path``, by default the file shipped with the package."""
    text = (
        path.read_text()
        if path is not None
        else files("credit_risk.monitoring").joinpath("thresholds.toml").read_text()
    )
    try:
        document = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise ThresholdError(f"the thresholds file does not parse: {error}") from error
    return parse(document)


# ---------------------------------------------------------------- the rules


def drift_alerts(period: date, rows: Iterable[Mapping[str, Any]], t: Thresholds) -> list[Alert]:
    """A ``prediction_drift`` warning for every prediction above its threshold."""
    out = []
    for row in rows:
        subject = row["subject"]
        if subject not in t.psi or row["psi"] <= t.psi[subject]:
            continue  # an input variable, or within its threshold
        pair = f"pd {row['pd_version']}, lgd {row['lgd_version']}"
        out.append(
            Alert(
                "prediction_drift",
                f"{period:%Y-%m}: PSI of {subject} {row['psi']:.3f} above {t.psi[subject]} "
                f"({pair})",
                period=period,
                details={
                    "signal": f"{subject}|pd={row['pd_version']}|lgd={row['lgd_version']}",
                    "subject": subject,
                    "psi": row["psi"],
                    "threshold": t.psi[subject],
                    "pd_version": row["pd_version"],
                    "lgd_version": row["lgd_version"],
                },
            )
        )
    return out


def early_warning_alerts(
    period: date, rows: Iterable[Mapping[str, Any]], t: Thresholds
) -> list[Alert]:
    """An ``early_warning`` warning for every result whose whole interval is above."""
    out = []
    for row in rows:
        if row["ratio_low"] <= t.ratio_low:
            continue
        cohort = row["cohort"]
        out.append(
            Alert(
                "early_warning",
                f"{period:%Y-%m}: cohort {cohort:%Y-%m}, {row['term']} months, defaulted "
                f"{row['ratio']:.2f} times the expected in its first year "
                f"(95% interval {row['ratio_low']:.2f} to {row['ratio_high']:.2f}, pd "
                f"{row['pd_version']})",
                period=period,
                details={
                    "signal": f"term={row['term']}|pd={row['pd_version']}|cohort={cohort:%Y-%m}",
                    "cohort": f"{cohort:%Y-%m}",
                    "term": row["term"],
                    "ratio": row["ratio"],
                    "ratio_low": row["ratio_low"],
                    "ratio_high": row["ratio_high"],
                    "threshold": t.ratio_low,
                    "pd_version": row["pd_version"],
                },
            )
        )
    return out


def _drop(
    period: date, row: Mapping[str, Any], metric: str, text: str, detail: Mapping[str, Any]
) -> Alert:
    cohort = row["cohort"]
    pair = f"pd {row['pd_version']}, lgd {row['lgd_version']}"
    return Alert(
        "performance_drop",
        f"{period:%Y-%m}: cohort {cohort:%Y-%m}, {row['term']} months: {text} ({pair})",
        period=period,
        details={
            "signal": f"{metric}|term={row['term']}|pd={row['pd_version']}|"
            f"lgd={row['lgd_version']}|cohort={cohort:%Y-%m}",
            "metric": metric,
            "cohort": f"{cohort:%Y-%m}",
            "term": row["term"],
            "pd_version": row["pd_version"],
            "lgd_version": row["lgd_version"],
            **detail,
        },
    )


def performance_alerts(
    period: date,
    rows: Iterable[Mapping[str, Any]],
    t: Thresholds,
    validation_auc: Callable[[str], float | None],
) -> list[Alert]:
    """A ``performance_drop`` error for every matured cohort clearly worse (whole cohort).

    ``validation_auc`` gives the validation AUC of a PD version (from its run).
    """
    out = []
    for row in rows:
        if row["segment"] != ALL:
            continue  # the rule is on the whole cohort; grades are for the dashboard
        reference = validation_auc(row["pd_version"])
        high = row.get("auc_high")
        if reference is not None and high is not None and high < reference - t.auc_margin:
            out.append(
                _drop(
                    period,
                    row,
                    "auc",
                    f"AUC {row['auc']:.3f} (up to {high:.3f}) below the validation "
                    f"{reference:.3f} minus {t.auc_margin}",
                    {
                        "auc": row["auc"],
                        "auc_high": high,
                        "validation_auc": reference,
                        "margin": t.auc_margin,
                    },
                )
            )
        low = row.get("calibration_low")
        if low is not None and low > t.calibration_margin:
            out.append(
                _drop(
                    period,
                    row,
                    "calibration_error",
                    f"calibration error {row['calibration_error']:.3f} (at least {low:.3f}) "
                    f"above {t.calibration_margin}",
                    {
                        "calibration_error": row["calibration_error"],
                        "calibration_low": low,
                        "margin": t.calibration_margin,
                    },
                )
            )
        level = row.get("lgd_level")
        if level is not None and abs(level) > t.lgd_level:
            out.append(
                _drop(
                    period,
                    row,
                    "lgd_level",
                    f"LGD level error {level:+.3f} beyond {t.lgd_level}",
                    {"lgd_level": level, "threshold": t.lgd_level},
                )
            )
    return out


def level_shift_alert(
    name: str, version: str, shift: float, promoted: bool, period: date | None, t: Thresholds
) -> Alert | None:
    """An ``lgd_level_shift`` warning when a new LGD needed a correction above (D-151)."""
    if abs(shift) <= t.lgd_shift:
        return None
    verdict = "promoted" if promoted else "not promoted"
    return Alert(
        "lgd_level_shift",
        f"{name} version {version} needed a level correction of {shift:+.3f}, beyond "
        f"{t.lgd_shift}; {verdict} by the usual rules",
        period=period,
        model=name,
        version=version,
        details={"shift": shift, "threshold": t.lgd_shift, "promoted": promoted},
    )
