"""T13.1 to T13.5: the explanations of the PD (D-083) on made-up data."""

import math
import warnings

import numpy as np
import polars as pl
import pytest

from credit_risk import battery
from credit_risk.explain import Explanation, explain, feature_of, reasons
from credit_risk.features import FEATURES, build_features
from credit_risk.model import PDModel, logit
from credit_risk.snapshot import SPLIT
from credit_risk.train import PDTraining, prepare_frame, train_pd
from tests.synthetic import CUTOFF, training_set


@pytest.fixture(scope="module")
def listings() -> pl.DataFrame:
    return training_set(seed=13)


@pytest.fixture(scope="module")
def training(listings: pl.DataFrame) -> PDTraining:
    return train_pd(prepare_frame(listings), CUTOFF, trials=3)


@pytest.fixture(scope="module")
def train(listings: pl.DataFrame) -> pl.DataFrame:
    return prepare_frame(listings).filter(pl.col(SPLIT) == "train")


@pytest.fixture(scope="module")
def validation(listings: pl.DataFrame) -> pl.DataFrame:
    return build_features(listings.filter(pl.col(SPLIT) == "validation"))


def _models(training: PDTraining) -> list[PDModel]:
    return [training.logistic, training.lightgbm, training.baseline]


def _odd_rows(validation: pl.DataFrame) -> pl.DataFrame:
    template = validation.head(1)
    empty = template.with_columns(
        pl.lit(None, dtype=validation[c].dtype).alias(c)
        for c in FEATURES
        if c not in battery.ESSENTIAL
    )
    unseen = template.with_columns(purpose=pl.lit("never seen"), home_ownership=pl.lit("BOAT"))
    extreme = template.with_columns(int_rate=pl.lit(500.0), annual_inc=pl.lit(1e12))
    return pl.concat([empty, unseen, extreme])


# T13.1
@pytest.mark.parametrize("name", ["logistic", "lightgbm", "baseline"])
def test_base_plus_contributions_is_the_prediction(
    training: PDTraining, validation: pl.DataFrame, name: str
) -> None:
    model = getattr(training, name)
    rows = pl.concat([validation, _odd_rows(validation)])
    explanation = explain(model, rows)
    expected = model.platt[0] * model.raw(rows) + model.platt[1]
    assert np.allclose(explanation.log_odds(), expected, rtol=1e-9, atol=1e-9)
    # The same, read back from the served PD (log-odds of the calibrated probability).
    pd_ = model.predict_pd(validation).to_numpy()
    assert np.allclose(explain(model, validation).log_odds(), logit(pd_), rtol=1e-9, atol=1e-6)


# T13.2
def test_the_contributions_are_shap_values(
    training: PDTraining, train: pl.DataFrame, validation: pl.DataFrame
) -> None:
    shap = pytest.importorskip("shap")  # absent only in the serve image, never here
    rows = validation.head(200)
    for model in (training.logistic, training.lightgbm):
        ours = explain(model, rows)
        x = model.prepare.transform(rows)
        if model.name == "logistic":
            background = model.prepare.transform(train)
            masker = shap.maskers.Independent(background, max_samples=background.shape[0])
            explainer = shap.LinearExplainer(model.estimator, masker)
            values = np.asarray(explainer.shap_values(x))
            base = float(np.ravel(explainer.expected_value)[0])
        else:
            explainer = shap.TreeExplainer(model.estimator)
            with warnings.catch_warnings():
                # shap notes that its output format for LightGBM changed; both are handled.
                warnings.filterwarnings("ignore", message="LightGBM binary classifier")
                output = explainer.shap_values(x)
            values = np.asarray(output[1] if isinstance(output, list) else output)
            base = float(np.ravel(explainer.expected_value)[-1])
        a, b = model.platt
        grouped = np.zeros((rows.height, len(FEATURES)))
        for j, column in enumerate(model.prepare.names):
            grouped[:, FEATURES.index(feature_of(column, model.prepare))] += values[:, j]
        assert np.allclose(ours.contributions, a * grouped, atol=1e-6), model.name
        assert ours.base == pytest.approx(a * base + b, abs=1e-6), model.name


# T13.3
def test_one_contribution_per_original_feature(
    training: PDTraining, validation: pl.DataFrame
) -> None:
    logistic = training.logistic
    names = logistic.prepare.names
    assert any("=" in n for n in names)
    assert any(n.endswith("_missing") for n in names)
    explanation = explain(logistic, validation)
    assert explanation.contributions.shape == (validation.height, len(FEATURES))
    # Every one-hot and "was missing" column lands in its feature.
    assert feature_of("purpose=credit_card", logistic.prepare) == "purpose"
    assert feature_of("mths_since_last_delinq_missing", logistic.prepare) == (
        "mths_since_last_delinq"
    )
    unused = [f for f in FEATURES if f not in logistic.prepare.features]
    for feature in unused:
        assert np.all(explanation.contributions[:, FEATURES.index(feature)] == 0.0)
    # The baseline uses the grade only: every other feature contributes 0.
    baseline = explain(training.baseline, validation).contributions
    others = [i for i, f in enumerate(FEATURES) if f != "grade"]
    assert np.all(baseline[:, others] == 0.0)
    assert np.any(baseline[:, FEATURES.index("grade")] != 0.0)


# T13.4
def test_the_four_main_reasons_by_hand() -> None:
    row = np.zeros(len(FEATURES))
    values = {"int_rate": 0.9, "dti": -0.5, "fico": -0.9, "revol_util": 0.2, "grade": 0.5}
    for feature, value in values.items():
        row[FEATURES.index(feature)] = value
    frame = pl.DataFrame({f: [f"value of {f}"] for f in FEATURES})
    found = reasons(Explanation(-2.0, row[np.newaxis, :]), frame)[0]
    # 0.9 and -0.9 tie, as do -0.5 and 0.5: the order of FEATURES decides.
    tied_first = sorted(["int_rate", "fico"], key=FEATURES.index)
    tied_second = sorted(["dti", "grade"], key=FEATURES.index)
    assert [r.feature for r in found] == [*tied_first, *tied_second]
    assert [r.contribution for r in found] == [values[f] for f in (*tied_first, *tied_second)]
    assert found[0].value == f"value of {tied_first[0]}"
    # No PD, no reasons; a model with fewer features gives fewer reasons.
    none = Explanation(-2.0, np.full((1, len(FEATURES)), math.nan))
    assert reasons(none, frame) == [[]]
    one = np.zeros((1, len(FEATURES)))
    one[0, FEATURES.index("grade")] = 0.3
    assert [r.feature for r in reasons(Explanation(-2.0, one), frame)[0]] == ["grade"]


# T13.5
def test_the_reasons_make_sense(training: PDTraining, validation: pl.DataFrame) -> None:
    template = validation.filter(pl.col("term").is_in(list(training.covered_terms))).head(1)
    for model in (training.logistic, training.lightgbm):
        bad = template.with_columns(pl.lit(v).alias(k) for k, v in battery.BAD.items())
        good = template.with_columns(pl.lit(v).alias(k) for k, v in battery.GOOD.items())
        bad = bad.cast(dict(validation.schema))  # type: ignore[arg-type]
        good = good.cast(dict(validation.schema))  # type: ignore[arg-type]
        assert reasons(explain(model, bad), bad)[0][0].contribution > 0, model.name
        assert reasons(explain(model, good), good)[0][0].contribution < 0, model.name
