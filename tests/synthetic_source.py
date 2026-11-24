"""A small made-up source file in the format of the Lending Club snapshot (step 4.1 tests).

The flow tests (T16.7 to T16.10) run the whole monthly cycle, simulator included, so they
need a source file that the simulator reads, that passes every validation rule month by
month, and whose training set at the cutoff has enough defaults for the PD to cover the
36-month term (D-070). Rows start from ``tests/valid_rows.py`` and change only what must
vary: the listing month, the risk features and the outcome.

At ``CUTOFF`` = 2012-01 the matured 36-month loans are those listed up to 2008-08;
validation is 2008-03 to 2008-08 (D-069) and training 2007-06 to 2008-02. Months up to
2008-11 carry the full volume, for the later cutoffs of the clock tests (T17); later
months carry a few loans each, so every month has a delivery.
"""

import gzip
import hashlib
from datetime import date
from pathlib import Path
from typing import Final

import numpy as np
import polars as pl

from credit_risk.contracts import LISTING_COLUMNS, OUTCOME_ONLY_COLUMNS
from tests.valid_rows import listing, month_text, outcome

CUTOFF: Final = date(2012, 1, 1)
FIRST: Final = date(2007, 6, 1)
#: Newest matured listing month at the cutoff (T - 36 - 5).
MATURED: Final = date(2008, 8, 1)
#: Months up to here carry the full volume and are paid off or charged off, so that the
#: clock tests (T17) also have enough defaults at later cutoffs, up to 2012-06.
FULL: Final = date(2008, 11, 1)
#: Loans per listing month: enough defaults in training and in validation (D-070).
PER_MATURED_MONTH: Final = 220
PER_LATER_MONTH: Final = 15
#: Payment month of the loans still running: after the cutoff, so none resolves before it.
RUNNING_UNTIL: Final = date(2012, 6, 1)

_GRADES: Final = "ABCDEFG"


def _add(period: date, months: int) -> date:
    index = period.year * 12 + period.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def _months(first: date, last: date) -> list[date]:
    months = [first]
    while months[-1] < last:
        months.append(_add(months[-1], 1))
    return months


def _money(x: float) -> str:
    return f"{x:.2f}"


def source_rows(
    seed: int = 0, *, until: date = CUTOFF, bad: tuple[date, str, str] | None = None
) -> list[dict[str, str | None]]:
    """Every loan from ``FIRST`` to ``until``; ``bad`` = (month, column, value) breaks one row.

    The months up to the cutoff are the same whatever ``until`` is, so their deliveries
    are byte for byte the same.
    """
    rng = np.random.default_rng(seed)
    rows: list[dict[str, str | None]] = []
    next_id = 1
    for period in _months(FIRST, until):
        n = PER_MATURED_MONTH if period <= FULL else PER_LATER_MONTH
        for _ in range(n):
            loan_id = next_id
            next_id += 1
            int_rate = float(rng.uniform(6, 24))
            fico = int(round(rng.uniform(660, 820) / 5) * 5)
            dti = float(rng.uniform(0, 30))
            income = float(np.exp(rng.normal(11, 0.4)))
            inq = int(rng.poisson(1))
            score = 0.15 * (int_rate - 15) - 0.012 * (fico - 740) + 0.03 * (dti - 15) + 0.2 * inq
            p_bad = 1 / (1 + np.exp(-(score - 1.2)))
            grade = _GRADES[min(int((int_rate - 6) / 18 * 7), 6)]
            amount = float(rng.integers(5, 25) * 1000)
            row = listing(
                loan_id,
                period,
                int_rate=f"{int_rate:.2f}",
                grade=grade,
                sub_grade=f"{grade}{int(rng.integers(1, 6))}",
                fico_range_low=f"{fico}.0",
                fico_range_high=f"{fico + 4}.0",
                dti=f"{dti:.2f}",
                annual_inc=_money(income),
                inq_last_6mths=f"{inq}.0",
                loan_amnt=_money(amount),
                installment=_money(amount * (int_rate / 1200) / (1 - (1 + int_rate / 1200) ** -36)),
                revol_util=f"{rng.uniform(0, 100):.1f}",
            )
            row.update(
                {k: v for k, v in outcome(loan_id, period).items() if k in OUTCOME_ONLY_COLUMNS}
            )
            row.update(_outcome(rng, period, amount, int_rate, bool(rng.random() < p_bad)))
            rows.append(row)
    if bad is not None:
        month, column, value = bad
        first = next(r for r in rows if r["issue_d"] == month_text(month))
        first[column] = value
    return rows


def _outcome(
    rng: np.random.Generator, period: date, amount: float, int_rate: float, defaults: bool
) -> dict[str, str | None]:
    """The final state of a loan: paid at 36 months, charged off, or still running."""
    interest = amount * int_rate / 100 * 1.5
    if period > FULL and not defaults:
        paid = amount * 0.3
        return {
            "loan_status": "Current",
            "funded_amnt": _money(amount),
            "funded_amnt_inv": _money(amount),
            "out_prncp": _money(amount - paid),
            "out_prncp_inv": _money(amount - paid),
            "total_pymnt": _money(paid + 100),
            "total_pymnt_inv": _money(paid + 100),
            "total_rec_prncp": _money(paid),
            "total_rec_int": "100.00",
            "last_pymnt_d": month_text(RUNNING_UNTIL),
            "last_credit_pull_d": month_text(RUNNING_UNTIL),
        }
    if not defaults:
        last = _add(period, 36)
        return {
            "loan_status": "Fully Paid",
            "funded_amnt": _money(amount),
            "funded_amnt_inv": _money(amount),
            "total_pymnt": _money(amount + interest),
            "total_pymnt_inv": _money(amount + interest),
            "total_rec_prncp": _money(amount),
            "total_rec_int": _money(interest),
            "last_pymnt_d": month_text(last),
            "last_credit_pull_d": month_text(last),
        }
    months_paid = int(rng.integers(2, 24))
    last = _add(period, months_paid)
    principal = amount * months_paid / 48
    recovered = float(rng.uniform(0, 0.3)) * (amount - principal)
    paid_interest = interest * months_paid / 36
    return {
        "loan_status": "Charged Off",
        "funded_amnt": _money(amount),
        "funded_amnt_inv": _money(amount),
        "total_pymnt": _money(principal + paid_interest + recovered),
        "total_pymnt_inv": _money(principal + paid_interest + recovered),
        "total_rec_prncp": _money(principal),
        "total_rec_int": _money(paid_interest),
        "recoveries": _money(recovered),
        "collection_recovery_fee": _money(recovered * 0.1),
        "last_pymnt_d": month_text(last),
        "last_credit_pull_d": month_text(_add(last, 5)),
    }


def write_source(
    path: Path,
    seed: int = 0,
    *,
    until: date = CUTOFF,
    bad: tuple[date, str, str] | None = None,
) -> str:
    """Write the source as the real one is (gzip CSV, every column); return its SHA-256."""
    columns = [*LISTING_COLUMNS, *OUTCOME_ONLY_COLUMNS]
    frame = pl.DataFrame(
        source_rows(seed, until=until, bad=bad), schema=dict.fromkeys(columns, pl.String)
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
        gz.write(frame.write_csv().encode())
    return hashlib.sha256(path.read_bytes()).hexdigest()
