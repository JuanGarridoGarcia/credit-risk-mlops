"""Model registry: storing models, automatic promotion and rollback (D-082, D-090).

A model is stored as a file in the artefacts of its training run and registered in the
MLflow model registry under ``pd`` or ``lgd``. The alias ``champion`` names the model in
use. :func:`promote` is the only way the alias moves forward, and it always runs every
rule itself: there is no option to skip one (D-082). Each promotion writes on the new
version the champion it replaced, so :func:`rollback` can walk back the chain, because
the registry alias keeps only the current champion (D-090).

Rules for a challenger against the champion (the grade-only baseline when there is no
champion yet, D-090):

1. better by more than the noise: paired bootstrap of the AUC for the PD, of the RMSE
   for the LGD (D-075);
2. not clearly worse in any key segment (D-081);
3. signs of the logistic regression, constraints of LightGBM (D-080);
4. the behavioural battery, for the PD (D-086).
"""

import argparse
import json
import logging
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, Literal

import joblib
import mlflow
import numpy as np
import polars as pl
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException

from credit_risk import battery
from credit_risk.compare import (
    LGD_MARGINS,
    PD_MARGINS,
    paired_bootstrap,
    segment_check,
    segments,
    segments_pass,
)
from credit_risk.features import build_features
from credit_risk.model import check_signs, monotone_constraints
from credit_risk.snapshot import LABEL, LGD

log = logging.getLogger(__name__)

Target = Literal["pd", "lgd"]
CHAMPION: Final = "champion"
PREVIOUS: Final = "previous_champion"
MODEL_FILE: Final = "model.joblib"
MODEL_DIR: Final = "model"


class RegistryError(RuntimeError):
    """A registry operation cannot be done as asked."""


# ---------------------------------------------------------------- storing models


def log_model(run_id: str, model: object) -> str:
    """Store ``model`` in the artefacts of ``run_id``; return its address."""
    client = MlflowClient()
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / MODEL_FILE
        joblib.dump(model, path)
        client.log_artifact(run_id, str(path), artifact_path=MODEL_DIR)
    return f"{client.get_run(run_id).info.artifact_uri}/{MODEL_DIR}"


def register(name: str, run_id: str, source: str) -> str:
    """Register the model at ``source`` as a new version of ``name``; return the version."""
    client = MlflowClient()
    try:
        client.create_registered_model(name)
    except MlflowException as error:
        if error.error_code != "RESOURCE_ALREADY_EXISTS":
            raise
    return str(client.create_model_version(name, source, run_id=run_id).version)


def load(name: str, version: str) -> Any:
    """Load a registered model version.

    The file is a pickle: it is only ever read from this project's own registry.
    """
    source = MlflowClient().get_model_version(name, version).source
    folder = mlflow.artifacts.download_artifacts(artifact_uri=source)
    return joblib.load(Path(folder) / MODEL_FILE)


def champion(name: str) -> str | None:
    """The version the alias ``champion`` points to, or None."""
    try:
        return str(MlflowClient().get_model_version_by_alias(name, CHAMPION).version)
    except MlflowException:
        return None


# ---------------------------------------------------------------- the rules


@dataclass
class Verdict:
    """Outcome of the rules for one challenger, with the evidence of each."""

    rules: dict[str, bool] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return bool(self.rules) and all(self.rules.values())

    @property
    def reasons(self) -> list[str]:
        return [rule for rule, ok in self.rules.items() if not ok]


def signs_hold(model: Any) -> bool:
    """D-080 on any model: signs of a linear model, constraints of LightGBM."""
    estimator = getattr(model, "estimator", None)
    if estimator is None:
        return True
    if hasattr(estimator, "coef_") and hasattr(model, "prepare"):
        return all(check_signs(model).values())
    if hasattr(estimator, "booster_"):
        expected = monotone_constraints(model.prepare)
        return list(estimator.get_params()["monotone_constraints"]) == expected
    return True


def _comparison(c: Any) -> dict[str, Any]:
    return {"metric": c.metric, "new": c.new, "current": c.current, "low": c.low, "high": c.high}


