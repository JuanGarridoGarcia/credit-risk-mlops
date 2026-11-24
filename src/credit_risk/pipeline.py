"""One retraining, end to end: PD and LGD from a training set version to the registry.

``python -m credit_risk.pipeline 2014-01`` (``make train T=2014-01``):

1. reads the newest training set version of that cutoff, checking its checksum (D-061);
2. runs the PD procedure (:func:`credit_risk.train.train_pd`) and the LGD procedure
   (:func:`credit_risk.lgd.train_lgd`) on the terms the PD covers;
3. logs one MLflow run per model, with every required field (D-079) and the model file;
4. registers the chosen model of each target (and the baseline while there is no
   champion yet) and asks the registry to promote it (D-082, D-090).
"""

import argparse
import json
import logging
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
import psycopg
from mlflow import MlflowClient

from credit_risk import card, registry
from credit_risk.compare import interval
from credit_risk.lgd import LGDTraining, fit_level, lgd_rows, train_lgd
from credit_risk.model import MONOTONE, LGDModel, PDModel
from credit_risk.settings import Settings
from credit_risk.snapshot import (
    LABEL,
    LGD,
    ROOT,
    SPLIT,
    SnapshotError,
    git_commit,
    read_features,
)
from credit_risk.storage import LocalStore
from credit_risk.tracking import Interval, RunRecord, library_versions, log_run
from credit_risk.train import (
    LIGHTGBM_TRIALS,
    SEED,
    PDTraining,
    Search,
    prepare_frame,
    train_pd,
)

log = logging.getLogger(__name__)


def newest_version(conn: psycopg.Connection[Any], cutoff: date) -> str:
    row = conn.execute(
        "SELECT version FROM ops.training_sets WHERE cutoff = %s ORDER BY built_at DESC LIMIT 1",
        (cutoff,),
    ).fetchone()
    if row is None:
        raise SnapshotError(f"no training set at {cutoff:%Y-%m}: run make snapshot first")
    return str(row[0])


def _interval(y: Any, p: Any, metric: str, seed: int) -> Interval:
    value, low, high = interval(y, p, metric, seed=seed)
    return Interval(value, low, high)


def _searches_file(folder: Path, searches: dict[str, Search]) -> dict[str, Path]:
    if not searches:
        return {}
    path = folder / "search.json"
    path.write_text(
        json.dumps(
            {
                name: {"chosen": s.params, "score": s.score, "trials": s.trials}
                for name, s in searches.items()
            },
            indent=1,
            default=str,
        )
    )
    return {"search": path}


@dataclass(frozen=True)
class Context:
    version: str
    commit: str
    seed: int
    #: Put before the experiment and registered model names (``pd``, ``lgd``); tests use
    #: it to keep their runs and models apart.
    prefix: str = ""


def _counts(frame: pl.DataFrame, label: str, terms: tuple[int, ...]) -> dict[str, str]:
    """Loans and defaults of each split on the covered terms, recorded as run tags (D-095)."""
    rows = frame.filter(pl.col("term").is_in(list(terms)))
    tags: dict[str, str] = {}
    for split in ("train", "validation"):
        part = rows.filter(pl.col(SPLIT) == split)
        tags[f"rows.{split}"] = str(part.height)
        # Every row of the LGD is a default; for the PD the label says which.
        defaults = part.height if label == LGD else int(part[label].sum())
        tags[f"defaults.{split}"] = str(defaults)
    return tags


def _log_pd(
    context: Context,
    model: PDModel,
    training: PDTraining,
    validation: pl.DataFrame,
    counts: dict[str, str],
) -> str:
    rows = validation.filter(pl.col("term").is_in(list(model.covered_terms)))
    y = rows[LABEL].cast(pl.Float64).to_numpy()
    p = model.predict_pd(rows).to_numpy()
    with tempfile.TemporaryDirectory() as folder:
        files = _searches_file(Path(folder), training.searches if model.name != "baseline" else {})
        run_id = log_run(
            RunRecord(
                experiment=f"{context.prefix}pd",
                name=f"pd {model.name} {training.cutoff:%Y-%m}",
                commit=context.commit,
                snapshot=context.version,
                seed=context.seed,
                versions=library_versions(),
                metrics={
                    "auc": _interval(y, p, "auc", context.seed),
                    "brier": _interval(y, p, "brier", context.seed),
                },
                params={k: v for k, v in model.params.items() if k != "removed"},
                tags={
                    "model": model.name,
                    "cutoff": f"{training.cutoff:%Y-%m}",
                    "chosen": str(model is training.chosen),
                    "covered_terms": ",".join(map(str, model.covered_terms)),
                    "removed_features": ",".join(model.params.get("removed", ())) or "none",
                    "monotone": json.dumps(MONOTONE),
                    "platt": json.dumps(model.platt),
                    **counts,
                },
                files=files,
            )
        )
    registry.log_model(run_id, model)
    return run_id


