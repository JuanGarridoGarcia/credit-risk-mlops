"""The PD model: learned preparation, an estimator, Platt calibration and the covered terms.

Everything here is needed to *predict*, so it ships in the ``serve`` image (D-078); the
search and the training procedure live in :mod:`credit_risk.train`.

- :class:`Prepare` is the learned part of the preparation (D-062): fill values, scaling
  and known categories, fitted on training rows only. The fixed part is
  :func:`credit_risk.features.build_features`.
- :class:`PDModel` predicts a calibrated probability of default (D-076) for the loans of
  the terms it covers (D-070) and nothing for the others: a missing value, never a PD.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Literal

import numpy as np
import numpy.typing as npt
import polars as pl
from scipy.special import expit

from credit_risk.features import CATEGORICAL, FEATURES, FICO, HISTORY, SCHEMA

Matrix = npt.NDArray[np.float64]
Kind = Literal["linear", "trees"]

#: D-070: a term is covered with at least this many defaults in training and in validation.
MIN_DEFAULTS: Final = 200

#: D-080: risk does not fall when these rise (+1) / does not rise when these rise (-1).
MONOTONE: Final = {
    "int_rate": 1,
    "dti": 1,
    "revol_util": 1,
    "inq_last_6mths": 1,
    "delinq_2yrs": 1,
    "pub_rec": 1,
    FICO: -1,
    "annual_inc": -1,
    HISTORY: -1,
}

#: The grade-only baseline (D-004).
BASELINE_FEATURES: Final = ("grade",)

_MISSING: Final = "__missing__"
_EPS: Final = 1e-15


def logit(p: Matrix) -> Matrix:
    """Log-odds of probabilities, clipped away from 0 and 1."""
    q = np.clip(p, _EPS, 1 - _EPS)
    return np.asarray(np.log(q / (1 - q)), dtype=np.float64)


def sigmoid(z: Matrix) -> Matrix:
    """Inverse of :func:`logit`, without overflow for extreme values (T7.2)."""
    return np.asarray(expit(z), dtype=np.float64)


@dataclass
class Prepare:
    """Learned preparation (D-062), fitted on training rows only.

    ``linear`` (logistic and linear regression): numeric gaps filled with the training
    median plus a 0/1 column saying the value was missing, then standardised; categories
    one-hot encoded, an unseen category gives all zeros. ``trees`` (LightGBM): numeric
    values as they are, gaps included; categories as integer codes, unseen or missing
    as a gap.
    """

    kind: Kind
    features: tuple[str, ...] = FEATURES
    medians: dict[str, float] = field(default_factory=dict)
    means: dict[str, float] = field(default_factory=dict)
    scales: dict[str, float] = field(default_factory=dict)
    gaps: tuple[str, ...] = ()
    categories: dict[str, tuple[str, ...]] = field(default_factory=dict)
    fitted: bool = False
    #: Mean of every output column on training (``linear`` only): the reference point of
    #: the explanations of a linear model (D-083).
    column_means: tuple[float, ...] = ()

    @property
    def numeric(self) -> tuple[str, ...]:
        return tuple(c for c in self.features if c not in CATEGORICAL)

    @property
    def categorical(self) -> tuple[str, ...]:
        return tuple(c for c in self.features if c in CATEGORICAL)

    def fit(self, frame: pl.DataFrame) -> "Prepare":
        """Learn the fill values, scales and categories from ``frame`` (training rows)."""
        for c in self.numeric:
            values = frame[c].cast(pl.Float64)
            median = values.median()
            self.medians[c] = float(median) if isinstance(median, float) else 0.0
            filled = values.fill_null(self.medians[c])
            mean = filled.mean()
            self.means[c] = float(mean) if isinstance(mean, float) else 0.0
            std = filled.std()
            self.scales[c] = float(std) if isinstance(std, float) and std > 0 else 1.0
        self.gaps = tuple(c for c in self.numeric if frame[c].null_count() > 0)
        for c in self.categorical:
            seen = frame[c].drop_nulls().unique().sort().to_list()
            if self.kind == "linear" and frame[c].null_count() > 0:
                seen.append(_MISSING)
            self.categories[c] = tuple(str(v) for v in seen)
        self.fitted = True
        if self.kind == "linear":
            self.column_means = tuple(float(m) for m in self.transform(frame).mean(axis=0))
        return self

    @property
    def names(self) -> list[str]:
        """Names of the output columns, in order."""
        if self.kind == "trees":
            return list(self.features)
        return [
            *self.numeric,
            *(f"{c}_missing" for c in self.gaps),
            *(f"{c}={v}" for c in self.categorical for v in self.categories[c]),
        ]

    def categorical_indices(self) -> list[int]:
        """Positions of the categorical columns in the output (``trees`` only)."""
        return [i for i, c in enumerate(self.features) if c in CATEGORICAL]

    def transform(self, frame: pl.DataFrame) -> Matrix:
        """The model matrix of ``frame``: one row per loan, columns as :attr:`names`."""
        if not self.fitted:
            raise RuntimeError("Prepare must be fitted on training rows first")
        columns: list[Matrix] = []
        if self.kind == "trees":
            for c in self.features:
                if c in CATEGORICAL:
                    codes = {v: float(i) for i, v in enumerate(self.categories[c])}
                    values = frame[c].cast(pl.String).to_list()
                    columns.append(
                        np.array([codes.get(v, math.nan) for v in values], dtype=np.float64)
                    )
                else:
                    columns.append(frame[c].cast(pl.Float64).fill_null(math.nan).to_numpy())
            return np.column_stack(columns) if columns else np.empty((frame.height, 0))
        for c in self.numeric:
            filled = frame[c].cast(pl.Float64).fill_null(self.medians[c]).to_numpy()
            columns.append((filled - self.means[c]) / self.scales[c])
        for c in self.gaps:
            columns.append(frame[c].is_null().cast(pl.Float64).to_numpy())
        for c in self.categorical:
            text = frame[c].cast(pl.String).fill_null(_MISSING)
            for v in self.categories[c]:
                columns.append((text == v).cast(pl.Float64).to_numpy())
        return np.column_stack(columns) if columns else np.empty((frame.height, 0))


@dataclass
class PDModel:
    """A fitted PD model: preparation, estimator, Platt calibrator and covered terms."""

    name: str
    prepare: Prepare
    estimator: Any
    covered_terms: tuple[int, ...]
    platt: tuple[float, float] = (1.0, 0.0)
    params: dict[str, Any] = field(default_factory=dict)

    def raw(self, features: pl.DataFrame) -> Matrix:
        """Uncalibrated log-odds of default of every row.

        For a linear model the sum is taken row by row, so a loan gets exactly the same
        value alone or inside a batch (D-086); a matrix product can differ in the last
        decimal with the number of rows.
        """
        x = self.prepare.transform(features)
        if hasattr(self.estimator, "coef_"):
            coef = np.asarray(self.estimator.coef_, dtype=np.float64).ravel()
            return np.asarray((x * coef).sum(axis=1) + self.estimator.intercept_[0])
        # LightGBM's own log-odds: the exact sum of its contributions (D-083).
        return np.asarray(self.estimator.predict(x, raw_score=True), dtype=np.float64)

    def calibrated(self, raw: Matrix) -> Matrix:
        """Platt scaling (D-076) of raw log-odds."""
        a, b = self.platt
        return sigmoid(a * raw + b)

    def covered(self, features: pl.DataFrame) -> npt.NDArray[np.bool_]:
        """Whether each row's term is covered (D-070)."""
        return np.asarray(features["term"].is_in(list(self.covered_terms)).fill_null(False))

    def predict_pd(self, features: pl.DataFrame) -> pl.Series:
        """Calibrated PD of every row; null for a term the model does not cover (D-070)."""
        pd_ = self.calibrated(self.raw(features)) if features.height else np.empty(0)
        values = np.where(self.covered(features), pd_, math.nan)
        return pl.Series("pd", values, dtype=pl.Float64).fill_nan(None)


