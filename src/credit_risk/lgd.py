"""The LGD training procedure (D-087): the PD machinery applied to loss given default.

Only defaults with a known LGD enter (D-088): the rows of each split whose ``lgd`` is
filled. Candidates: a ridge regression on the linear preparation and a LightGBM
regressor, tuned on the inner time split (D-073) with the same budgets as the PD
(D-074), RMSE as the score. LightGBM is chosen only if it beats the ridge by more than
the noise (D-068, D-075); the chosen one must still beat the mean LGD by grade (D-005),
the baseline, to become champion (D-090). Predictions are clipped to [0, 1].
"""

import dataclasses
import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Final

import numpy as np
import polars as pl
from lightgbm import LGBMRegressor, early_stopping
from sklearn.linear_model import Ridge

from credit_risk.compare import Comparison, choose, paired_bootstrap, rmse
from credit_risk.model import LGDModel, Matrix, Prepare
from credit_risk.snapshot import LGD, SPLIT
from credit_risk.train import (
    EARLY_STOPPING_ROUNDS,
    LIGHTGBM_TRIALS,
    MAX_TREES,
    SEED,
    THREADS,
    Search,
    Seen,
    inner_split,
)

log = logging.getLogger(__name__)

RIDGE_GRID: Final = tuple(float(a) for a in np.logspace(-3, 3, 20))


def lgd_rows(frame: pl.DataFrame) -> pl.DataFrame:
    """The rows with a known LGD (D-088)."""
    return frame.filter(pl.col(LGD).is_not_null())


def _y(frame: pl.DataFrame) -> Matrix:
    return frame[LGD].cast(pl.Float64).to_numpy()


def _record(seen: Seen | None, *frames: pl.DataFrame) -> None:
    if seen is not None:
        for frame in frames:
            seen(frame["id"])


def fit_baseline(train: pl.DataFrame, terms: tuple[int, ...]) -> LGDModel:
    """D-005: the mean LGD of each grade in training."""
    means = train.group_by("grade").agg(pl.col(LGD).mean()).rows()
    return LGDModel(
        "baseline",
        terms,
        grade_means={str(g): float(m) for g, m in means},
        overall_mean=float(train[LGD].mean() or 0.0),  # type: ignore[arg-type]
    )


def fit_level(model: LGDModel, validation: pl.DataFrame) -> LGDModel:
    """D-094: the same model with its level moved to the mean LGD observed in validation.

    The LGD rises from one listing year to the next, so a model fitted on every year of
    training lags the most recent ones. Like Platt scaling for the PD (D-076), the
    correction is fitted on validation, the most recent period, and is one number: the
    observed mean minus the mean predicted. Ranking within the period is unchanged.
    """
    uncorrected = dataclasses.replace(model, shift=0.0)
    gap = float(np.mean(_y(validation)) - np.mean(uncorrected.predict_lgd(validation).to_numpy()))
    return dataclasses.replace(model, shift=gap)


def fit_ridge(train: pl.DataFrame, alpha: float, terms: tuple[int, ...]) -> LGDModel:
    prepare = Prepare("linear").fit(train)
    estimator = Ridge(alpha=alpha).fit(prepare.transform(train), _y(train))
    return LGDModel("ridge", terms, prepare, estimator, params={"alpha": alpha})


def fit_lightgbm(
    train: pl.DataFrame,
    params: dict[str, Any],
    seed: int,
    n_estimators: int,
    terms: tuple[int, ...],
    stop_on: pl.DataFrame | None = None,
) -> LGDModel:
    prepare = Prepare("trees").fit(train)
    estimator = LGBMRegressor(
        objective="regression",
        n_estimators=n_estimators,
        subsample_freq=1,
        random_state=seed,
        deterministic=True,
        force_row_wise=True,
        n_jobs=THREADS,
        verbose=-1,
        **params,
    )
    fit: dict[str, Any] = {"categorical_feature": prepare.categorical_indices()}
    if stop_on is not None:
        fit["eval_X"] = prepare.transform(stop_on)
        fit["eval_y"] = _y(stop_on)
        fit["eval_metric"] = "l2"
        fit["callbacks"] = [early_stopping(EARLY_STOPPING_ROUNDS, verbose=False)]
    estimator.fit(prepare.transform(train), _y(train), **fit)
    return LGDModel(
        "lightgbm", terms, prepare, estimator, params={**params, "n_estimators": n_estimators}
    )


def _rmse(model: LGDModel, frame: pl.DataFrame) -> float:
    return rmse(_y(frame), model.predict_lgd(frame).to_numpy())


