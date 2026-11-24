"""T7.3 and T7.4: the inner split for tuning, and the same seed giving the same result."""

from datetime import date

import numpy as np
import polars as pl
import pytest

from credit_risk.snapshot import SPLIT
from credit_risk.train import (
    LIGHTGBM_TRIALS,
    LOGISTIC_GRID,
    inner_split,
    prepare_frame,
    train_pd,
)
from tests.synthetic import CUTOFF, training_set

T = date(2014, 1, 1)


def _loans(term: int, months_before: list[int]) -> pl.DataFrame:
    issue = [
        date((T.year * 12 + T.month - 1 - m) // 12, (T.year * 12 + T.month - 1 - m) % 12 + 1, 1)
        for m in months_before
    ]
    return pl.DataFrame(
        {
            "id": list(range(len(issue))),
            "term": [term] * len(issue),
            "issue_d": issue,
            "months": months_before,
        }
    )


# T7.3
@pytest.mark.parametrize(
    ("term", "inner_months", "edges"),
    [
        # 36 months: training listings are 48 or more months before T (D-069); the inner
        # validation is 48 to 53, the inner training 54 and more.
        (36, range(48, 54), (53, 54)),
        (60, range(72, 78), (77, 78)),
    ],
)
def test_the_inner_split_is_the_last_six_training_months_of_each_term(
    term: int, inner_months: range, edges: tuple[int, int]
) -> None:
    months = list(range(inner_months.start, inner_months.stop + 6))
    inner_train, inner_validation = inner_split(_loans(term, months), T)
    assert sorted(inner_validation["months"].to_list()) == list(inner_months)
    assert min(inner_train["months"].to_list()) == inner_months.stop
    last_inner, first_train = edges
    assert last_inner in inner_validation["months"].to_list()
    assert first_train in inner_train["months"].to_list()


def test_the_search_never_sees_a_validation_loan() -> None:
    frame = prepare_frame(training_set(seed=2))
    seen: set[int] = set()
    train_pd(frame, CUTOFF, trials=5, seen=lambda ids: seen.update(ids.to_list()))
    validation = set(frame.filter(pl.col(SPLIT) == "validation")["id"].to_list())
    training = set(frame.filter(pl.col(SPLIT) == "train")["id"].to_list())
    assert seen, "the search recorded nothing"
    assert seen.isdisjoint(validation)
    assert seen <= training


# T7.4
def test_the_same_seed_gives_the_same_model() -> None:
    frame = prepare_frame(training_set(seed=3))
    first = train_pd(frame, CUTOFF, seed=7)
    second = train_pd(frame, CUTOFF, seed=7)
    for name in ("logistic", "lightgbm"):
        assert first.searches[name].params == second.searches[name].params
    validation = frame.filter(pl.col(SPLIT) == "validation")
    for a, b in (
        (first.logistic, second.logistic),
        (first.lightgbm, second.lightgbm),
        (first.chosen, second.chosen),
    ):
        assert np.array_equal(
            a.predict_pd(validation).to_numpy(), b.predict_pd(validation).to_numpy()
        )
    # The budget is counted in trials (D-074).
    assert len(first.searches["logistic"].trials) == len(LOGISTIC_GRID) == 20
    assert len(first.searches["lightgbm"].trials) == LIGHTGBM_TRIALS == 50
