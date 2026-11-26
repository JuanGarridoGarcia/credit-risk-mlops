"""T23.1 to T23.6: drift (D-139, D-140); T25.1, T25.3: the early warning (D-143); T26.2:
real performance with the metrics of promotion (D-144). Approved by Juan on 2026-11-26.

The made-up loans are those of the training tests (``tests/synthetic.py``), turned into the
30 features by the same module as the models (``credit_risk.features``).
"""

import math

import numpy as np
import polars as pl
import pytest
from scipy.stats import ks_2samp

from credit_risk import business, compare
from credit_risk.features import FEATURES, build_features
from credit_risk.monitoring import drift, outcomes
from credit_risk.monitoring.store import kind_of
from tests.synthetic import training_set


def _features(n: int, seed: int) -> pl.DataFrame:
    return build_features(training_set(n, seed=seed))


def _psi(reference: pl.Series, month: pl.Series, kind: drift.Kind = "numeric") -> float:
    return drift.measure(drift.fit("x", kind, reference), month).psi


# T23.1
def test_psi_is_zero_for_the_same_shares_and_matches_the_hand_examples() -> None:
    shares = (0.20, 0.35, 0.30, 0.15)
    assert drift.psi(shares, shares) == 0.0
    # The two examples of grade given to Juan (A, B, C, D+).
    assert drift.psi(shares, (0.15, 0.30, 0.33, 0.22)) == pytest.approx(0.0518, abs=5e-4)
    assert drift.psi(shares, (0.10, 0.25, 0.30, 0.35)) == pytest.approx(0.2724, abs=5e-4)
    # Through the bins: the same values against themselves.
    grades = pl.Series(["A"] * 20 + ["B"] * 35 + ["C"] * 30 + ["D"] * 15)
    assert _psi(grades, grades, "categorical") == 0.0
    with pytest.raises(ValueError, match="different bins"):
        drift.psi((0.5, 0.5), (1.0,))


# T23.2
def test_two_samples_of_the_same_distribution_show_no_drift() -> None:
    reference, month = _features(20_000, 1), _features(20_000, 2)
    for subject in FEATURES:
        kind = kind_of(subject)
        value = _psi(reference[subject], month[subject], kind)
        assert value < 0.01, (subject, value)


#: Shares of grades A, B, C and D of the example given to Juan, before and after.
BEFORE = {"A": 0.20, "B": 0.35, "C": 0.30, "D": 0.15}
AFTER = {"A": 0.10, "B": 0.25, "C": 0.30, "D": 0.35}


def _with_grades(frame: pl.DataFrame, shares: dict[str, float], seed: int) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    drawn = rng.choice(list(shares), frame.height, p=list(shares.values()))
    return frame.with_columns(grade=pl.Series(drawn))


# T23.3
def test_an_injected_change_is_seen_in_that_variable_only() -> None:
    reference = _with_grades(_features(20_000, 1), BEFORE, 1)
    month = _with_grades(_features(20_000, 2), BEFORE, 2)
    changes = {
        "int_rate": month.with_columns(pl.col("int_rate") + 2),
        # More than twice the loans of grade D, the second example given to Juan.
        "grade": _with_grades(month, AFTER, 3),
    }
    for changed, frame in changes.items():
        for subject in FEATURES:
            value = _psi(reference[subject], frame[subject], kind_of(subject))
            if subject == changed:
                assert value > 0.25, (changed, value)
            else:
                assert value < 0.01, (changed, subject, value)


# T23.4
def test_bins_are_cut_at_the_deciles_of_the_reference() -> None:
    values = pl.Series(np.arange(1, 101, dtype=np.float64))
    bins = drift.fit("x", "numeric", values)
    assert bins.edges == tuple(np.quantile(values.to_numpy(), drift.QUANTILES))
    assert len(bins.shares) == len(bins.edges) + 2  # ten bins and the missing one
    assert bins.shares[:-1] == pytest.approx([0.1] * 10)
    # Out of range: into the bin at that end.
    found = drift.counts(bins, pl.Series([-1e9, 0.0, 1e9]))
    assert found.tolist() == [2] + [0] * 8 + [1, 0]
    # A value equal to a cut point belongs to the bin that ends there.
    assert drift.counts(bins, pl.Series([bins.edges[0]])).tolist()[0] == 1
    # Mostly zeros (like delinq_2yrs): cut points kept once, no empty twin bins.
    ties = pl.Series([0.0] * 850 + [1.0] * 100 + [2.0] * 50)
    tied = drift.fit("delinq_2yrs", "numeric", ties)
    assert tied.edges == tuple(sorted(set(tied.edges)))
    assert all(s > 0 for s in tied.shares[:-1]), tied.shares
    assert drift.measure(tied, ties).psi == 0.0


