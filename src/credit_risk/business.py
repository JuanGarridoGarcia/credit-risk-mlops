"""The buy rule and the business metric (D-084, D-085, D-096, D-007).

An investor decides on each loan as it is listed (D-008): buy one 25 dollar note when the
loan's expected return is at least a minimum. Each month at most K notes are bought,
K being a share of the loans listed the month before; loans that pass are bought in
listing order (the order of their ids) until K is reached. Money not invested earns
nothing. The minimum is chosen on validation only (D-096); the realised return is
measured on the following year, with the loans' final outcomes.
"""

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Final

import numpy as np
import numpy.typing as npt
import polars as pl

from credit_risk.features import build_features
from credit_risk.model import LGDModel, PDModel

#: One note per loan bought (D-085).
NOTE: Final = 25.0
#: Monthly cap: this share of the loans listed the month before (D-085).
CAP: Final = 0.10
#: The caps the business metric is also reported at (D-085).
SENSITIVITY: Final = (0.05, 0.10, 0.20)
#: Candidate minimum expected returns, from a loss of 10% to a gain of 30%.
GRID: Final = tuple(round(float(m), 3) for m in np.arange(-0.10, 0.3001, 0.005))

Array = npt.NDArray[np.float64]
Seen = Callable[[pl.Series], None]


def scheduled_interest(int_rate: Array, term: Array) -> Array:
    """Total interest of a fully amortised loan, as a share of its amount (D-084).

    ``int_rate`` in percent a year, ``term`` in months.
    """
    rate = np.asarray(int_rate, dtype=np.float64) / 1200
    n = np.asarray(term, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        payment = np.where(rate > 0, rate / (1 - (1 + rate) ** -n), 1 / n)
    return np.asarray(n * payment - 1, dtype=np.float64)


def expected_return(pd_: Array, lgd: Array, interest: Array) -> Array:
    """``(1 - PD) x scheduled interest - PD x LGD``; NaN where the PD or LGD is missing."""
    return np.asarray((1 - pd_) * interest - pd_ * lgd, dtype=np.float64)


def month(d: date) -> date:
    return date(d.year, d.month, 1)


def previous(m: date) -> date:
    return date(m.year - 1, 12, 1) if m.month == 1 else date(m.year, m.month - 1, 1)


def caps(listed: Mapping[date, int], months: list[date], share: float = CAP) -> dict[date, int]:
    """K of each month: ``share`` of the loans listed the month before, rounded down."""
    return {m: math.floor(share * listed.get(previous(m), 0)) for m in months}


def buy(candidates: pl.DataFrame, minimum: float, k: Mapping[date, int]) -> pl.DataFrame:
    """The loans bought: ``candidates`` has ``id``, ``issue_d`` and ``expected_return``.

    A loan with no expected return (no PD or LGD, D-070) is never bought.
    """
    passing = candidates.filter(
        pl.col("expected_return").is_not_null()
        & pl.col("expected_return").is_not_nan()
        & (pl.col("expected_return") >= minimum)
    ).with_columns(month=pl.col("issue_d").dt.truncate("1mo"))
    limits = pl.DataFrame(
        {"month": list(k), "k": list(k.values())}, schema={"month": pl.Date, "k": pl.Int64}
    )
    return (
        passing.sort("id")
        .with_columns(rank=pl.int_range(pl.len()).over("month"))
        .join(limits, on="month", how="inner")
        .filter(pl.col("rank") < pl.col("k"))
        .drop("rank", "k", "month")
    )


@dataclass(frozen=True)
class Portfolio:
    """What an investor's notes realised (D-007)."""

    notes: int
    budget: float
    invested: float
    received: float
    defaults: int
    lost: float

    @property
    def net_return(self) -> float:
        """Money made over the money available; idle money counts as zero (D-085)."""
        return (self.received - self.invested) / self.budget if self.budget else 0.0

    @property
    def default_rate(self) -> float:
        return self.defaults / self.notes if self.notes else 0.0

    @property
    def loss(self) -> float:
        """Money not recovered from defaulted notes, over the money invested."""
        return self.lost / self.invested if self.invested else 0.0


def realise(bought: pl.DataFrame, outcomes: pl.DataFrame, k: Mapping[date, int]) -> Portfolio:
    """Realised result of one note in each ``bought`` loan.

    ``outcomes``: ``id``, ``label``, ``funded_amnt``, ``total_pymnt`` and
    ``collection_recovery_fee``; a note receives its share of what the borrower paid,
    less the collection fee taken from recoveries.
    """
    rows = bought.select("id").join(outcomes, on="id", how="left")
    if rows["funded_amnt"].null_count():
        raise ValueError("a bought loan has no outcome")
    share = (rows["total_pymnt"] - rows["collection_recovery_fee"].fill_null(0)) / rows[
        "funded_amnt"
    ]
    received = (NOTE * share).to_numpy()
    bad = rows["label"].to_numpy() == 1
    return Portfolio(
        notes=rows.height,
        budget=NOTE * sum(k.values()),
        invested=NOTE * rows.height,
        received=float(received.sum()),
        defaults=int(bad.sum()),
        lost=float(np.clip(NOTE - received[bad], 0, None).sum()),
    )


def choose_minimum(
    candidates: pl.DataFrame,
    outcomes: pl.DataFrame,
    k: Mapping[date, int],
    grid: tuple[float, ...] = GRID,
    seen: Seen | None = None,
) -> float:
    """The minimum of ``grid`` with the highest realised return on ``candidates``
    (validation only, D-096); a tie goes to the smallest minimum."""
    if seen is not None:
        seen(candidates["id"])
    best, best_return = grid[0], -math.inf
    for minimum in grid:
        value = realise(buy(candidates, minimum, k), outcomes, k).net_return
        if value > best_return:
            best, best_return = minimum, value
    return best


def candidates(pd_model: PDModel, lgd_model: LGDModel, listings: pl.DataFrame) -> pl.DataFrame:
    """``id``, ``issue_d`` and expected return of every listing under one pair of models."""
    features = build_features(listings)
    pd_ = pd_model.predict_pd(features).to_numpy()
    lgd = lgd_model.predict_lgd(features).to_numpy()
    interest = scheduled_interest(features["int_rate"].to_numpy(), features["term"].to_numpy())
    return listings.select("id", "issue_d").with_columns(
        expected_return=pl.Series(expected_return(pd_, lgd, interest)).fill_nan(None)
    )
