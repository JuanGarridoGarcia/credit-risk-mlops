"""T7.1, T7.2, T7.5 and T9.4: the PD model's learned preparation, odd rows, coverage, signs."""

import math

import numpy as np
import polars as pl
import pytest
from sklearn.linear_model import LogisticRegression

from credit_risk.features import FEATURES
from credit_risk.model import (
    MIN_DEFAULTS,
    MONOTONE,
    PDModel,
    Prepare,
    check_signs,
    covered_terms,
    monotone_constraints,
)
from credit_risk.snapshot import LABEL, SPLIT
from credit_risk.train import fit_lightgbm, fit_logistic, prepare_frame
from tests.synthetic import training_set


@pytest.fixture(scope="module")
def frame() -> pl.DataFrame:
    return prepare_frame(training_set(3_000, seed=1))


@pytest.fixture(scope="module")
def train(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.filter(pl.col(SPLIT) == "train")


@pytest.fixture(scope="module")
def validation(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.filter(pl.col(SPLIT) == "validation")


# T7.1
def test_learned_preparation_sees_training_only(
    train: pl.DataFrame, validation: pl.DataFrame
) -> None:
    prepare = Prepare("linear").fit(train)
    assert prepare.medians["dti"] == pytest.approx(train["dti"].median())
    expected = tuple(sorted(train["purpose"].drop_nulls().unique().to_list()))
    assert prepare.categories["purpose"] == expected

    # Extreme values and a new category in validation change nothing that was learned.
    before = (dict(prepare.medians), dict(prepare.means), dict(prepare.categories))
    extreme = validation.with_columns(dti=pl.lit(1e9), purpose=pl.lit("never seen"))
    prepare.transform(extreme)
    assert (prepare.medians, prepare.means, prepare.categories) == before
    # And fitting on training plus extreme validation rows would have changed them.
    leaked = Prepare("linear").fit(pl.concat([train, extreme]))
    assert leaked.means["dti"] != prepare.means["dti"]
    assert "never seen" in leaked.categories["purpose"]


# T7.2
@pytest.mark.parametrize("kind", ["logistic", "lightgbm"])
def test_an_odd_row_still_gets_a_probability(
    kind: str, train: pl.DataFrame, validation: pl.DataFrame
) -> None:
    if kind == "logistic":
        prepare, estimator, _ = fit_logistic(train, 1.0)
    else:
        prepare, estimator = fit_lightgbm(train, {}, seed=0, n_estimators=50)
    model = PDModel(kind, prepare, estimator, (36,))
    row = validation.head(1)
    empty = row.with_columns(
        pl.lit(None, dtype=row.schema[c]).alias(c) for c in FEATURES if c != "term"
    )
    unseen = row.with_columns(purpose=pl.lit("never seen"), home_ownership=pl.lit("BOAT"))
    extreme = row.with_columns(annual_inc=pl.lit(1e12), dti=pl.lit(1e6), int_rate=pl.lit(-50.0))
    pd_ = model.predict_pd(pl.concat([empty, unseen, extreme])).to_numpy()
    assert np.all(np.isfinite(pd_))
    assert np.all((pd_ >= 0) & (pd_ <= 1))


# T7.5
def _with_defaults(term: int, train: int, validation: int) -> pl.DataFrame:
    rows = [(term, 1, "train")] * train + [(term, 1, "validation")] * validation
    rows += [(term, 0, "train"), (term, 0, "validation")]
    return pl.DataFrame(rows, schema=["term", LABEL, SPLIT], orient="row")


def test_a_term_needs_200_defaults_in_training_and_in_validation() -> None:
    assert MIN_DEFAULTS == 200
    cases = pl.concat(
        [
            _with_defaults(36, 200, 200),  # exactly at the minimum: covered
            _with_defaults(60, 199, 300),  # one short in training: not covered
        ]
    )
    train = cases.filter(pl.col(SPLIT) == "train")
    validation = cases.filter(pl.col(SPLIT) == "validation")
    assert covered_terms(train, validation) == (36,)
    cases = _with_defaults(60, 300, 199)  # one short in validation: not covered
    split = cases.partition_by(SPLIT, as_dict=True)
    assert covered_terms(split[("train",)], split[("validation",)]) == ()


def test_an_uncovered_term_gets_no_pd(train: pl.DataFrame, validation: pl.DataFrame) -> None:
    prepare, estimator, _ = fit_logistic(train, 1.0)
    model = PDModel("logistic", prepare, estimator, covered_terms=(36,))
    rows = validation.head(2).with_columns(term=pl.Series([36, 60], dtype=pl.Int16))
    pd_ = model.predict_pd(rows).to_list()
    assert pd_[0] is not None
    assert pd_[1] is None


# T9.4
def test_the_logistic_regression_keeps_the_signs_of_d080(train: pl.DataFrame) -> None:
    prepare, estimator, removed = fit_logistic(train, 1.0)
    model = PDModel("logistic", prepare, estimator, (36,))
    assert all(check_signs(model).values())
    assert removed == ()

    # Made-up data where a higher interest rate lowers the risk.
    flipped = train.with_columns(int_rate=-pl.col("int_rate"))
    plain = Prepare("linear").fit(flipped)
    unconstrained = LogisticRegression(C=1.0, max_iter=5_000).fit(
        plain.transform(flipped), flipped[LABEL].to_numpy()
    )
    signs = check_signs(PDModel("logistic", plain, unconstrained, (36,)))
    assert signs["int_rate"] is False
    # The procedure (D-092) removes it and refits, so no wrong sign comes out.
    prepare, estimator, removed = fit_logistic(flipped, 1.0)
    assert "int_rate" in removed
    assert all(check_signs(PDModel("logistic", prepare, estimator, (36,))).values())


def test_lightgbm_is_trained_with_exactly_the_fixed_constraints(train: pl.DataFrame) -> None:
    prepare, estimator = fit_lightgbm(train, {}, seed=0, n_estimators=20)
    constraints = estimator.get_params()["monotone_constraints"]
    assert constraints == monotone_constraints(prepare)
    by_name = dict(zip(prepare.names, constraints, strict=True))
    assert {k: v for k, v in by_name.items() if v} == MONOTONE
    assert math.isclose(sum(abs(v) for v in constraints), len(MONOTONE))
