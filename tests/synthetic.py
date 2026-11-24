"""Made-up training sets with a known risk structure, for the training tests (F3).

The rows look like a training set version (D-058): the listing columns the features read,
plus ``emp_title`` and ``addr_state`` (unused by any model), the label, the LGD label and
the split, which follows D-069 (the last 6 matured months of each term are validation).
Risk rises with ``int_rate``, ``dti``, ``revol_util``, ``inq_last_6mths``,
``delinq_2yrs`` and ``pub_rec``, and falls with FICO, income and credit history, so a
sensible model learns the directions of D-080.
"""

from datetime import date

import numpy as np
import polars as pl

from credit_risk.features import INPUTS
from credit_risk.snapshot import LABEL, LGD, SPLIT

CUTOFF = date(2014, 1, 1)
GRADES = ("A", "B", "C", "D", "E", "F", "G")


def _month(cutoff: date, back: int) -> date:
    index = cutoff.year * 12 + cutoff.month - 1 - back
    return date(index // 12, index % 12 + 1, 1)


def training_set(
    n: int = 6_000,
    *,
    seed: int = 0,
    cutoff: date = CUTOFF,
    terms: tuple[int, ...] = (36,),
    months: int = 30,
    strength: float = 1.0,
) -> pl.DataFrame:
    """``n`` matured loans listed over ``months`` months before the newest matured one.

    ``strength`` scales how much the features explain: 0 gives pure noise.
    """
    rng = np.random.default_rng(seed)
    term = rng.choice(np.array(terms, dtype=np.int16), n)
    # Months between listing and cutoff: matured (term + 5) plus up to ``months`` more.
    back = term + 5 + rng.integers(0, months, n)
    int_rate = rng.uniform(6, 26, n)
    fico_low = np.round(rng.uniform(660, 820, n) / 5) * 5
    dti = rng.uniform(0, 35, n)
    revol_util = rng.uniform(0, 100, n)
    annual_inc = np.exp(rng.normal(11, 0.5, n))
    inq = rng.poisson(1, n).astype(float)
    delinq = rng.poisson(0.3, n).astype(float)
    pub_rec = rng.poisson(0.1, n).astype(float)
    history = rng.integers(36, 360, n)
    score = strength * (
        0.12 * (int_rate - 16)
        + 0.02 * (dti - 17)
        + 0.008 * (revol_util - 50)
        + 0.15 * inq
        + 0.2 * delinq
        + 0.2 * pub_rec
        - 0.01 * (fico_low - 740)
        - 0.4 * (np.log(annual_inc) - 11)
        - 0.002 * (history - 200)
    )
    p = 1 / (1 + np.exp(-(score - 1.8)))
    label = (rng.random(n) < p).astype(np.int16)
    grade_index = np.clip(((int_rate - 6) / 20 * 7).astype(int), 0, 6)
    grade = np.array(GRADES)[grade_index]
    sub_grade = np.char.add(grade, (rng.integers(1, 6, n)).astype(str))
    lgd = np.where(
        label == 1,
        np.clip(0.6 + strength * 0.01 * (int_rate - 16) + rng.normal(0, 0.2, n), -0.2, 1.1),
        np.nan,
    )
    issue = [_month(cutoff, int(b)) for b in back]
    earliest = [_month(d, int(h)) for d, h in zip(issue, history, strict=True)]
    split = np.where(back <= term + 5 + 6, "validation", "train")
    missing_delinq = rng.random(n) < 0.5
    frame = pl.DataFrame(
        {
            "id": np.arange(1, n + 1, dtype=np.int64),
            "loan_amnt": rng.integers(1, 35, n) * 1_000.0,
            "term": term,
            "int_rate": int_rate,
            "emp_length": rng.integers(0, 11, n).astype(np.int16),
            "annual_inc": annual_inc,
            "dti": dti,
            "delinq_2yrs": delinq,
            "inq_last_6mths": inq,
            "mths_since_last_delinq": np.where(missing_delinq, np.nan, rng.integers(0, 80, n)),
            "mths_since_last_record": np.where(pub_rec > 0, rng.integers(0, 100, n), np.nan),
            "open_acc": rng.integers(1, 30, n).astype(float),
            "pub_rec": pub_rec,
            "revol_bal": rng.integers(0, 50_000, n).astype(float),
            "revol_util": revol_util,
            "total_acc": rng.integers(5, 60, n).astype(float),
            "collections_12_mths_ex_med": np.zeros(n),
            "acc_now_delinq": np.zeros(n),
            "chargeoff_within_12_mths": np.zeros(n),
            "delinq_amnt": np.zeros(n),
            "tax_liens": np.zeros(n),
            "fico_range_low": fico_low,
            "fico_range_high": fico_low + 4,
            "issue_d": issue,
            "earliest_cr_line": earliest,
            "grade": grade,
            "sub_grade": sub_grade,
            "home_ownership": rng.choice(["RENT", "OWN", "MORTGAGE"], n),
            "verification_status": rng.choice(["Not Verified", "Source Verified", "Verified"], n),
            "purpose": rng.choice(["debt_consolidation", "credit_card", "other"], n),
            "initial_list_status": rng.choice(["f", "w"], n),
            "application_type": np.full(n, "Individual"),
            "disbursement_method": np.full(n, "Cash"),
            "emp_title": rng.choice(["Teacher", "Nurse", "Engineer"], n),
            "addr_state": rng.choice(["CA", "NY", "TX"], n),
            LABEL: label,
            LGD: lgd,
            SPLIT: split,
        },
        nan_to_null=True,
    )
    missing = set(INPUTS) - set(frame.columns)
    assert not missing, missing
    return frame.with_columns(
        pl.col("mths_since_last_delinq", "mths_since_last_record").cast(pl.Float64)
    )
