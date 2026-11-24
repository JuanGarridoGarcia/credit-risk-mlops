"""The PD training procedure of F3 (D-067): the same steps at every retraining.

1. Fixed features (:func:`credit_risk.features.build_features`) of the training set version.
2. Covered terms (D-070).
3. Hyperparameters of each candidate on an inner time split of the training rows (D-073):
   a grid of 20 values of ``C`` for the logistic regression, 50 seeded Optuna trials for
   LightGBM with early stopping (D-074). Validation rows never reach the search.
4. Each candidate refitted on all the training rows with its chosen values; the
   grade-only baseline (D-004) fitted too.
5. Platt calibration of each model on the validation rows of the covered terms (D-076);
   no refit on training plus validation (D-077).
6. LightGBM is chosen only if it beats the logistic regression by more than the noise
   (paired bootstrap of the AUC on validation, D-068, D-075).
"""

import logging
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Final

import numpy as np
import polars as pl
from lightgbm import LGBMClassifier, early_stopping
from sklearn.linear_model import LogisticRegression

from credit_risk.compare import Comparison, auc, choose, paired_bootstrap
from credit_risk.features import FEATURES, build_features
from credit_risk.model import (
    BASELINE_FEATURES,
    MONOTONE,
    Matrix,
    PDModel,
    Prepare,
    covered_terms,
    monotone_constraints,
)
from credit_risk.snapshot import LABEL, SPLIT, VALIDATION_MONTHS
from credit_risk.validation.contract import CHARGE_OFF_LAG_MONTHS

log = logging.getLogger(__name__)

SEED: Final = 2014
#: D-074: the budget is counted in trials, not in time.
LOGISTIC_GRID: Final = tuple(float(c) for c in np.logspace(-4, 2, 20))
LIGHTGBM_TRIALS: Final = 50
MAX_TREES: Final = 2_000
EARLY_STOPPING_ROUNDS: Final = 50
#: Fixed so that LightGBM gives the same trees on every run (T7.4).
THREADS: Final = 4

#: Columns of the training set kept next to the features.
KEEP: Final = ("id", "issue_d", LABEL, SPLIT)

Seen = Callable[[pl.Series], None]


def prepare_frame(training_set: pl.DataFrame) -> pl.DataFrame:
    """Fixed features of a training set version, with ``issue_d``, the label and the split."""
    features = build_features(training_set)
    return features.with_columns(training_set.select(*KEEP[1:]))


def _months_before(cutoff: date) -> pl.Expr:
    issue = pl.col("issue_d")
    return (
        cutoff.year * 12
        + cutoff.month
        - (issue.dt.year().cast(pl.Int32) * 12 + issue.dt.month().cast(pl.Int32))
    )


def inner_split(train: pl.DataFrame, cutoff: date) -> tuple[pl.DataFrame, pl.DataFrame]:
    """D-073: inside the training rows, the last 6 listing months of each term are the
    inner validation set; the earlier months are the inner training set.

    A 36-month loan is a training loan at T when listed at least 36 + 5 + 7 = 48 months
    before T (D-069), so its inner validation months are 48 to 53 months before T.
    """
    last = pl.col("term") + CHARGE_OFF_LAG_MONTHS + 2 * VALIDATION_MONTHS
    inner = _months_before(cutoff) <= last
    return train.filter(~inner), train.filter(inner)


def _y(frame: pl.DataFrame) -> Matrix:
    return frame[LABEL].cast(pl.Float64).to_numpy()


def _record(seen: Seen | None, *frames: pl.DataFrame) -> None:
    if seen is not None:
        for frame in frames:
            seen(frame["id"])


# ---------------------------------------------------------------- candidates


def fit_logistic(
    train: pl.DataFrame, c: float, features: tuple[str, ...] = FEATURES
) -> tuple[Prepare, LogisticRegression, tuple[str, ...]]:
    """Prepare (linear) and a logistic regression with regularisation strength ``c``,
    with the signs of D-080 enforced.

    While a feature of :data:`~credit_risk.model.MONOTONE` gets a coefficient with the
    wrong sign, the one with the largest wrong coefficient is removed and the model is
    fitted again (D-092). Returns the removed features too.
    """
    removed: list[str] = []
    while True:
        kept = tuple(f for f in features if f not in removed)
        prepare = Prepare("linear", kept).fit(train)
        estimator = LogisticRegression(C=c, max_iter=5_000)
        estimator.fit(prepare.transform(train), _y(train))
        wrong = _wrong_signs(prepare, estimator)
        if not wrong:
            return prepare, estimator, tuple(removed)
        removed.append(max(wrong, key=lambda f: wrong[f]))