# T23.5
def test_missing_and_new_values_have_their_own_bin() -> None:
    reference = pl.Series(["A", "B", "C", None] * 25)
    bins = drift.fit("grade", "categorical", reference)
    assert bins.categories == ("A", "B", "C")
    assert bins.shares == pytest.approx((0.25, 0.25, 0.25, 0.0, 0.25))
    month = pl.Series(["A", "B", "C", "Z"] * 25)
    measured = drift.measure(bins, month)
    assert measured.new_values == 25
    assert measured.null_share == 0.0
    assert math.isfinite(measured.psi)
    assert measured.psi > 0.25
    # An empty bin counts with the floor of 0.01%, never infinity: the new bin goes from
    # 0 to 25% and the missing one from 25% to 0.
    assert measured.psi == pytest.approx(2 * (0.25 - drift.FLOOR) * math.log(0.25 / drift.FLOOR))
    # A numeric variable: missing values in their bin, numbers out of range are new.
    numbers = drift.fit("dti", "numeric", pl.Series([1.0, 2.0, 3.0, 4.0]))
    month_numbers = drift.measure(numbers, pl.Series([1.0, None, 9.0, float("nan")]))
    assert month_numbers.null_share == 0.5
    assert month_numbers.new_values == 1
    assert month_numbers.psi > 0


# T23.6
def test_ks_is_the_scipy_statistic_against_the_reference_sample() -> None:
    rng = np.random.default_rng(0)
    small = pl.Series(rng.normal(0, 1, 1_000))
    month = pl.Series(rng.normal(0.3, 1, 2_000))
    bins = drift.fit("x", "numeric", small)
    assert bins.sample == tuple(small.to_list()), "small references are kept whole"
    expected = ks_2samp(small.to_numpy(), month.to_numpy()).statistic
    assert drift.measure(bins, month).ks == pytest.approx(expected, abs=1e-12)
    large = pl.Series(rng.normal(0, 1, 20_000))
    sampled = drift.fit("x", "numeric", large)
    assert len(sampled.sample) == drift.SAMPLE
    assert drift.fit("x", "numeric", large).sample == sampled.sample, "a fixed seed"
    assert drift.measure(sampled, month).ks == pytest.approx(
        ks_2samp(np.asarray(sampled.sample), month.to_numpy()).statistic, abs=1e-12
    )
    # Not for categorical variables.
    assert (
        drift.measure(drift.fit("g", "categorical", pl.Series(["A"])), pl.Series(["A"])).ks is None
    )


# T25.1
def test_first_year_share_by_term_and_grade_with_the_term_for_small_grades() -> None:
    rows = [(36, "A", 100, 40), (36, "B", 60, 30), (36, "G", 10, 9), (60, "C", 49, 10)]
    shares = outcomes.first_year(rows)
    assert shares.share(36, "A") == 0.40
    assert shares.share(36, "B") == 0.50
    # G has fewer than 50 defaults: the share of all 36-month defaults, 79 of 170.
    assert shares.share(36, "G") == pytest.approx(79 / 170)
    assert shares.share(60, "C") == pytest.approx(10 / 49)
    assert shares.share(36, "Z") == pytest.approx(79 / 170)
    assert shares.share(60, "A") == pytest.approx(10 / 49)
    with pytest.raises(ValueError, match="early"):
        outcomes.first_year([(36, "A", 10, 11)])


def _cohort(n: int, early: int, pd_: float, grade: str = "A") -> pl.DataFrame:
    return pl.DataFrame(
        {
            "term": [36] * n,
            "grade": [grade] * n,
            "pd": np.linspace(pd_ / 2, pd_ * 1.5, n),
            "early": [True] * early + [False] * (n - early),
        }
    )