def covered_terms(
    train: pl.DataFrame, validation: pl.DataFrame, minimum: int = MIN_DEFAULTS
) -> tuple[int, ...]:
    """Terms with at least ``minimum`` defaults in training and in validation (D-070)."""

    def defaults(frame: pl.DataFrame) -> dict[int, int]:
        counts = frame.group_by("term").agg(pl.col("label").sum()).rows()
        return {int(term): int(n) for term, n in counts if term is not None}

    in_train, in_validation = defaults(train), defaults(validation)
    return tuple(
        sorted(t for t in in_train if in_train[t] >= minimum and in_validation.get(t, 0) >= minimum)
    )


def monotone_constraints(prepare: Prepare) -> list[int]:
    """LightGBM constraint per output column of ``prepare`` (D-080), 0 for the others."""
    return [MONOTONE.get(c, 0) for c in prepare.names]


def check_signs(model: PDModel) -> dict[str, bool]:
    """D-080 for the logistic regression: whether each of the nine coefficients has its sign.

    A feature the model does not use is reported as passing: it cannot push the risk the
    wrong way.
    """
    names = model.prepare.names
    coefficients = np.asarray(model.estimator.coef_, dtype=np.float64).ravel()
    signs: dict[str, bool] = {}
    for feature, direction in MONOTONE.items():
        if feature not in names:
            signs[feature] = True
            continue
        signs[feature] = bool(coefficients[names.index(feature)] * direction >= 0)
    return signs


def feature_frame(rows: Sequence[dict[str, object]]) -> pl.DataFrame:
    """A features frame from plain rows (tests, the battery)."""
    return pl.DataFrame(list(rows), schema=dict(SCHEMA))


@dataclass
class LGDModel:
    """A fitted LGD model (D-087): a regression on the prepared features, or, for the
    baseline (D-005), the mean LGD of each grade in training. ``shift`` is the level
    correction fitted on validation (D-094), added before predictions are clipped to
    [0, 1]; a term the PD does not cover gets nothing (D-070)."""

    name: str
    covered_terms: tuple[int, ...]
    prepare: Prepare | None = None
    estimator: Any = None
    grade_means: dict[str, float] = field(default_factory=dict)
    overall_mean: float = 0.0
    params: dict[str, Any] = field(default_factory=dict)
    shift: float = 0.0

    def predict_lgd(self, features: pl.DataFrame) -> pl.Series:
        """LGD of every row, in [0, 1]; null for a term not covered."""
        if self.estimator is None:
            raw = np.array(
                [self.grade_means.get(g, self.overall_mean) for g in features["grade"]],
                dtype=np.float64,
            )
        elif features.height and self.prepare is not None:
            raw = np.asarray(self.estimator.predict(self.prepare.transform(features)))
        else:
            raw = np.empty(0)
        covered = np.asarray(features["term"].is_in(list(self.covered_terms)).fill_null(False))
        values = np.where(covered, np.clip(raw + self.shift, 0.0, 1.0), math.nan)
        return pl.Series("lgd", values, dtype=pl.Float64).fill_nan(None)