def _wrong_signs(prepare: Prepare, estimator: LogisticRegression) -> dict[str, float]:
    """Features of D-080 whose coefficient has the wrong sign, with how wrong it is."""
    coef = np.asarray(estimator.coef_, dtype=np.float64).ravel()
    names = prepare.names
    return {
        f: float(-coef[names.index(f)] * sign)
        for f, sign in MONOTONE.items()
        if f in names and coef[names.index(f)] * sign < 0
    }


def _lightgbm(params: dict[str, Any], seed: int, n_estimators: int) -> LGBMClassifier:
    return LGBMClassifier(
        objective="binary",
        n_estimators=n_estimators,
        subsample_freq=1,
        random_state=seed,
        deterministic=True,
        force_row_wise=True,
        n_jobs=THREADS,
        verbose=-1,
        **params,
    )


def fit_lightgbm(
    train: pl.DataFrame,
    params: dict[str, Any],
    seed: int,
    n_estimators: int,
    stop_on: pl.DataFrame | None = None,
) -> tuple[Prepare, LGBMClassifier]:
    """Prepare (trees) and LightGBM with the monotone constraints of D-080.

    With ``stop_on``, trees are added until the AUC on it stops improving for
    :data:`EARLY_STOPPING_ROUNDS` rounds (used only inside the search, on inner rows).
    """
    prepare = Prepare("trees").fit(train)
    estimator = _lightgbm(
        {**params, "monotone_constraints": monotone_constraints(prepare)}, seed, n_estimators
    )
    fit: dict[str, Any] = {"categorical_feature": prepare.categorical_indices()}
    if stop_on is not None:
        fit["eval_X"] = prepare.transform(stop_on)
        fit["eval_y"] = _y(stop_on)
        fit["eval_metric"] = "auc"
        fit["callbacks"] = [early_stopping(EARLY_STOPPING_ROUNDS, verbose=False)]
    estimator.fit(prepare.transform(train), _y(train), **fit)
    return prepare, estimator


@dataclass(frozen=True)
class Search:
    """Result of a hyperparameter search: the chosen values and every trial."""

    params: dict[str, Any]
    score: float
    trials: list[tuple[dict[str, Any], float]]


def _inner_auc(prepare: Prepare, estimator: Any, frame: pl.DataFrame) -> float:
    proba = estimator.predict_proba(prepare.transform(frame))[:, 1]
    return auc(_y(frame), np.asarray(proba, dtype=np.float64))


def search_logistic(
    inner_train: pl.DataFrame, inner_validation: pl.DataFrame, seen: Seen | None = None
) -> Search:
    """D-074: every value of :data:`LOGISTIC_GRID`, scored by AUC on the inner validation."""
    trials = []
    for c in LOGISTIC_GRID:
        _record(seen, inner_train, inner_validation)
        prepare, estimator, _ = fit_logistic(inner_train, c)
        trials.append(({"C": c}, _inner_auc(prepare, estimator, inner_validation)))
    params, score = max(trials, key=lambda t: t[1])
    return Search(params, score, trials)


def search_lightgbm(
    inner_train: pl.DataFrame,
    inner_validation: pl.DataFrame,
    seed: int,
    seen: Seen | None = None,
    trials: int = LIGHTGBM_TRIALS,
) -> Search:
    """D-074: Optuna TPE, seeded, trials one after the other, early stopping on the inner
    validation. The number of trees found is kept as ``n_estimators``."""
    import optuna  # training only: not in the serve image (D-078)

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    done: list[tuple[dict[str, Any], float]] = []

    def objective(trial: optuna.Trial) -> float:
        params = {
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "num_leaves": trial.suggest_int("num_leaves", 4, 64, log=True),
            "min_child_samples": trial.suggest_int("min_child_samples", 20, 500, log=True),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "subsample": trial.suggest_float("subsample", 0.5, 1.0),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
        }
        _record(seen, inner_train, inner_validation)
        prepare, estimator = fit_lightgbm(
            inner_train, params, seed, MAX_TREES, stop_on=inner_validation
        )
        params["n_estimators"] = int(estimator.best_iteration_ or MAX_TREES)
        score = _inner_auc(prepare, estimator, inner_validation)
        done.append((params, score))
        return score

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=seed))
    study.optimize(objective, n_trials=trials, n_jobs=1)
    params, score = done[study.best_trial.number]
    return Search(params, score, done)


