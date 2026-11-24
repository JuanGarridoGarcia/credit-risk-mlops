"""Explanations of the PD (D-083): a base value plus one contribution per feature.

The contributions are SHAP values in log-odds, and they add up exactly: base value plus
contributions equals the log-odds of the calibrated PD. They are computed without the
``shap`` library, which only the training image carries (D-078, B7):

- logistic regression (and the grade-only baseline): coefficient times (value minus its
  mean on training), the exact SHAP values of a linear model with independent features;
- LightGBM: its own ``pred_contrib``, the same tree algorithm as ``shap.TreeExplainer``.

Platt scaling (D-076) is a straight line in log-odds, ``a x raw + b``: every contribution
is multiplied by ``a`` and the base value becomes ``a x base + b``. Contributions of the
columns made from one feature (one-hot categories, the "was missing" column) are summed
into that feature, so every explanation has the same 30 features (FEATURES); a feature the
model does not use contributes 0.
"""

import math
from dataclasses import dataclass
from typing import Final

import numpy as np
import polars as pl

from credit_risk.features import FEATURES
from credit_risk.model import Matrix, PDModel, Prepare

#: How many reasons the API returns with each PD (D-083).
REASONS: Final = 4


@dataclass(frozen=True)
class Explanation:
    """Base value and contributions, in log-odds after Platt scaling.

    ``contributions`` has one row per loan and one column per feature of FEATURES; the
    row of a loan whose term is not covered (D-070) is all NaN, like its PD.
    """

    base: float
    contributions: Matrix

    def log_odds(self) -> Matrix:
        """Base value plus contributions: the log-odds of each calibrated PD."""
        return np.asarray(self.base + self.contributions.sum(axis=1), dtype=np.float64)


@dataclass(frozen=True)
class Reason:
    """One of the main reasons of a PD: the feature, its push in log-odds, its value."""

    feature: str
    contribution: float
    value: object


def feature_of(column: str, prepare: Prepare) -> str:
    """The feature an output column of ``prepare`` was made from."""
    if column in prepare.features:
        return column
    if column.endswith("_missing") and column.removesuffix("_missing") in prepare.features:
        return column.removesuffix("_missing")
    return column.split("=", 1)[0]


def raw_contributions(model: PDModel, features: pl.DataFrame) -> tuple[float, Matrix]:
    """Base value and one contribution per output column of the model, before Platt."""
    x = model.prepare.transform(features)
    estimator = model.estimator
    if hasattr(estimator, "coef_"):
        coef = np.asarray(estimator.coef_, dtype=np.float64).ravel()
        means = np.asarray(model.prepare.column_means, dtype=np.float64)
        base = float(estimator.intercept_[0] + (coef * means).sum())
        return base, np.asarray((x - means) * coef, dtype=np.float64)
    out = np.asarray(estimator.predict(x, pred_contrib=True), dtype=np.float64)
    base = float(out[0, -1]) if out.shape[0] else 0.0
    return base, out[:, :-1]


def explain(model: PDModel, features: pl.DataFrame) -> Explanation:
    """The explanation of every row's PD (D-083)."""
    base, columns = raw_contributions(model, features)
    a, b = model.platt
    contributions = np.zeros((features.height, len(FEATURES)))
    for j, column in enumerate(model.prepare.names):
        contributions[:, FEATURES.index(feature_of(column, model.prepare))] += columns[:, j]
    contributions *= a
    contributions[~model.covered(features)] = math.nan
    return Explanation(a * base + b, contributions)


def reasons(
    explanation: Explanation, features: pl.DataFrame, k: int = REASONS
) -> list[list[Reason]]:
    """The ``k`` main reasons of each PD: the largest contributions in absolute value.

    Ties keep the order of FEATURES, so the same loan always gets the same reasons. A
    feature with no contribution is no reason; a loan with no PD gets none.
    """
    result: list[list[Reason]] = []
    for i, row in enumerate(explanation.contributions):
        if np.isnan(row).any():
            result.append([])
            continue
        order = np.argsort(-np.abs(row), kind="stable")
        result.append(
            [
                Reason(FEATURES[j], float(row[j]), features[FEATURES[j]][i])
                for j in order[:k]
                if row[j] != 0.0
            ]
        )
    return result