#: Folds of validation for the honest calibration error of the LGD (D-076, D-094).
FOLDS = 5


def cross_fitted_lgd(model: LGDModel, rows: pl.DataFrame, seed: int) -> np.ndarray:
    """Predictions where each loan's level correction was fitted without that loan.

    The level is fitted on validation (D-094), so on validation the calibration error of
    the corrected model is zero by construction. As for Platt scaling (D-076), its honest
    value comes from cross-fitting: fit the correction on four fifths of validation and
    predict the other fifth, five times.
    """
    fold = np.random.default_rng(seed).permutation(rows.height) % FOLDS
    out = np.empty(rows.height)
    for k in range(FOLDS):
        held = fold == k
        fitted = fit_level(model, rows.filter(pl.Series(~held)))
        out[held] = fitted.predict_lgd(rows.filter(pl.Series(held))).to_numpy()
    return out


def _log_lgd(
    context: Context,
    model: LGDModel,
    training: LGDTraining,
    validation: pl.DataFrame,
    counts: dict[str, str],
) -> str:
    rows = validation.filter(pl.col("term").is_in(list(model.covered_terms)))
    y = rows[LGD].cast(pl.Float64).to_numpy()
    p = model.predict_lgd(rows).to_numpy()
    with tempfile.TemporaryDirectory() as folder:
        files = _searches_file(Path(folder), training.searches if model.name != "baseline" else {})
        run_id = log_run(
            RunRecord(
                experiment=f"{context.prefix}lgd",
                name=f"lgd {model.name} {training.cutoff:%Y-%m}",
                commit=context.commit,
                snapshot=context.version,
                seed=context.seed,
                versions=library_versions(),
                metrics={
                    "rmse": _interval(y, p, "rmse", context.seed),
                    "calibration_error": _interval(
                        y,
                        cross_fitted_lgd(model, rows, context.seed),
                        "calibration_error",
                        context.seed,
                    ),
                },
                params=model.params,
                tags={
                    "model": model.name,
                    "cutoff": f"{training.cutoff:%Y-%m}",
                    "chosen": str(model is training.chosen),
                    "covered_terms": ",".join(map(str, model.covered_terms)),
                    "level_shift": f"{model.shift:.6f}",
                    **counts,
                },
                files=files,
            )
        )
    registry.log_model(run_id, model)
    return run_id


@dataclass(frozen=True)
class Outcome:
    """What one retraining of one target left in the registry."""

    target: registry.Target
    #: Registered version of the chosen model (the challenger).
    version: str
    covered_terms: tuple[int, ...]
    verdict: registry.Verdict
    #: True when the key of D-101 was already registered and nothing was trained.
    reused: bool


def _register_and_promote(
    context: Context,
    target: registry.Target,
    runs: dict[str, str],
    chosen: str,
    validation: pl.DataFrame,
    existing: dict[str, str],
) -> tuple[str, registry.Verdict]:
    name = f"{context.prefix}{target}"

    def version_of(model: str, role: str) -> str:
        # A baseline registered by an attempt that stopped later is reused (D-101).
        if role in existing:
            return existing[role]
        source = f"runs:/{runs[model]}/{registry.MODEL_DIR}"
        tags = registry.key_tags(context.version, context.commit, role)
        return registry.register(name, runs[model], source, tags)

    # The baseline first: once the challenger is registered, everything it needs is too.
    baseline = version_of("baseline", "baseline") if registry.champion(name) is None else None
    challenger = version_of(chosen, "challenger")
    verdict = registry.promote(
        name, challenger, validation, target=target, baseline_version=baseline, seed=context.seed
    )
    # Every registered version gets its card, built once its evidence is stored (D-095).
    for version in (challenger, baseline):
        if version is not None:
            card.write(name, version, target, validation)
    return challenger, verdict


def _reuse(
    context: Context, target: registry.Target, version: str, validation: pl.DataFrame
) -> Outcome:
    """D-101: the key is registered, so nothing is trained; finish the promotion if needed."""
    name = f"{context.prefix}{target}"
    run_id = str(MlflowClient().get_model_version(name, version).run_id)
    tags = MlflowClient().get_run(run_id).data.tags
    terms = tuple(int(t) for t in tags["covered_terms"].split(",") if t)
    baseline = registry.trained(name, context.version, context.commit).get("baseline")
    verdict = registry.promote(
        name, version, validation, target=target, baseline_version=baseline, seed=context.seed
    )
    log.info("%s: training set %s at commit %s already trained", name, context.version[:12],
             context.commit[:12])  # fmt: skip
    return Outcome(target, version, terms, verdict, reused=True)


