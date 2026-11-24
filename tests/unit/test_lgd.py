"""T12.1 to T12.5: the LGD procedure (D-087) on made-up data."""

import numpy as np
import polars as pl
import pytest

from credit_risk import registry
from credit_risk.compare import LGD_MARGINS, segment_check, segments, segments_pass
from credit_risk.lgd import fit_baseline, fit_ridge, lgd_rows, train_lgd
from credit_risk.model import LGDModel
from credit_risk.snapshot import LGD, SPLIT
from credit_risk.train import prepare_frame
from tests.synthetic import CUTOFF, training_set


def _frame(strength: float, seed: int) -> pl.DataFrame:
    return prepare_frame(training_set(12_000, seed=seed, strength=strength))


@pytest.fixture(scope="module")
def frame() -> pl.DataFrame:
    return _frame(1.0, seed=8)


# T12.1
def test_only_defaults_with_a_known_lgd_enter(frame: pl.DataFrame) -> None:
    seen: set[int] = set()
    train_lgd(frame, CUTOFF, (36,), trials=3, seen=lambda ids: seen.update(ids.to_list()))
    known = lgd_rows(frame.filter(pl.col(SPLIT) == "train"))
    assert seen
    assert seen <= set(known["id"].to_list())
    others = frame.filter(pl.col(LGD).is_null() | (pl.col(SPLIT) == "validation"))
    assert seen.isdisjoint(others["id"].to_list())


# T12.2
def test_the_baseline_is_the_mean_lgd_by_grade(frame: pl.DataFrame) -> None:
    train = lgd_rows(frame.filter(pl.col(SPLIT) == "train"))
    baseline = fit_baseline(train, (36,))
    by_hand = {
        g: float(np.mean(train.filter(pl.col("grade") == g)[LGD].to_numpy()))
        for g in train["grade"].unique()
    }
    assert baseline.grade_means == pytest.approx(by_hand)
    validation = lgd_rows(frame.filter(pl.col(SPLIT) == "validation"))
    expected = [min(max(by_hand[g], 0.0), 1.0) for g in validation["grade"]]
    assert baseline.predict_lgd(validation).to_list() == pytest.approx(expected)


# T12.3
@pytest.mark.parametrize(("strength", "wins"), [(0.0, False), (8.0, True)])
def test_the_baseline_wins_on_noise_and_loses_to_a_real_signal(strength: float, wins: bool) -> None:
    listings = training_set(12_000, seed=9, strength=strength)
    training = train_lgd(prepare_frame(listings), CUTOFF, (36,), trials=5)
    validation = lgd_rows(listings.filter(pl.col(SPLIT) == "validation"))
    verdict = registry.judge("lgd", training.chosen, training.baseline, validation, resamples=300)
    assert verdict.rules["better than the noise"] is wins
    # Not better: promotion leaves the baseline as champion (D-087, D-090).
    assert verdict.passed is wins


# T12.4
def test_a_wrong_level_in_one_grade_fails_the_segment_rule(frame: pl.DataFrame) -> None:
    train = lgd_rows(frame.filter(pl.col(SPLIT) == "train"))
    validation = lgd_rows(frame.filter(pl.col(SPLIT) == "validation"))
    good = fit_ridge(train, 1.0, (36,))

    class Shifted(LGDModel):
        def predict_lgd(self, features: pl.DataFrame) -> pl.Series:
            base = good.predict_lgd(features)
            shift = pl.Series((features["grade"] == "C").cast(pl.Float64) * 0.3)
            return (base + shift).clip(0, 1)

    shifted = Shifted("shifted", (36,))
    y = validation[LGD].to_numpy()
    masks = segments(validation, np.ones(validation.height), (36,))
    results = segment_check(
        y,
        shifted.predict_lgd(validation).to_numpy(),
        good.predict_lgd(validation).to_numpy(),
        masks,
        ("calibration_error",),
        margins=LGD_MARGINS,
        resamples=300,
        stratify=False,
    )
    assert not segments_pass(results)
    assert [r.segment for r in results if r.blocking] == ["grade C"]


# T12.5
def test_lgd_predictions_stay_between_0_and_1(frame: pl.DataFrame) -> None:
    train = lgd_rows(frame.filter(pl.col(SPLIT) == "train"))
    labels = train[LGD].to_numpy()
    assert labels.min() < 0 or labels.max() > 1  # the label can fall outside
    model = fit_ridge(train, 1e-3, (36,))
    rows = train.head(3).with_columns(
        int_rate=pl.Series([-500.0, 500.0, 16.0]), annual_inc=pl.Series([1e12, 1.0, 5e4])
    )
    lgd = model.predict_lgd(rows).to_numpy()
    assert np.all((lgd >= 0) & (lgd <= 1))
    assert lgd.min() == 0.0 or lgd.max() == 1.0
