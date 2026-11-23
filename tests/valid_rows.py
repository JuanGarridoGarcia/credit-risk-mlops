"""Delivered rows (text, as in a delivery file) that pass every validation rule (step 2.2).

Tests start from these rows and change only what they test, so a failure comes from
that change and not from an unrelated rule (T4.2).
"""

from datetime import date
from typing import Final

from credit_risk.contracts import LISTING_COLUMNS, OUTCOME_COLUMNS

Row = dict[str, str | None]

#: A listing month where every rule and every contract change before C5 applies.
MONTH: Final = date(2015, 3, 1)

_FILLED_NUMBERS: Final = (
    "delinq_2yrs",
    "inq_last_6mths",
    "open_acc",
    "pub_rec",
    "total_acc",
    "collections_12_mths_ex_med",
    "acc_now_delinq",
    "tot_coll_amt",
    "tot_cur_bal",
    "total_rev_hi_lim",
    "acc_open_past_24mths",
    "chargeoff_within_12_mths",
    "delinq_amnt",
    "mo_sin_old_rev_tl_op",
    "mo_sin_rcnt_rev_tl_op",
    "mo_sin_rcnt_tl",
    "mort_acc",
    "num_accts_ever_120_pd",
    "num_actv_bc_tl",
    "num_actv_rev_tl",
    "num_bc_sats",
    "num_bc_tl",
    "num_il_tl",
    "num_op_rev_tl",
    "num_rev_accts",
    "num_rev_tl_bal_gt_0",
    "num_sats",
    "num_tl_30dpd",
    "num_tl_90g_dpd_24m",
    "num_tl_op_past_12m",
    "pub_rec_bankruptcies",
    "tax_liens",
    "tot_hi_cred_lim",
    "total_bal_ex_mort",
    "total_bc_limit",
    "total_il_high_credit_limit",
)


def month_text(period: date) -> str:
    """``2015-03-01`` as Lending Club writes it: ``Mar-2015``."""
    return f"{period:%b-%Y}"


def listing(id_: int, period: date = MONTH, /, **values: str | None) -> Row:
    """A valid individual listing of ``period``; ``values`` override columns."""
    row: Row = dict.fromkeys(LISTING_COLUMNS)
    row.update(dict.fromkeys(_FILLED_NUMBERS, "1.0"))
    row.update(
        {
            "id": str(id_),
            "loan_amnt": "10000.0",
            "term": " 36 months",
            "int_rate": "10.0",
            "installment": "322.67",
            "grade": "B",
            "sub_grade": "B3",
            "emp_length": "10+ years",
            "home_ownership": "RENT",
            "annual_inc": "60000.0",
            "verification_status": "Verified",
            "issue_d": month_text(period),
            "url": f"https://lendingclub.com/browse/loanDetail.action?loan_id={id_}",
            "purpose": "credit_card",
            "zip_code": "123xx",
            "addr_state": "CA",
            "dti": "12.5",
            "earliest_cr_line": "Sep-1990",
            "fico_range_low": "700.0",
            "fico_range_high": "704.0",
            "revol_bal": "5000.0",
            "revol_util": "40.0",
            "total_acc": "10.0",
            "open_acc": "5.0",
            "num_bc_tl": "4.0",
            "num_actv_bc_tl": "2.0",
            "initial_list_status": "w",
            "application_type": "Individual",
            "disbursement_method": "Cash",
        }
    )
    row.update(values)
    return row


def outcome(id_: int, period: date = MONTH, /, **values: str | None) -> Row:
    """A valid fully paid outcome resolved in ``period``; ``values`` override columns."""
    row: Row = dict.fromkeys(OUTCOME_COLUMNS)
    row.update(
        {
            "id": str(id_),
            "funded_amnt": "10000.0",
            "funded_amnt_inv": "10000.0",
            "loan_status": "Fully Paid",
            "pymnt_plan": "n",
            "out_prncp": "0.0",
            "out_prncp_inv": "0.0",
            "total_pymnt": "10500.0",
            "total_pymnt_inv": "10500.0",
            "total_rec_prncp": "10000.0",
            "total_rec_int": "500.0",
            "total_rec_late_fee": "0.0",
            "recoveries": "0.0",
            "collection_recovery_fee": "0.0",
            "last_pymnt_d": month_text(period),
            "last_pymnt_amnt": "322.67",
            "last_credit_pull_d": month_text(period),
            "last_fico_range_high": "714.0",
            "last_fico_range_low": "710.0",
            "policy_code": "1.0",
            "hardship_flag": "N",
            "debt_settlement_flag": "N",
        }
    )
    row.update(values)
    return row