# ---------------------------------------------------------------- calibration


def fit_platt(raw: Matrix, y: Matrix) -> tuple[float, float]:
    """D-076: a one-feature logistic regression of the label on the raw log-odds."""
    platt = LogisticRegression(C=math.inf)
    platt.fit(raw.reshape(-1, 1), y)
    return float(platt.coef_[0, 0]), float(platt.intercept_[0])


def calibrate(model: PDModel, validation: pl.DataFrame) -> PDModel:
    """Fit the model's Platt calibrator on the validation rows of its covered terms."""
    rows = validation.filter(pl.col("term").is_in(list(model.covered_terms)))
    model.platt = fit_platt(model.raw(rows), _y(rows))
    return model


# ---------------------------------------------------------------- the procedure


@dataclass
class PDTraining:
    """Everything one run of the procedure produced."""

    cutoff: date
    seed: int
    covered_terms: tuple[int, ...]
    logistic: PDModel
    lightgbm: PDModel
    baseline: PDModel
    chosen: PDModel
    comparison: Comparison | None
    searches: dict[str, Search] = field(default_factory=dict)


class NotCoveredError(RuntimeError):
    """No term has enough defaults to train and validate a model (D-070)."""


def train_pd(
    frame: pl.DataFrame,
    cutoff: date,
    seed: int = SEED,
    *,
    params: dict[str, dict[str, Any]] | None = None,
    seen: Seen | None = None,
    trials: int = LIGHTGBM_TRIALS,
) -> PDTraining:
    """Run the procedure on ``frame`` (from :func:`prepare_frame`).

    ``params`` skips the search and uses the given hyperparameters (to rebuild a model
    from what its run recorded, T8.4). ``seen`` is called with the ids of every set used
    to fit or score a search trial (T7.3).
    """
    train = frame.filter(pl.col(SPLIT) == "train")
    validation = frame.filter(pl.col(SPLIT) == "validation")
    terms = covered_terms(train, validation)
    if not terms:
        raise NotCoveredError("no term has enough defaults in training and in validation")
    searches: dict[str, Search] = {}
    if params is None:
        inner_train, inner_validation = inner_split(train, cutoff)
        searches["logistic"] = search_logistic(inner_train, inner_validation, seen)
        searches["lightgbm"] = search_lightgbm(inner_train, inner_validation, seed, seen, trials)
        params = {name: dict(search.params) for name, search in searches.items()}

    prepare, estimator, removed = fit_logistic(train, params["logistic"]["C"])
    logistic = PDModel(
        "logistic", prepare, estimator, terms, params={**params["logistic"], "removed": removed}
    )
    lgbm_params = dict(params["lightgbm"])
    n_estimators = int(lgbm_params.pop("n_estimators"))
    prepare, estimator = fit_lightgbm(train, lgbm_params, seed, n_estimators)
    lightgbm = PDModel("lightgbm", prepare, estimator, terms, params=params["lightgbm"])
    prepare, estimator, _ = fit_logistic(train, math.inf, BASELINE_FEATURES)
    baseline = PDModel("baseline", prepare, estimator, terms, params={"C": math.inf})
    for model in (logistic, lightgbm, baseline):
        calibrate(model, validation)

    rows = validation.filter(pl.col("term").is_in(list(terms)))
    y = _y(rows)
    comparison = paired_bootstrap(
        y,
        lightgbm.predict_pd(rows).to_numpy(),
        logistic.predict_pd(rows).to_numpy(),
        "auc",
        seed=seed,
    )
    chosen = lightgbm if choose(comparison) == "lightgbm" else logistic
    log.info(
        "AUC on validation: logistic %.4f, lightgbm %.4f, improvement [%.4f, %.4f]; chosen %s",
        comparison.current,
        comparison.new,
        comparison.low,
        comparison.high,
        chosen.name,
    )
    return PDTraining(
        cutoff, seed, terms, logistic, lightgbm, baseline, chosen, comparison, searches
    )
