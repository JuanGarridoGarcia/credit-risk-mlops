"""T21.1: the simulated investor's rule, by hand (D-085, D-123 to D-129).

The rest of the replayer (months, order inside ``advance``, failures, the whole story)
runs against the API in ``tests/integration/test_clock.py``.
"""

from datetime import date
from typing import Any

import polars as pl

from credit_risk import business
from credit_risk.simulator.replayer import NOTE, choose, k_of

MONTH = date(2014, 2, 1)
MINIMUM = 0.10


def _answer(loan_id: int, expected_return: float | None, *, rule: bool = True) -> dict[str, Any]:
    """An answer of the API as the replayer reads it."""
    covered = expected_return is not None
    threshold = None
    if expected_return is not None:
        threshold = {
            "available": rule,
            "minimum": MINIMUM if rule else None,
            "passes": expected_return >= MINIMUM if rule else None,
        }
    return {
        "prediction_id": 1_000 + loan_id,
        "loan_id": loan_id,
        "covered": covered,
        "expected_return": expected_return,
        "threshold": threshold,
    }


# T21.1
def test_the_investor_buys_what_passes_in_listing_order_up_to_k() -> None:
    # K: 10% of the loans listed the month before, rounded down.
    assert k_of(MONTH, 15_269) == 1_526
    assert k_of(MONTH, 9) == 0
    assert k_of(date(2014, 1, 1), 100) == 10
    assert NOTE == 25

    # Listed in this order; ids say the listing order (D-085).
    answers = [
        _answer(7, 0.20),
        _answer(3, 0.05),  # below the minimum
        _answer(5, None),  # term not covered: no risk, never bought
        _answer(1, 0.12),
        _answer(9, 0.30),
        _answer(4, 0.10),  # exactly the minimum passes
    ]
    bought = choose(answers, MONTH, 2)
    assert [a["loan_id"] for a in bought] == [1, 4]
    assert [a["loan_id"] for a in choose(answers, MONTH, 3)] == [1, 4, 7]

    # Fewer pass than K: all of them, and the rest of the budget stays idle.
    assert [a["loan_id"] for a in choose(answers, MONTH, 10)] == [1, 4, 7, 9]
    # K above every loan of the month: only those that pass, no error.
    assert [a["loan_id"] for a in choose(answers, MONTH, 1_000_000)] == [1, 4, 7, 9]
    assert choose(answers, MONTH, 0) == []
    assert choose([], MONTH, 5) == []

    # No buy rule for the pair in use: nothing passes, nothing is bought.
    assert choose([_answer(2, 0.5, rule=False)], MONTH, 5) == []

    # The same as the business metric of F3 on the same loans.
    candidates = pl.DataFrame(
        {
            "id": [a["loan_id"] for a in answers],
            "issue_d": [MONTH] * len(answers),
            "expected_return": [a["expected_return"] for a in answers],
        },
        schema={"id": pl.Int64, "issue_d": pl.Date, "expected_return": pl.Float64},
    )
    for k in (0, 1, 2, 3, 4, 10):
        expected = business.buy(candidates, MINIMUM, {MONTH: k})["id"].to_list()
        assert [a["loan_id"] for a in choose(answers, MONTH, k)] == expected, k