def search_ridge(
    inner_train: pl.DataFrame,
    inner_validation: pl.DataFrame,
    terms: tuple[int, ...],
    seen: Seen | None = None,
) -> Search:
    trials = []
    for alpha in RIDGE_GRID:
        _record(seen, inner_train, inner_validation)
        model = fit_ridge(inner_train, alpha, terms)
        trials.append(({"alpha": alpha}, -_rmse(model, inner_validation)))
    params, score = max(trials, key=lambda t: t[1])
    return Search(params, score, trials)


def search_lightgbm(
    inner_train: pl.DataFrame,
    inner_validation: pl.DataFrame,
    seed: int,
    terms: tuple[int, ...],
    seen: Seen | None = None,
    trials: int = LIGHTGBM_TRIALS,
) -> Search:
    import optuna  # training only: not in the serve image (D-078)

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    done: list[tuple[dict[str, Any], float]] = []

    def objective(trial: optuna.Trial) -> float:
        params = {
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "num_leaves": trial.suggest_int("num_leaves", 4, 64, log=True),
            "min_child_samples": trial.suggest_int("min_child_samples", 20, 200, log=True),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "subsample": trial.suggest_float("subsample", 0.5, 1.0),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
        }
        _record(seen, inner_train, inner_validation)
        model = fit_lightgbm(inner_train, params, seed, MAX_TREES, terms, inner_validation)
        n = int(model.estimator.best_iteration_ or MAX_TREES)
        score = -_rmse(model, inner_validation)
        done.append(({**params, "n_estimators": n}, score))
        return score

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=seed))
    study.optimize(objective, n_trials=trials, n_jobs=1)
    params, score = done[study.best_trial.number]
    return Search(params, score, done)


@dataclass
class LGDTraining:
    cutoff: date
    seed: int
    covered_terms: tuple[int, ...]
    ridge: LGDModel
    lightgbm: LGDModel
    baseline: LGDModel
    chosen: LGDModel
    comparison: Comparison
    searches: dict[str, Search] = field(default_factory=dict)


def train_lgd(
    frame: pl.DataFrame,
    cutoff: date,
    terms: tuple[int, ...],
    seed: int = SEED,
    *,
    params: dict[str, dict[str, Any]] | None = None,
    seen: Seen | None = None,
    trials: int = LIGHTGBM_TRIALS,
) -> LGDTraining:
    """Run the LGD procedure on ``frame`` (from :func:`credit_risk.train.prepare_frame`,
    with the ``lgd`` column) for the terms the PD covers."""
    rows = lgd_rows(frame)
    train = rows.filter(pl.col(SPLIT) == "train")
    validation = rows.filter(pl.col(SPLIT) == "validation")
    searches: dict[str, Search] = {}
    if params is None:
        inner_train, inner_validation = inner_split(train, cutoff)
        searches["ridge"] = search_ridge(inner_train, inner_validation, terms, seen)
        searches["lightgbm"] = search_lightgbm(
            inner_train, inner_validation, seed, terms, seen, trials
        )
        params = {name: dict(s.params) for name, s in searches.items()}
    ridge = fit_ridge(train, params["ridge"]["alpha"], terms)
    lgbm_params = dict(params["lightgbm"])
    n_estimators = int(lgbm_params.pop("n_estimators"))
    lightgbm = fit_lightgbm(train, lgbm_params, seed, n_estimators, terms)
    baseline = fit_baseline(train, terms)
    covered = validation.filter(pl.col("term").is_in(list(terms)))
    # The level of every model, the baseline included, is set on validation (D-094).
    ridge, lightgbm, baseline = (fit_level(m, covered) for m in (ridge, lightgbm, baseline))
    log.info(
        "LGD level shifts fitted on validation: ridge %.4f, lightgbm %.4f, baseline %.4f",
        ridge.shift,
        lightgbm.shift,
        baseline.shift,
    )
    y = _y(covered)
    comparison = paired_bootstrap(
        y,
        lightgbm.predict_lgd(covered).to_numpy(),
        ridge.predict_lgd(covered).to_numpy(),
        "rmse",
        seed=seed,
        stratify=False,
    )
    chosen = lightgbm if choose(comparison) == "lightgbm" else ridge
    log.info(
        "LGD RMSE on validation: ridge %.4f, lightgbm %.4f, improvement [%.4f, %.4f]; chosen %s",
        comparison.current,
        comparison.new,
        comparison.low,
        comparison.high,
        chosen.name,
    )
    return LGDTraining(cutoff, seed, terms, ridge, lightgbm, baseline, chosen, comparison, searches)
