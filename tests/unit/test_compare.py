"""T9.1 to T9.3: the paired bootstrap, the choice between candidates and the key segments."""

from datetime import date

import numpy as np
import polars as pl
import pytest

from credit_risk.compare import (
    PD_MARGINS,
    choose,
    paired_bootstrap,
    segment_check,
    segments,
    segments_pass,
)

RNG = np.random.default_rng(0)
N = 4_000
Y = (RNG.random(N) < 0.15).astype(float)
#: A score that knows the label well, and one that knows it a little.
GOOD = Y * 1.5 + RNG.normal(0, 1, N)
WEAK = Y * 0.3 + RNG.normal(0, 1, N)
STRONG = Y * 4.0 + RNG.normal(0, 1, N)


# T9.1
def test_a_clearly_better_model_wins_and_a_worse_one_loses() -> None:
    better = paired_bootstrap(Y, GOOD, WEAK, "auc", resamples=300)
    assert better.better
    assert not better.worse
    worse = paired_bootstrap(Y, WEAK, GOOD, "auc", resamples=300)
    assert worse.worse
    assert not worse.better


def test_identical_models_never_win() -> None:
    same = paired_bootstrap(Y, GOOD, GOOD.copy(), "auc", resamples=300)
    assert np.all(same.improvements == 0)
    assert not same.better
    assert not same.worse


def test_every_resample_keeps_the_number_of_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    import credit_risk.compare as compare

    drawn: list[float] = []
    original = compare._resample

    def spy(y: np.ndarray, rng: np.random.Generator, stratify: bool) -> np.ndarray:
        idx = original(y, rng, stratify)
        drawn.append(float(y[idx].sum()))
        return idx

    monkeypatch.setattr(compare, "_resample", spy)
    paired_bootstrap(Y, GOOD, WEAK, "auc", resamples=50)
    assert drawn == [Y.sum()] * 50


def test_the_same_seed_gives_the_same_interval() -> None:
    a = paired_bootstrap(Y, GOOD, WEAK, "auc", resamples=200, seed=3)
    b = paired_bootstrap(Y, GOOD, WEAK, "auc", resamples=200, seed=3)
    assert (a.low, a.high) == (b.low, b.high)
    assert np.array_equal(a.improvements, b.improvements)


def test_lower_is_better_for_the_brier_score() -> None:
    calibrated = np.clip(np.where(Y == 1, 0.6, 0.1), 0, 1)
    off = np.clip(calibrated + 0.3, 0, 1)
    comparison = paired_bootstrap(Y, calibrated, off, "brier", resamples=300)
    assert comparison.new < comparison.current
    assert comparison.better


# T9.2
def test_lightgbm_needs_its_interval_above_zero_to_be_chosen() -> None:
    assert choose(paired_bootstrap(Y, GOOD, WEAK, "auc", resamples=300)) == "lightgbm"
    slightly = GOOD + RNG.normal(0, 0.05, N)
    tie = paired_bootstrap(Y, slightly, GOOD, "auc", resamples=300)
    assert tie.low <= 0 <= tie.high
    assert choose(tie) == "logistic"
    # Even when its mean AUC is the higher one: a tiny gain inside the noise.
    noise = np.random.default_rng(0).normal(0, 0.05, N)
    lucky = paired_bootstrap(Y, GOOD + noise, GOOD, "auc", resamples=300)
    assert lucky.new > lucky.current
    assert lucky.low <= 0
    assert choose(lucky) == "logistic"


# T9.3
def _frame(grades: list[str], quarters: list[date]) -> pl.DataFrame:
    return pl.DataFrame(
        {"grade": grades, "term": [36] * len(grades), "issue_d": quarters},
        schema={"grade": pl.String, "term": pl.Int16, "issue_d": pl.Date},
    )


def test_segments_merge_f_and_g_and_small_groups() -> None:
    grades = ["A"] * 100 + ["B"] * 100 + ["F"] * 30 + ["G"] * 30
    issue = [date(2010, 3, 1)] * 130 + [date(2010, 6, 1)] * 130
    frame = _frame(grades, issue)
    # Defaults: 49 in A (merged with B), 60 in B, 30 + 30 in F and G (one segment).
    events = np.array([1.0] * 49 + [0.0] * 51 + [1.0] * 60 + [0.0] * 40 + [1.0] * 60)
    masks = segments(frame, events, covered_terms=(36,))
    assert {k for k in masks if k.startswith("grade")} == {"grade A+B", "grade F+G"}
    assert "term 36 months" in masks
    assert {k for k in masks if k.startswith("quarter")} == {"quarter 2010Q1", "quarter 2010Q2"}
    # With 50 defaults, A stands on its own.
    events[49] = 1.0
    masks = segments(frame, events, covered_terms=(36,))
    assert "grade A" in masks


def test_a_model_clearly_worse_in_one_segment_fails() -> None:
    grade_a = np.arange(N) < N // 4
    masks = {"grade A": grade_a, "grade B": ~grade_a}
    # Better than the current model overall, but much worse inside grade A.
    new = np.where(grade_a, WEAK, STRONG)
    current = GOOD
    overall = paired_bootstrap(Y, new, current, "auc", resamples=200)
    assert overall.better
    results = segment_check(Y, new, current, masks, ("auc",), margins=PD_MARGINS, resamples=200)
    assert not segments_pass(results)
    # A tie in every segment passes: it need not improve everywhere.
    results = segment_check(Y, GOOD, GOOD.copy(), masks, ("auc",), resamples=200)
    assert segments_pass(results)


def test_clearly_worse_within_the_margin_passes() -> None:
    masks = {"all": np.ones(N, dtype=bool)}
    p = np.clip(np.where(Y == 1, 0.5, 0.1), 0, 1)
    # Off by half a point of PD everywhere: clearly worse, but under the 1-point margin.
    off = p + 0.005
    results = segment_check(
        Y, off, p, masks, ("calibration_error",), margins=PD_MARGINS, resamples=200
    )
    assert results[0].comparison.worse
    assert segments_pass(results)
    # Without the margin it would block (D-081 before D-093).
    assert not segments_pass(segment_check(Y, off, p, masks, ("calibration_error",), resamples=200))
