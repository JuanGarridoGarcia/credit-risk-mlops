"""T15.1 to T15.6: the buy rule and the business metric (D-084, D-085, D-096) by hand."""

from datetime import date

import numpy as np
import polars as pl
import pytest

from credit_risk.business import (
    NOTE,
    buy,
    caps,
    choose_minimum,
    expected_return,
    realise,
    scheduled_interest,
)


# T15.1
def test_scheduled_interest_by_hand() -> None:
    rates, terms = np.array([7.0, 20.0, 0.0]), np.array([36, 36, 36])
    by_hand = []
    for rate in (7.0, 20.0):
        r = rate / 1200
        payment = r / (1 - (1 + r) ** -36)
        by_hand.append(36 * payment - 1)
    found = scheduled_interest(rates, terms)
    assert found[:2] == pytest.approx(by_hand)
    assert found[:2] == pytest.approx([0.111, 0.338], abs=1e-3)  # the examples of D-084
    assert found[2] == 0.0


# T15.2
def test_expected_return_by_hand_and_no_pd_is_never_bought() -> None:
    interest = scheduled_interest(np.array([7.0, 20.0]), np.array([36, 36]))
    found = expected_return(np.array([0.04, 0.25]), np.array([0.6, 0.6]), interest)
    assert found == pytest.approx([0.96 * interest[0] - 0.024, 0.75 * interest[1] - 0.15])
    assert found == pytest.approx([0.083, 0.103], abs=5e-4)
    uncovered = expected_return(np.array([np.nan]), np.array([0.6]), np.array([0.3]))
    candidates = pl.DataFrame(
        {"id": [1, 2], "issue_d": [date(2014, 2, 1)] * 2, "expected_return": [uncovered[0], None]}
    )
    assert buy(candidates, -1.0, {date(2014, 2, 1): 10}).height == 0


# T15.3
def test_the_monthly_cap_and_the_listing_order() -> None:
    listed = {date(2014, 1, 1): 59, date(2014, 2, 1): 20}
    k = caps(listed, [date(2014, 2, 1), date(2014, 3, 1)])
    assert k == {date(2014, 2, 1): 5, date(2014, 3, 1): 2}  # floor(5.9), floor(2.0)
    candidates = pl.DataFrame(
        {
            "id": [7, 3, 9, 1, 5, 2, 8, 4],
            "issue_d": [date(2014, 2, 1)] * 6 + [date(2014, 3, 1)] * 2,
            "expected_return": [0.2, 0.2, 0.01, 0.2, 0.2, 0.2, 0.2, 0.2],
        }
    )
    bought = buy(candidates, 0.05, k)
    # February: passing ids in listing order 1, 2, 3, 5, 7 (9 fails), five allowed.
    # March: 4 and 8, both within the cap of two.
    assert sorted(bought["id"].to_list()) == [1, 2, 3, 4, 5, 7, 8]
    tight = buy(candidates, 0.05, {date(2014, 2, 1): 2, date(2014, 3, 1): 1})
    assert sorted(tight["id"].to_list()) == [1, 2, 4]


# T15.4
def test_realised_return_by_hand() -> None:
    outcomes = pl.DataFrame(
        {
            "id": [1, 2],
            "label": [0, 1],
            "funded_amnt": [10_000.0, 5_000.0],
            "total_pymnt": [11_500.0, 3_000.0],  # paid off; defaulted after some payments
            "collection_recovery_fee": [0.0, 100.0],
        }
    )
    k = {date(2014, 2, 1): 4}  # four notes allowed, two bought: half the money idle
    result = realise(pl.DataFrame({"id": [1, 2]}), outcomes, k)
    received = NOTE * 1.15 + NOTE * (2_900 / 5_000)
    assert result.budget == 4 * NOTE
    assert result.invested == 2 * NOTE
    assert result.received == pytest.approx(received)
    assert result.net_return == pytest.approx((received - 2 * NOTE) / (4 * NOTE))
    assert result.default_rate == 0.5
    assert result.loss == pytest.approx((NOTE - NOTE * 0.58) / (2 * NOTE))


def _market(n: int, seed: int, months: list[date]) -> tuple[pl.DataFrame, pl.DataFrame, np.ndarray]:
    """Made-up loans: a true PD, the rate a little above the risk, outcomes drawn from it."""
    rng = np.random.default_rng(seed)
    true_pd = rng.uniform(0.02, 0.45, n)
    rate = np.clip(6 + 30 * true_pd + rng.normal(0, 3, n), 5, 28)
    bad = rng.random(n) < true_pd
    interest = scheduled_interest(rate, np.full(n, 36))
    funded = np.full(n, 10_000.0)
    paid = np.where(bad, funded * rng.uniform(0.2, 0.7, n), funded * (1 + interest))
    loans = pl.DataFrame(
        {"id": np.arange(n), "issue_d": [months[i % len(months)] for i in range(n)], "rate": rate}
    )
    outcomes = pl.DataFrame(
        {
            "id": np.arange(n),
            "label": bad.astype(int),
            "funded_amnt": funded,
            "total_pymnt": paid,
            "collection_recovery_fee": np.zeros(n),
        }
    )
    return loans, outcomes, true_pd


# T15.5
def test_the_minimum_is_chosen_on_validation_only() -> None:
    months = [date(2010, m, 1) for m in range(1, 7)]
    loans, outcomes, true_pd = _market(3_000, 1, months)
    interest = scheduled_interest(loans["rate"].to_numpy(), np.full(loans.height, 36))
    candidates = loans.with_columns(
        expected_return=pl.Series(expected_return(true_pd, np.full(loans.height, 0.6), interest))
    )
    k = caps(dict.fromkeys([date(2009, 12, 1), *months], 1_000), months)
    seen: set[int] = set()
    grid = (0.0, 0.05, 0.10, 0.15)
    chosen = choose_minimum(candidates, outcomes, k, grid, lambda ids: seen.update(ids.to_list()))
    returns = {m: realise(buy(candidates, m, k), outcomes, k).net_return for m in grid}
    best = max(returns.values())
    assert chosen == min(m for m, r in returns.items() if r == best)
    assert seen == set(candidates["id"].to_list())
    # A tie goes to the smallest minimum: two minimums that buy the same loans.
    tied = choose_minimum(candidates, outcomes, k, (0.15, 0.1500001))
    assert tied == 0.15


# T15.6
def test_an_informative_pd_earns_more_with_the_same_budget() -> None:
    months = [date(2010, m, 1) for m in range(1, 13)]
    loans, outcomes, true_pd = _market(12_000, 2, months)
    interest = scheduled_interest(loans["rate"].to_numpy(), np.full(loans.height, 36))
    lgd = np.full(loans.height, 0.6)
    noise = np.random.default_rng(3).permutation(true_pd)  # right level, no information
    k = caps(dict.fromkeys([date(2009, 12, 1), *months], 1_000), months)
    first, second = months[:6], months[6:]
    results = {}
    for name, pd_ in (("model", true_pd), ("baseline", noise)):
        candidates = loans.with_columns(
            expected_return=pl.Series(expected_return(pd_, lgd, interest))
        )
        choose_on = candidates.filter(pl.col("issue_d").is_in(first))
        measure_on = candidates.filter(pl.col("issue_d").is_in(second))
        k_choose = {m: k[m] for m in first}
        k_measure = {m: k[m] for m in second}
        minimum = choose_minimum(choose_on, outcomes, k_choose)
        results[name] = realise(buy(measure_on, minimum, k_measure), outcomes, k_measure)
    assert results["model"].budget == results["baseline"].budget
    assert results["model"].net_return > results["baseline"].net_return