# T25.3
def test_the_ratio_and_its_wilson_interval() -> None:
    shares = outcomes.first_year([(36, "A", 1_000, 400)])
    # Expected: mean PD 0.10 x 0.40 = 4% of 10,000 = 400 defaults.
    equal = outcomes.early_warning(_cohort(10_000, 400, 0.10), shares)[0]
    assert equal.expected_defaults == pytest.approx(400)
    assert equal.ratio == pytest.approx(1.0)
    assert equal.ratio_low < 1 < equal.ratio_high
    double = outcomes.early_warning(_cohort(10_000, 800, 0.10), shares)[0]
    assert double.ratio == pytest.approx(2.0)
    assert double.ratio_low > 1
    # The Wilson interval against its formula, and at the edges.
    low, high = outcomes.wilson(40, 100)
    z = outcomes.Z
    centre = (0.4 + z * z / 200) / (1 + z * z / 100)
    half = z * math.sqrt(0.4 * 0.6 / 100 + z * z / 40_000) / (1 + z * z / 100)
    assert (low, high) == pytest.approx((centre - half, centre + half))
    assert outcomes.wilson(0, 50)[0] == 0.0
    assert outcomes.wilson(50, 50)[1] == pytest.approx(1.0)
    with pytest.raises(ValueError, match="at least one"):
        outcomes.wilson(0, 0)
    # The PD orders the early defaults: AUC above one half when they have higher PD.
    ordered = _cohort(1_000, 100, 0.1).with_columns(early=pl.int_range(pl.len()) >= 900)
    assert outcomes.early_warning(ordered, shares)[0].auc == pytest.approx(1.0)


# T26.2 (the metrics themselves; the cohort and its timing are in the integration tests)
def test_performance_uses_the_metrics_of_promotion_and_the_returns_of_business() -> None:
    rng = np.random.default_rng(5)
    n = 2_000
    grade = rng.choice(["A", "B", "C"], n)
    pd_ = rng.uniform(0.02, 0.4, n)
    label = (rng.random(n) < pd_).astype(np.int16)
    label_with_unresolved = [None if i < 10 else int(v) for i, v in enumerate(label)]
    lgd = rng.uniform(0.5, 1.0, n)
    actual = np.where(label == 1, np.clip(lgd + rng.normal(0, 0.1, n), 0, 1.2), np.nan)
    funded = rng.integers(5, 30, n) * 1_000.0
    paid = np.where(label == 1, funded * 0.6, funded * 1.2)
    frame = pl.DataFrame(
        {
            "loan_id": np.arange(n),
            "term": [36] * n,
            "grade": grade,
            "pd": pd_,
            "lgd": lgd,
            "label": pl.Series(label_with_unresolved, dtype=pl.Int16),
            "lgd_actual": actual,
            "amount": np.where(np.arange(n) % 7 == 0, 50.0, 0.0),
            "funded_amnt": funded,
            "total_pymnt": paid,
            "collection_recovery_fee": np.zeros(n),
        },
        nan_to_null=True,
    )
    found = {p.segment: p for p in outcomes.performance(frame)}
    assert set(found) == {"all", "grade=A", "grade=B", "grade=C"}
    known = frame.filter(pl.col("label").is_not_null())
    y = known["label"].to_numpy().astype(np.float64)
    p = known["pd"].to_numpy()
    overall = found["all"]
    assert overall.unresolved == 10
    assert overall.loans == n - 10
    assert overall.auc == pytest.approx(compare.auc(y, p))
    assert overall.brier == pytest.approx(compare.brier(y, p))
    assert overall.calibration_error == pytest.approx(compare.calibration_error(y, p))
    a = known.filter(pl.col("grade") == "A")
    assert found["grade=A"].auc == pytest.approx(
        compare.auc(a["label"].to_numpy().astype(np.float64), a["pd"].to_numpy())
    )
    assert found["grade=A"].lgd_loans is None
    lgd_rows = known.filter(pl.col("lgd_actual").is_not_null())
    assert overall.lgd_loans == lgd_rows.height
    assert overall.lgd_rmse == pytest.approx(
        compare.rmse(lgd_rows["lgd_actual"].to_numpy(), lgd_rows["lgd"].to_numpy())
    )
    assert overall.lgd_level == pytest.approx(
        lgd_rows["lgd"].mean() - lgd_rows["lgd_actual"].mean()  # type: ignore[operator]
    )
    bought = known.filter(pl.col("amount") > 0)
    values, _ = business.received(
        bought.select(pl.col("loan_id").alias("id")),
        bought.select(
            pl.col("loan_id").alias("id"), "label", "funded_amnt", "total_pymnt",
            "collection_recovery_fee",
        ),
    )  # fmt: skip
    invested = float(bought["amount"].sum())
    assert overall.purchases == bought.height
    assert overall.invested == invested
    assert overall.realised_return == pytest.approx(
        float(np.sum(values / business.NOTE * bought["amount"].to_numpy())) / invested - 1
    )
