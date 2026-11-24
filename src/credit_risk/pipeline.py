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
from typing import Any, Final

import polars as pl
import psycopg

from credit_risk import registry
from credit_risk.compare import interval
from credit_risk.lgd import LGDTraining, lgd_rows, train_lgd
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
from credit_risk.train import SEED, PDTraining, Search, prepare_frame, train_pd

log = logging.getLogger(__name__)

EXPERIMENT: Final = {"pd": "pd", "lgd": "lgd"}


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


def _log_pd(
    context: Context, model: PDModel, training: PDTraining, validation: pl.DataFrame
) -> str:
    rows = validation.filter(pl.col("term").is_in(list(model.covered_terms)))
    y = rows[LABEL].cast(pl.Float64).to_numpy()
    p = model.predict_pd(rows).to_numpy()
    with tempfile.TemporaryDirectory() as folder:
        files = _searches_file(Path(folder), training.searches if model.name != "baseline" else {})
        run_id = log_run(
            RunRecord(
                experiment=EXPERIMENT["pd"],
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
                },
                files=files,
            )
        )
    registry.log_model(run_id, model)
    return run_id


def _log_lgd(
    context: Context, model: LGDModel, training: LGDTraining, validation: pl.DataFrame
) -> str:
    rows = validation.filter(pl.col("term").is_in(list(model.covered_terms)))
    y = rows[LGD].cast(pl.Float64).to_numpy()
    p = model.predict_lgd(rows).to_numpy()
    with tempfile.TemporaryDirectory() as folder:
        files = _searches_file(Path(folder), training.searches if model.name != "baseline" else {})
        run_id = log_run(
            RunRecord(
                experiment=EXPERIMENT["lgd"],
                name=f"lgd {model.name} {training.cutoff:%Y-%m}",
                commit=context.commit,
                snapshot=context.version,
                seed=context.seed,
                versions=library_versions(),
                metrics={
                    "rmse": _interval(y, p, "rmse", context.seed),
                    "calibration_error": _interval(y, p, "calibration_error", context.seed),
                },
                params=model.params,
                tags={
                    "model": model.name,
                    "cutoff": f"{training.cutoff:%Y-%m}",
                    "chosen": str(model is training.chosen),
                    "covered_terms": ",".join(map(str, model.covered_terms)),
                },
                files=files,
            )
        )
    registry.log_model(run_id, model)
    return run_id


def _register_and_promote(
    target: registry.Target,
    runs: dict[str, str],
    chosen: str,
    validation: pl.DataFrame,
    seed: int,
) -> registry.Verdict:
    def version_of(name: str) -> str:
        source = f"runs:/{runs[name]}/{registry.MODEL_DIR}"
        return registry.register(target, runs[name], source)

    challenger = version_of(chosen)
    baseline = version_of("baseline") if registry.champion(target) is None else None
    return registry.promote(target, challenger, validation, baseline_version=baseline, seed=seed)


def retrain(
    training_set: pl.DataFrame, cutoff: date, version: str, *, seed: int = SEED
) -> dict[str, registry.Verdict]:
    """Train, log, register and promote the PD and the LGD of one training set version."""
    context = Context(version, git_commit(), seed)
    frame = prepare_frame(training_set)
    validation_listings = training_set.filter(pl.col(SPLIT) == "validation")
    validation = frame.filter(pl.col(SPLIT) == "validation")

    pd_training = train_pd(frame, cutoff, seed)
    pd_runs = {
        m.name: _log_pd(context, m, pd_training, validation)
        for m in (pd_training.logistic, pd_training.lightgbm, pd_training.baseline)
    }
    verdicts = {
        "pd": _register_and_promote(
            "pd", pd_runs, pd_training.chosen.name, validation_listings, seed
        )
    }

    lgd_training = train_lgd(frame, cutoff, pd_training.covered_terms, seed)
    lgd_validation = lgd_rows(validation)
    lgd_runs = {
        m.name: _log_lgd(context, m, lgd_training, lgd_validation)
        for m in (lgd_training.ridge, lgd_training.lightgbm, lgd_training.baseline)
    }
    verdicts["lgd"] = _register_and_promote(
        "lgd", lgd_runs, lgd_training.chosen.name, lgd_rows(validation_listings), seed
    )
    return verdicts


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
