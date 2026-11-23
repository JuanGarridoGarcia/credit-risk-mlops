"""The dated contract: allowed values, product limits and required columns (D-056).

The base is what was known up to 2013-12, the last month loaded as history before the
replay (D-041). Every later change has a month of entry into force, a reason and a pull
request. A delivery is validated with the contract in force in its month, so a value
that arrives before its change fails as critical. Catalogue: docs/validation_rules.md.

Every number here was measured on the cleaned deliveries up to 2013-12 only (2026-11-23).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from types import MappingProxyType
from typing import Final

from credit_risk.contracts import LISTING_COLUMNS

#: First month of the source; nothing can be required before it.
FIRST_PERIOD: Final = date(2007, 6, 1)
#: The source is a snapshot taken in this month: bad loans whose charge-off month would
#: come later are delivered here (data_audit.md 4.2, R1.5).
SNAPSHOT: Final = date(2019, 3, 1)
#: A bad loan resolves this many months after its last payment, or after issue if it
#: never paid (data_audit.md 4.2, E-013).
CHARGE_OFF_LAG_MONTHS: Final = 5

GOOD_STATUSES: Final = frozenset(
    {"Fully Paid", "Does not meet the credit policy. Status:Fully Paid"}
)
BAD_STATUSES: Final = frozenset(
    {"Charged Off", "Default", "Does not meet the credit policy. Status:Charged Off"}
)

#: The columns that describe a second applicant; empty in individual applications.
JOINT_COLUMNS: Final[tuple[str, ...]] = tuple(
    c for c in LISTING_COLUMNS if "joint" in c or c.startswith("sec_app")
)

SETTLEMENT_COLUMNS: Final = (
    "debt_settlement_flag_date",
    "settlement_status",
    "settlement_date",
    "settlement_amount",
    "settlement_percentage",
    "settlement_term",
)
HARDSHIP_COLUMNS: Final = (
    "hardship_type",
    "hardship_reason",
    "hardship_status",
    "deferral_term",
    "hardship_amount",
    "hardship_start_date",
    "hardship_end_date",
    "payment_plan_start_date",
    "hardship_length",
    "hardship_dpd",
    "hardship_loan_status",
    "hardship_payoff_balance_amount",
    "hardship_last_payment_amount",
)

_STATES_2013: Final = [
    "AK",
    "AL",
    "AR",
    "AZ",
    "CA",
    "CO",
    "CT",
    "DC",
    "DE",
    "FL",
    "GA",
    "HI",
    "IA",
    "ID",
    "IL",
    "IN",
    "KS",
    "KY",
    "LA",
    "MA",
    "MD",
    "ME",
    "MI",
    "MN",
    "MO",
    "MS",
    "MT",
    "NC",
    "NE",
    "NH",
    "NJ",
    "NM",
    "NV",
    "NY",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VA",
    "VT",
    "WA",
    "WI",
    "WV",
    "WY",
]

_VERIFICATION: Final = ("Not Verified", "Source Verified", "Verified")


@dataclass(frozen=True)
class Contract:
    """The contract in force in one month."""

    #: Allowed values of each category column; an empty set means "always empty".
    categories: Mapping[str, frozenset[str]]
    loan_amnt_min: float
    loan_amnt_max: float
    #: Listing columns that must be filled, by the first month they are required in.
    required_listings: Mapping[str, date]
    #: Outcome columns that must be filled, by the first month they are required in.
    required_outcomes: Mapping[str, date]
    #: False once the source stops delivering listings (C8).
    listings_expected: bool = True
    #: The change ids applied, in order.
    changes: tuple[str, ...] = field(default=())


def _frozen(**sets: Sequence[str]) -> dict[str, frozenset[str]]:
    return {name: frozenset(values) for name, values in sets.items()}


def _month(text: str) -> date:
    return date.fromisoformat(f"{text}-01")


def _after(text: str) -> date:
    """The month after ``YYYY-MM``: a column is required from the month after its last gap."""
    year, month = map(int, text.split("-"))
    return date(year + month // 12, month % 12 + 1, 1)


# R4.1: never empty up to 2013-12 (dti is required only for individuals, R4.3).
_ALWAYS_LISTINGS: Final = [
    "id",
    "loan_amnt",
    "term",
    "int_rate",
    "installment",
    "grade",
    "sub_grade",
    "home_ownership",
    "verification_status",
    "issue_d",
    "url",
    "purpose",
    "zip_code",
    "addr_state",
    "fico_range_low",
    "fico_range_high",
    "revol_bal",
    "initial_list_status",
    "application_type",
    "disbursement_method",
]
# R4.2: complete through 2013, required from the month after their last empty value.
_LAST_GAP_LISTINGS: Final = {
    **dict.fromkeys(
        [
            "annual_inc",
            "delinq_2yrs",
            "earliest_cr_line",
            "inq_last_6mths",
            "open_acc",
            "pub_rec",
            "total_acc",
            "acc_now_delinq",
            "delinq_amnt",
        ],
        "2007-08",
    ),
    **dict.fromkeys(
        ["collections_12_mths_ex_med", "chargeoff_within_12_mths", "tax_liens"], "2007-10"
    ),
    "pub_rec_bankruptcies": "2009-09",
    **dict.fromkeys(
        ["acc_open_past_24mths", "mort_acc", "total_bal_ex_mort", "total_bc_limit"], "2012-04"
    ),
    **dict.fromkeys(["num_bc_sats", "num_sats"], "2012-07"),
    **dict.fromkeys(
        [
            "tot_coll_amt",
            "tot_cur_bal",
            "total_rev_hi_lim",
            "mo_sin_old_rev_tl_op",
            "mo_sin_rcnt_rev_tl_op",
            "mo_sin_rcnt_tl",
            "num_accts_ever_120_pd",
            "num_actv_bc_tl",
            "num_actv_rev_tl",
            "num_bc_tl",
            "num_il_tl",
            "num_op_rev_tl",
            "num_rev_accts",
            "num_rev_tl_bal_gt_0",
            "num_tl_30dpd",
            "num_tl_90g_dpd_24m",
            "num_tl_op_past_12m",
            "tot_hi_cred_lim",
            "total_il_high_credit_limit",
        ],
        "2012-12",
    ),
}
# R4.4: never empty up to 2013-12, plus last_credit_pull_d (last gap 2012-11).
_ALWAYS_OUTCOMES: Final = [
    "id",
    "funded_amnt",
    "funded_amnt_inv",
    "loan_status",
    "pymnt_plan",
    "out_prncp",
    "out_prncp_inv",
    "total_pymnt",
    "total_pymnt_inv",
    "total_rec_prncp",
    "total_rec_int",
    "total_rec_late_fee",
    "recoveries",
    "collection_recovery_fee",
    "last_pymnt_amnt",
    "last_fico_range_high",
    "last_fico_range_low",
    "policy_code",
    "hardship_flag",
    "debt_settlement_flag",
]

BASE: Final = Contract(
    categories=MappingProxyType(
        _frozen(
            grade=tuple("ABCDEFG"),
            sub_grade=tuple(f"{g}{n}" for g in "ABCDEFG" for n in range(1, 6)),
            home_ownership=("MORTGAGE", "NONE", "OTHER", "OWN", "RENT"),
            verification_status=_VERIFICATION,
            verification_status_joint=(),
            purpose=[
                "car",
                "credit_card",
                "debt_consolidation",
                "educational",
                "home_improvement",
                "house",
                "major_purchase",
                "medical",
                "moving",
                "other",
                "renewable_energy",
                "small_business",
                "vacation",
                "wedding",
            ],
            addr_state=tuple(_STATES_2013),
            initial_list_status=("f", "w"),
            application_type=("Individual",),
            disbursement_method=("Cash",),
            loan_status=(
                "Fully Paid",
                "Charged Off",
                "Does not meet the credit policy. Status:Fully Paid",
                "Does not meet the credit policy. Status:Charged Off",
            ),
            settlement_status=("ACTIVE", "BROKEN", "COMPLETE"),
            hardship_type=(),
            hardship_reason=(),
            hardship_status=(),
            hardship_loan_status=(),
        )
    ),
    loan_amnt_min=500.0,
    loan_amnt_max=35_000.0,
    required_listings=MappingProxyType(
        {
            **dict.fromkeys(_ALWAYS_LISTINGS, FIRST_PERIOD),
            **{c: _after(m) for c, m in _LAST_GAP_LISTINGS.items()},
        }
    ),
    required_outcomes=MappingProxyType(
        {**dict.fromkeys(_ALWAYS_OUTCOMES, FIRST_PERIOD), "last_credit_pull_d": _after("2012-11")}
    ),
)


@dataclass(frozen=True)
class Change:
    """A dated contract change."""

    id: str
    in_force: date
    reason: str
    add_values: Mapping[str, Sequence[str]] = field(default_factory=dict)
    loan_amnt_max: float | None = None
    optional_outcomes: tuple[str, ...] = ()
    listings_end: bool = False

    def apply(self, contract: Contract) -> Contract:
        categories = dict(contract.categories)
        for column, values in self.add_values.items():
            categories[column] = categories[column] | frozenset(values)
        required = {
            c: m for c, m in contract.required_outcomes.items() if c not in self.optional_outcomes
        }
        return replace(
            contract,
            categories=MappingProxyType(categories),
            loan_amnt_max=self.loan_amnt_max or contract.loan_amnt_max,
            required_outcomes=MappingProxyType(required),
            listings_expected=contract.listings_expected and not self.listings_end,
            changes=(*contract.changes, self.id),
        )


CHANGES: Final[tuple[Change, ...]] = (
    Change(
        "C1", _month("2014-09"), "New category home_ownership ANY", {"home_ownership": ("ANY",)}
    ),
    Change("C2", _month("2015-07"), "First loans in North Dakota", {"addr_state": ("ND",)}),
    Change(
        "C3",
        _month("2015-10"),
        "Joint applications launched",
        {"application_type": ("Joint App",), "verification_status_joint": _VERIFICATION},
    ),
    Change(
        "C4", _month("2016-01"), "New disbursement method", {"disbursement_method": ("DirectPay",)}
    ),
    Change("C5", _month("2016-03"), "Maximum loan raised to 40,000", loan_amnt_max=40_000.0),
    Change(
        "C6",
        _month("2017-06"),
        "Hardship program launched",
        {
            "hardship_type": ("INTEREST ONLY-3 MONTHS DEFERRAL",),
            "hardship_reason": [
                "DISABILITY",
                "DIVORCE",
                "EXCESSIVE_OBLIGATIONS",
                "FAMILY_DEATH",
                "INCOME_CURTAILMENT",
                "MEDICAL",
                "NATURAL_DISASTER",
                "REDUCED_HOURS",
                "UNEMPLOYMENT",
            ],
            "hardship_status": ("BROKEN", "COMPLETED"),
            "hardship_loan_status": (
                "Current",
                "In Grace Period",
                "Issued",
                "Late (16-30 days)",
                "Late (31-120 days)",
            ),
        },
    ),
    Change(
        "C9",
        _month("2014-08"),
        "last_credit_pull_d may be empty: sporadic gaps, one or two a month",
        optional_outcomes=("last_credit_pull_d",),
    ),
    Change(
        "C8",
        _month("2019-01"),
        "The source file ends in 2018-12 for listings; outcomes go on to 2019-03",
        listings_end=True,
    ),
    Change(
        "C7",
        _month("2019-03"),
        "Loans in default and not yet charged off at the snapshot",
        {"loan_status": ("Default",)},
    ),
)


def contract_at(period: date, changes: tuple[Change, ...] = CHANGES) -> Contract:
    """The contract in force in ``period``: the base plus every change in force by then."""
    contract = BASE
    for change in sorted(changes, key=lambda c: (c.in_force, c.id)):
        if change.in_force <= period:
            contract = change.apply(contract)
    return contract


@dataclass(frozen=True)
class ReviewedException:
    """A reviewed exception: one loan passes one critical rule; the data is not changed."""

    rule: str
    loan_id: int
    period: date
    reason: str


EXCEPTIONS: Final[tuple[ReviewedException, ...]] = (
    ReviewedException("R3.5", 124624, _month("2007-09"), "open_acc 4 greater than total_acc 3"),
    ReviewedException("R3.5", 127213, _month("2007-09"), "open_acc 14 greater than total_acc 8"),
    ReviewedException("R4.2", 63407533, _month("2015-10"), "num_rev_accts empty in one row"),
    ReviewedException("R4.2", 69266577, _month("2016-01"), "inq_last_6mths empty in one row"),
    ReviewedException("R4.1", 96387212, _month("2017-01"), "zip_code empty in one row"),
)
