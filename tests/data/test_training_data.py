"""T10.6 and T12.6: the training procedures on the real first training set, at T0.

Needs the deliveries in ``data/landing`` (``make publish PERIOD=2019-03``) and the
compose Postgres (``make up``). The training set comes from the fixtures of
``conftest.py``, shared with the snapshot data tests.
"""

from dataclasses import replace

import numpy as np
import polars as pl
import pytest

from credit_risk import battery, registry
from credit_risk.compare import interval
from credit_risk.lgd import lgd_rows, train_lgd
from credit_risk.snapshot import FEATURES, LGD, SPLIT, Manifest
from credit_risk.storage import LocalStore
from credit_risk.train import prepare_frame, train_pd
from tests.data.conftest import T0

pytestmark = pytest.mark.data

RESAMPLES = 1_000
#: Largest level correction (D-094) T12.6 accepts without a look (drift at T0: 0.05).
MAX_SHIFT = 0.10


@pytest.fixture(scope="module")
def listings(first: Manifest, t0_store: LocalStore) -> pl.DataFrame:
    return pl.read_parquet(t0_store.local(first.version, FEATURES))


# T10.6
def test_the_model_trained_at_t0_passes_the_battery(listings: pl.DataFrame) -> None:
    training = train_pd(prepare_frame(listings), T0)
    result = battery.run(training.chosen, listings.filter(pl.col(SPLIT) == "validation"))
    print(f"\nPD chosen at T0: {training.chosen.name}; battery details: {result.details}")
    assert result.passed, {k: result.details.get(k) for k, v in result.checks.items() if not v}


def _observed_mean_interval(y: np.ndarray, seed: int = 0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    means = [y[rng.integers(0, y.size, y.size)].mean() for _ in range(RESAMPLES)]
    low, high = np.percentile(means, [2.5, 97.5])
    return float(low), float(high)


# T12.6
def test_the_lgd_at_t0_is_on_the_level_of_the_observed_lgd(listings: pl.DataFrame) -> None:
    frame = prepare_frame(listings)
    seen: set[int] = set()
    training = train_lgd(frame, T0, (36,), seen=lambda ids: seen.update(ids.to_list()))
    train = lgd_rows(frame.filter(pl.col(SPLIT) == "train"))
    validation = lgd_rows(frame.filter(pl.col(SPLIT) == "validation"))
    assert (train.height, validation.height) == (992, 344)
    assert seen <= set(train["id"].to_list())

    verdict = registry.judge(
        "lgd",
        training.chosen,
        training.baseline,
        lgd_rows(listings.filter(pl.col(SPLIT) == "validation")),
    )
    champion = training.chosen if verdict.passed else training.baseline
    models = (training.ridge, training.lightgbm, training.baseline)
    y = validation[LGD].to_numpy()
    rmse = {m.name: interval(y, m.predict_lgd(validation).to_numpy(), "rmse") for m in models}
    shifts = {m.name: m.shift for m in models}
    predicted = float(np.mean(champion.predict_lgd(validation).to_numpy()))
    before = float(np.mean(replace(champion, shift=0.0).predict_lgd(validation).to_numpy()))
    low, high = _observed_mean_interval(y)
    print(
        f"\nLGD at T0, RMSE (value, low, high): {rmse}"
        f"\nchosen {training.chosen.name} against the baseline: {verdict.metrics}"
        f"\nlevel shifts (D-094): {shifts}"
        f"\nchampion: {champion.name}; mean predicted {before:.3f} before the correction, "
        f"{predicted:.3f} after; observed {y.mean():.3f} [{low:.3f}, {high:.3f}]"
    )
    # No winner is fixed (D-087). The level is set on validation (D-094), so the mean
    # matches up to the clipping to [0, 1]; a shift above 0.10 is far more than the drift
    # measured at T0 (about 0.05) and must be looked at before going on.
    assert abs(predicted - float(y.mean())) < 0.005
    assert all(abs(shift) <= MAX_SHIFT for shift in shifts.values()), shifts