def _existing(context: Context, target: registry.Target) -> dict[str, str]:
    """Registered versions of this key; when unfinished, mark the runs left behind."""
    name = f"{context.prefix}{target}"
    existing = registry.trained(name, context.version, context.commit)
    if "challenger" not in existing:
        client = MlflowClient()
        keep = {str(client.get_model_version(name, v).run_id) for v in existing.values()}
        registry.fail_orphans(f"{context.prefix}{target}", context.version, context.commit, keep)
    return existing


def retrain_pd(
    training_set: pl.DataFrame,
    cutoff: date,
    version: str,
    *,
    seed: int = SEED,
    prefix: str = "",
    trials: int = LIGHTGBM_TRIALS,
) -> Outcome:
    """Train, log, register and promote the PD of one training set version (D-100).

    Idempotent (D-101): if this training set and this code commit already have a
    registered PD, nothing is trained again.
    """
    context = Context(version, git_commit(), seed, prefix)
    validation_listings = training_set.filter(pl.col(SPLIT) == "validation")
    existing = _existing(context, "pd")
    if "challenger" in existing:
        return _reuse(context, "pd", existing["challenger"], validation_listings)
    frame = prepare_frame(training_set)
    validation = frame.filter(pl.col(SPLIT) == "validation")
    training = train_pd(frame, cutoff, seed, trials=trials)
    counts = _counts(frame, LABEL, training.covered_terms)
    runs = {
        m.name: _log_pd(context, m, training, validation, counts)
        for m in (training.logistic, training.lightgbm, training.baseline)
    }
    challenger, verdict = _register_and_promote(
        context, "pd", runs, training.chosen.name, validation_listings, existing
    )
    return Outcome("pd", challenger, training.covered_terms, verdict, reused=False)


def retrain_lgd(
    training_set: pl.DataFrame,
    cutoff: date,
    version: str,
    covered_terms: tuple[int, ...],
    *,
    seed: int = SEED,
    prefix: str = "",
    trials: int = LIGHTGBM_TRIALS,
) -> Outcome:
    """Train, log, register and promote the LGD on the terms the PD covers (D-100, D-101)."""
    context = Context(version, git_commit(), seed, prefix)
    validation_listings = lgd_rows(training_set.filter(pl.col(SPLIT) == "validation"))
    existing = _existing(context, "lgd")
    if "challenger" in existing:
        return _reuse(context, "lgd", existing["challenger"], validation_listings)
    frame = prepare_frame(training_set)
    validation = lgd_rows(frame.filter(pl.col(SPLIT) == "validation"))
    training = train_lgd(frame, cutoff, covered_terms, seed, trials=trials)
    counts = _counts(lgd_rows(frame), LGD, training.covered_terms)
    runs = {
        m.name: _log_lgd(context, m, training, validation, counts)
        for m in (training.ridge, training.lightgbm, training.baseline)
    }
    challenger, verdict = _register_and_promote(
        context, "lgd", runs, training.chosen.name, validation_listings, existing
    )
    return Outcome("lgd", challenger, training.covered_terms, verdict, reused=False)


def retrain(
    training_set: pl.DataFrame,
    cutoff: date,
    version: str,
    *,
    seed: int = SEED,
    prefix: str = "",
    trials: int = LIGHTGBM_TRIALS,
) -> dict[str, registry.Verdict]:
    """Train, log, register and promote the PD and the LGD of one training set version."""
    options: dict[str, Any] = {"seed": seed, "prefix": prefix, "trials": trials}
    pd_ = retrain_pd(training_set, cutoff, version, **options)
    lgd = retrain_lgd(training_set, cutoff, version, pd_.covered_terms, **options)
    return {"pd": pd_.verdict, "lgd": lgd.verdict}


def main(argv: list[str] | None = None) -> None:  # pragma: no cover - thin command line
    """``python -m credit_risk.pipeline 2014-01``."""
    parser = argparse.ArgumentParser(description="Retrain the PD and the LGD (F3).")
    parser.add_argument("cutoff", help="YYYY-MM")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cutoff = date.fromisoformat(f"{args.cutoff}-01")
    with psycopg.connect(Settings().postgres_conninfo(), autocommit=True) as conn:
        version = newest_version(conn, cutoff)
        training_set = read_features(conn, LocalStore(args.root), version)
    for target, verdict in retrain(training_set, cutoff, version).items():
        outcome = "promoted" if verdict.passed else f"rejected ({', '.join(verdict.reasons)})"
        print(f"{target}: {outcome}")


if __name__ == "__main__":
    main()