def judge(
    target: Target,
    challenger: Any,
    current: Any,
    validation: pl.DataFrame,
    *,
    seed: int = 0,
    resamples: int = 1_000,
    run_battery: Callable[[Any, pl.DataFrame], battery.BatteryResult] = battery.run,
) -> Verdict:
    """Apply every rule to ``challenger`` against ``current`` on validation listings.

    ``validation`` holds listing columns plus the label (and ``lgd`` for the LGD). Only
    the terms both models cover are compared.
    """
    verdict = Verdict()
    features = build_features(validation)
    common = tuple(sorted(set(challenger.covered_terms) & set(current.covered_terms)))
    keep = features["term"].is_in(list(common)).to_numpy()
    if target == "pd":
        y = validation[LABEL].cast(pl.Float64).to_numpy()[keep]
        new = challenger.predict_pd(features).to_numpy()[keep]
        old = current.predict_pd(features).to_numpy()[keep]
        metric, events, stratify, margins = "auc", y, True, PD_MARGINS
        metrics: tuple[str, ...] = ("auc", "calibration_error")
    else:
        y = validation[LGD].cast(pl.Float64).to_numpy()[keep]
        new = challenger.predict_lgd(features).to_numpy()[keep]
        old = current.predict_lgd(features).to_numpy()[keep]
        metric, events, stratify, margins = "rmse", np.ones_like(y), False, LGD_MARGINS
        metrics = ("calibration_error",)
    overall = paired_bootstrap(
        y, new, old, metric, seed=seed, resamples=resamples, stratify=stratify
    )
    verdict.rules["better than the noise"] = overall.better
    verdict.evidence["overall"] = _comparison(overall)
    verdict.evidence["improvements"] = overall.improvements.tolist()
    verdict.metrics.update(
        {f"{metric}.new": overall.new, f"{metric}.current": overall.current,
         f"{metric}.improvement.low": overall.low, f"{metric}.improvement.high": overall.high}
    )  # fmt: skip
    masks = segments(validation.filter(pl.Series(keep)), events, common)
    results = segment_check(
        y, new, old, masks, metrics, margins=margins, seed=seed, resamples=resamples,
        stratify=stratify,
    )  # fmt: skip
    verdict.rules["no key segment clearly worse"] = segments_pass(results)
    verdict.evidence["segments"] = [
        {
            "segment": r.segment,
            **_comparison(r.comparison),
            "margin": r.margin,
            "blocking": r.blocking,
        }
        for r in results
    ]
    if target == "pd":
        # D-080 is about the PD; the LGD has no fixed directions.
        verdict.rules["signs and constraints"] = signs_hold(challenger)
        checks = run_battery(challenger, validation)
        verdict.rules["behavioural battery"] = checks.passed
        verdict.evidence["battery"] = {"checks": checks.checks, "details": checks.details}
    return verdict


# ---------------------------------------------------------------- promotion and rollback


def _record(run_id: str, verdict: Verdict, outcome: str) -> None:
    client = MlflowClient()
    client.set_tag(run_id, "promotion.outcome", outcome)
    client.set_tag(run_id, "promotion.reasons", ", ".join(verdict.reasons) or "none")
    for rule, ok in verdict.rules.items():
        client.set_tag(run_id, f"rule.{rule}", str(ok))
    for name, value in verdict.metrics.items():
        client.log_metric(run_id, f"promotion.{name}", value)
    client.log_dict(run_id, verdict.evidence, "promotion/evidence.json")


def _move(name: str, version: str, previous: str | None, event: str) -> None:
    client = MlflowClient()
    client.set_registered_model_alias(name, CHAMPION, version)
    now = datetime.now(UTC).isoformat(timespec="seconds")
    if event == "promoted":
        client.set_model_version_tag(name, version, PREVIOUS, previous or "none")
        client.set_model_version_tag(name, version, "promoted_at", now)
    # The alert (D-082): a WARNING that monitoring picks up (Grafana in F6).
    log.warning("champion %s %s: %s -> %s at %s", name, event, previous or "none", version, now)


def promote(
    name: str,
    version: str,
    validation: pl.DataFrame,
    *,
    target: Target,
    baseline_version: str | None = None,
    seed: int = 0,
    resamples: int = 1_000,
) -> Verdict:
    """Make ``version`` the champion if it passes every rule against the current one.

    With no champion yet, the challenger is judged against ``baseline_version``; if it
    fails, the baseline becomes the champion (D-090). The verdict and its evidence are
    stored in the challenger's run whatever the outcome.
    """
    client = MlflowClient()
    current_version = champion(name)
    against = current_version or baseline_version
    if against is None:
        raise RegistryError(f"no champion of {name} and no baseline to compare with")
    verdict = judge(
        target, load(name, version), load(name, against), validation, seed=seed,
        resamples=resamples,
    )  # fmt: skip
    run_id = str(client.get_model_version(name, version).run_id)
    if verdict.passed:
        _record(run_id, verdict, "promoted")
        _move(name, version, current_version, "promoted")
    else:
        _record(run_id, verdict, "rejected")
        log.info("%s version %s rejected: %s", name, version, ", ".join(verdict.reasons))
        if current_version is None and baseline_version is not None:
            _move(name, baseline_version, None, "promoted")
    return verdict


def rollback(name: str) -> tuple[str, str]:
    """Point ``champion`` back to the champion before the current one."""
    client = MlflowClient()
    current = champion(name)
    if current is None:
        raise RegistryError(f"{name} has no champion")
    previous = client.get_model_version(name, current).tags.get(PREVIOUS)
    if previous is None or previous == "none":
        raise RegistryError(f"{name} version {current} has no previous champion")
    client.set_model_version_tag(name, current, "rolled_back_at", datetime.now(UTC).isoformat())
    _move(name, previous, current, "rolled back")
    return current, previous


def main(argv: list[str] | None = None) -> None:
    """``python -m credit_risk.registry rollback pd``."""
    parser = argparse.ArgumentParser(description="Model registry (D-082).")
    parser.add_argument("action", choices=["rollback", "champion"])
    parser.add_argument("model", choices=["pd", "lgd"])
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if args.action == "rollback":
        current, previous = rollback(args.model)
        print(f"champion {args.model}: v{current} -> v{previous}")
    else:
        print(json.dumps({"model": args.model, "champion": champion(args.model)}))


if __name__ == "__main__":
    main()
