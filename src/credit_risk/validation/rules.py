"""The validation rules that need only the month that arrived, written with pandera (D-053).

Every check is named by its rule id, the same id as in docs/validation_rules.md, the run
report and the warnings table. Checks return True for a passing row. Missing values pass
every check except the required-column ones (R4.x): missing values are information and
are watched by their own rules (D-051).
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Final

import pandera.polars as pa
import polars as pl
from pandera.errors import SchemaErrors

from credit_risk.cleaning import LISTING_RULES, OUTCOME_RULES, Rule
from credit_risk.contracts import LISTINGS, OUTCOMES
from credit_risk.validation.contract import (
    BAD_STATUSES,
    EXCEPTIONS,
    JOINT_COLUMNS,
    SETTLEMENT_COLUMNS,
    Contract,
)


class Level(Enum):
    """D-054: a critical failure stops the month; a warning is reported and stored."""

    CRITICAL = "critical"
    WARNING = "warning"


class Engine(Enum):
    """Where a rule runs."""

    CLEANING = "C"  # cleaning or the delivery reader (step 2.1)
    PANDERA = "P"  # pandera on the month
    SQL = "S"  # SQL against the history, in the load transaction
    BOTH = "P+S"  # computed on the month, compared with history from the database


@dataclass(frozen=True)
class RuleSpec:
    """One rule of the catalogue."""

    id: str
    level: Level
    engine: Engine
    text: str


_C, _W = Level.CRITICAL, Level.WARNING
_P, _S = Engine.PANDERA, Engine.SQL

CATALOGUE: Final[dict[str, RuleSpec]] = {
    r.id: r
    for r in (
        RuleSpec(
            "R1.1", _C, Engine.CLEANING, "Columns are exactly those of the contract, in order"
        ),
        RuleSpec("R1.2", _C, _P, "id is never empty and unique in the delivery"),
        RuleSpec("R1.3", _C, _S, "The id is not already in clean in another month"),
        RuleSpec("R1.4", _C, _P, "Listings: issue_d is the month of the delivery"),
        RuleSpec("R1.5", _C, _S, "Outcomes: the computed resolution month is the delivery month"),
        RuleSpec("R1.6", _C, _S, "Every outcome has its listing, from the same month or earlier"),
        RuleSpec("R1.7", _C, _P, "url ends with loan_id=<id>"),
        RuleSpec("R2.1", _C, _P, "Categories and zip_code follow the contract in force"),
        RuleSpec("R2.2", _C, _P, "loan_amnt within the product limits in force"),
        RuleSpec("R2.3", _C, _P, "Money amounts are at least -0.01"),
        RuleSpec("R2.4", _C, _P, "Counts and months are whole numbers, at least 0"),
        RuleSpec("R2.5", _C, _P, "int_rate greater than 0 and at most 100"),
        RuleSpec("R2.6", _C, _P, "Shares of accounts between 0 and 100"),
        RuleSpec("R2.7", _C, _P, "Credit utilisation at least 0"),
        RuleSpec("R2.8", _C, _P, "Listing FICO between 300 and 850, high = low + 4 or + 5"),
        RuleSpec("R2.9", _C, _P, "Outcome last FICO whole numbers between 0 and 850"),
        RuleSpec("R2.10", _W, _P, "dti negative or above 100"),
        RuleSpec("R2.11", _W, _P, "annual_inc above 10 million"),
        RuleSpec("R2.12", _W, _P, "Cap-like codes: 999 in account ages, 9,999,999 in limits"),
        RuleSpec("R2.13", _W, _S, "int_rate above the highest rate seen in clean so far"),
        RuleSpec("R3.1", _C, _P, "sub_grade starts with its grade"),
        RuleSpec("R3.2", _C, _P, "Credit history does not start after issue_d"),
        RuleSpec("R3.3", _C, _P, "Joint-application columns empty in individual applications"),
        RuleSpec("R3.4", _C, _P, "Every joint application has annual_inc_joint"),
        RuleSpec("R3.5", _C, _P, "open_acc <= total_acc and num_actv_bc_tl <= num_bc_tl"),
        RuleSpec("R3.6", _C, _P, "total_pymnt = principal + interest + late fees + recoveries"),
        RuleSpec("R3.7", _C, _P, "out_prncp is 0 unless loan_status is Default"),
        RuleSpec("R3.8", _C, _P, "Recoveries only in bad loans"),
        RuleSpec("R3.9", _C, _P, "Settlement and hardship columns all filled or all empty"),
        RuleSpec("R3.10", _C, _P, "funded_amnt_inv <= funded_amnt"),
        RuleSpec("R3.11", _C, _S, "funded_amnt <= loan_amnt of its listing"),
        RuleSpec("R3.12", _C, _S, "last_pymnt_d is not before issue_d of its listing"),
        RuleSpec("R3.13", _W, _P, "annual_inc = 0 in an individual application"),
        RuleSpec("R3.14", _W, _P, "Fully Paid but principal received differs from funded"),
        RuleSpec("R3.15", _W, _S, "installment differs from the amortisation formula"),
        RuleSpec("R4.1", _C, _P, "Columns never empty up to 2013-12 stay filled"),
        RuleSpec("R4.2", _C, _P, "Columns required from the month after their last gap"),
        RuleSpec("R4.3", _C, _P, "dti filled in individual applications"),
        RuleSpec("R4.4", _C, _P, "Required outcome columns; last_pymnt_d in paid loans"),
        RuleSpec("R4.5", _C, _P, "member_id stays empty"),
        RuleSpec(
            "R4.6", _W, Engine.BOTH, "Missing share moves more than 10 points from last month"
        ),
        RuleSpec("R5.1", _C, _S, "Volume below 10% or above 5 times the 12-month median"),
        RuleSpec("R5.2", _W, _S, "Volume below half or above twice the 12-month median"),
        RuleSpec("R5.3", _C, _S, "R5.1 and R5.2 apply only with a median of at least 1,000"),
    )
}

# Kinds of numeric column (group 2). Everything else numeric is a count or a month.
MONEY: Final = frozenset(
    [
        "loan_amnt",
        "installment",
        "annual_inc",
        "revol_bal",
        "annual_inc_joint",
        "tot_coll_amt",
        "tot_cur_bal",
        "total_bal_il",
        "max_bal_bc",
        "total_rev_hi_lim",
        "avg_cur_bal",
        "bc_open_to_buy",
        "delinq_amnt",
        "tot_hi_cred_lim",
        "total_bal_ex_mort",
        "total_bc_limit",
        "total_il_high_credit_limit",
        "revol_bal_joint",
        "funded_amnt",
        "funded_amnt_inv",
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
        "hardship_amount",
        "orig_projected_additional_accrued_interest",
        "hardship_payoff_balance_amount",
        "hardship_last_payment_amount",
        "settlement_amount",
    ]
)
UTILISATION: Final = frozenset(
    ["revol_util", "il_util", "all_util", "bc_util", "sec_app_revol_util"]
)
SHARES: Final = frozenset({"pct_tl_nvr_dlq", "percent_bc_gt_75"})
LISTING_FICO: Final = (
    ("fico_range_low", "fico_range_high"),
    ("sec_app_fico_range_low", "sec_app_fico_range_high"),
)
LAST_FICO: Final = ("last_fico_range_low", "last_fico_range_high")
_NOT_COUNTS: Final = (
    MONEY
    | UTILISATION
    | SHARES
    | {c for pair in LISTING_FICO for c in pair}
    | set(LAST_FICO)
    | {"int_rate", "dti", "dti_joint", "policy_code", "settlement_percentage"}
)
COUNTS: Final = frozenset(
    c
    for rules in (LISTING_RULES, OUTCOME_RULES)
    for c, rule in rules.items()
    if rule is Rule.NUMBER and c not in _NOT_COUNTS
)
AGE_CODES: Final = ("mo_sin_old_il_acct", "mo_sin_old_rev_tl_op")
LIMIT_CODES: Final = ("tot_hi_cred_lim", "total_rev_hi_lim")
INCOME_WARNING: Final = 10_000_000.0
TOLERANCE: Final = 0.01


def _check(rule: str, expr: pl.Expr, *, keep_nulls: bool = False) -> pa.Check:
    """A column check named by its rule; ``expr`` is True for a passing value of ``col``."""
    return pa.Check(lambda data: data.lazyframe.select(expr), name=rule, ignore_na=not keep_nulls)


def _rows(rule: str, expr: pl.Expr) -> pa.Check:
    """A row check named by its rule; ``expr`` is True for a passing row (null passes)."""
    return pa.Check(lambda data: data.lazyframe.select(expr.fill_null(True)), name=rule)


def _all_or_none(columns: Iterable[str]) -> pl.Expr:
    filled = [pl.col(c).is_not_null() for c in columns]
    return pl.all_horizontal(filled) | ~pl.any_horizontal(filled)


def _whole(e: pl.Expr) -> pl.Expr:
    return (e >= 0) & (e == e.floor())


def _common(contract: Contract, rules: dict[str, Rule]) -> dict[str, list[pa.Check]]:
    """Critical column checks shared by both streams."""
    checks: dict[str, list[pa.Check]] = {c: [] for c in rules}
    checks["id"].append(
        _check("R1.2", pl.col("id").is_not_null() & pl.col("id").is_unique(), keep_nulls=True)
    )
    for col, allowed in contract.categories.items():
        if col in checks:
            checks[col].append(_check("R2.1", pl.col(col).is_in(sorted(allowed))))
    for col in checks:
        if col in MONEY:
            checks[col].append(_check("R2.3", pl.col(col) >= -TOLERANCE))
        elif col in COUNTS:
            checks[col].append(_check("R2.4", _whole(pl.col(col))))
    return checks


def _required(rule: str, columns: Iterable[str]) -> dict[str, pa.Check]:
    return {c: _check(rule, pl.col(c).is_not_null(), keep_nulls=True) for c in columns}


def listing_schemas(period: date, contract: Contract) -> dict[Level, pa.DataFrameSchema]:
    """The critical and warning schemas of a ``listings`` month."""
    checks = _common(contract, dict(LISTING_RULES))

    def add(col: str, check: pa.Check) -> None:
        checks[col].append(check)

    add("issue_d", _check("R1.4", pl.col("issue_d") == pl.lit(period)))
    add(
        "url",
        _check(
            "R1.7", pl.col("url").str.ends_with(pl.lit("loan_id=") + pl.col("id").cast(pl.String))
        ),
    )
    add("zip_code", _check("R2.1", pl.col("zip_code").str.contains(r"^\d{3}xx$")))
    add(
        "loan_amnt",
        _check(
            "R2.2", pl.col("loan_amnt").is_between(contract.loan_amnt_min, contract.loan_amnt_max)
        ),
    )
    add("int_rate", _check("R2.5", (pl.col("int_rate") > 0) & (pl.col("int_rate") <= 100)))
    for col in SHARES:
        add(col, _check("R2.6", pl.col(col).is_between(0, 100)))
    for col in UTILISATION:
        add(col, _check("R2.7", pl.col(col) >= 0))
    for low, high in LISTING_FICO:
        add(low, _check("R2.8", pl.col(low).is_between(300, 850)))
        add(high, _check("R2.8", pl.col(high).is_between(300, 850)))
    individual = pl.col("application_type") == "Individual"
    for col, since in contract.required_listings.items():
        rule = "R4.1" if since <= date(2007, 6, 1) else "R4.2"
        if since <= period:
            add(col, _check(rule, pl.col(col).is_not_null(), keep_nulls=True))
    add("member_id", _check("R4.5", pl.col("member_id").is_null(), keep_nulls=True))
    frame_checks = [
        *(
            _rows("R2.8", (pl.col(high) - pl.col(low)).is_in([4.0, 5.0]))
            for low, high in LISTING_FICO
        ),
        _rows("R3.1", pl.col("sub_grade").str.slice(0, 1) == pl.col("grade")),
        _rows(
            "R3.2",
            (pl.col("earliest_cr_line") <= pl.col("issue_d"))
            & (pl.col("sec_app_earliest_cr_line") <= pl.col("issue_d")).fill_null(True),
        ),
        _rows(
            "R3.3", ~individual | ~pl.any_horizontal(pl.col(c).is_not_null() for c in JOINT_COLUMNS)
        ),
        _rows("R3.4", individual | pl.col("annual_inc_joint").is_not_null()),
        _rows(
            "R3.5",
            (pl.col("open_acc") <= pl.col("total_acc")).fill_null(True)
            & (pl.col("num_actv_bc_tl") <= pl.col("num_bc_tl")).fill_null(True),
        ),
        _rows("R4.3", ~individual | pl.col("dti").is_not_null()),
    ]
    warnings: dict[str, list[pa.Check]] = {
        "dti": [_check("R2.10", pl.col("dti").is_between(0, 100))],
        "annual_inc": [_check("R2.11", pl.col("annual_inc") <= INCOME_WARNING)],
        **{c: [_check("R2.12", pl.col(c) != 999)] for c in AGE_CODES},
        **{c: [_check("R2.12", pl.col(c) != 9_999_999)] for c in LIMIT_CODES},
    }
    warning_rows = [_rows("R3.13", ~individual | (pl.col("annual_inc") != 0))]
    return _schemas(checks, frame_checks, warnings, warning_rows)


def outcome_schemas(period: date, contract: Contract) -> dict[Level, pa.DataFrameSchema]:
    """The critical and warning schemas of an ``outcomes`` month."""
    checks = _common(contract, dict(OUTCOME_RULES))
    for col in LAST_FICO:
        checks[col].append(_check("R2.9", _whole(pl.col(col)) & (pl.col(col) <= 850)))
    for col, since in contract.required_outcomes.items():
        if since <= period:
            checks[col].append(_check("R4.4", pl.col(col).is_not_null(), keep_nulls=True))
    status = pl.col("loan_status")
    good = ~status.is_in(sorted(BAD_STATUSES))
    paid = pl.sum_horizontal("total_rec_prncp", "total_rec_int", "total_rec_late_fee", "recoveries")
    frame_checks = [
        _rows("R3.6", (pl.col("total_pymnt") - paid).abs() <= 1),
        _rows("R3.7", (pl.col("out_prncp") == 0) | (status == "Default")),
        _rows("R3.8", (pl.col("recoveries") == 0) | ~good),
        _rows(
            "R3.9",
            (pl.col("debt_settlement_flag") == pl.col("settlement_status").is_not_null())
            & _all_or_none(SETTLEMENT_COLUMNS),
        ),
        _rows("R3.9", _all_or_none(("hardship_type", "hardship_status", "hardship_start_date"))),
        _rows("R3.10", pl.col("funded_amnt_inv") <= pl.col("funded_amnt") + TOLERANCE),
        _rows("R4.4", ~good | pl.col("last_pymnt_d").is_not_null()),
    ]
    warning_rows = [
        _rows(
            "R3.14",
            ~status.str.ends_with("Fully Paid")
            | ((pl.col("total_rec_prncp") - pl.col("funded_amnt")).abs() <= 1),
        )
    ]
    return _schemas(checks, frame_checks, {}, warning_rows)


SCHEMAS: Final = {LISTINGS: listing_schemas, OUTCOMES: outcome_schemas}


def _schemas(
    checks: dict[str, list[pa.Check]],
    frame_checks: list[pa.Check],
    warnings: dict[str, list[pa.Check]],
    warning_rows: list[pa.Check],
) -> dict[Level, pa.DataFrameSchema]:
    def schema(by_column: dict[str, list[pa.Check]], rows: list[pa.Check]) -> pa.DataFrameSchema:
        columns = {c: pa.Column(nullable=True, checks=cs) for c, cs in by_column.items() if cs}
        return pa.DataFrameSchema(columns, checks=rows, strict=False)

    return {
        Level.CRITICAL: schema(checks, frame_checks),
        Level.WARNING: schema(warnings, warning_rows),
    }


@dataclass(frozen=True)
class Finding:
    """Rows of one stream that failed one rule in one column (``None`` for a row rule)."""

    rule: str
    level: str  # "critical", "warning" or "exception" (a reviewed exception, section 4)
    stream: str
    column: str | None
    count: int
    examples: tuple[tuple[int | None, str | None], ...]


MAX_EXAMPLES: Final = 20


def run_schema(schema: pa.DataFrameSchema, frame: pl.DataFrame) -> pl.DataFrame:
    """Validate lazily; return one row per failing value: rule, column, row index, value."""
    try:
        schema.validate(frame, lazy=True)
    except SchemaErrors as exc:
        cases: pl.DataFrame = exc.failure_cases
        return cases.select(
            pl.col("check").alias("rule"),
            pl.col("column"),
            pl.col("index").cast(pl.Int64).alias("row"),
            pl.col("failure_case").alias("value"),
        )
    return pl.DataFrame(
        schema={"rule": pl.String, "column": pl.String, "row": pl.Int64, "value": pl.String}
    )


def validate_month(
    frame: pl.DataFrame, stream: str, period: date, contract: Contract
) -> list[Finding]:
    """Run the pandera rules of a month; reviewed exceptions become their own findings."""
    findings: list[Finding] = []
    ids = frame["id"]
    waived = {(e.rule, e.loan_id) for e in EXCEPTIONS if e.period == period}
    for level, schema in SCHEMAS[stream](period, contract).items():
        cases = run_schema(schema, frame)
        if cases.is_empty():
            continue
        cases = cases.with_columns(
            loan_id=pl.col("row").map_elements(lambda i: ids[i], return_dtype=pl.Int64),
            value=pl.when(pl.col("column").is_null()).then(None).otherwise(pl.col("value")),
        ).with_columns(
            kind=pl.when(
                pl.struct("rule", "loan_id").map_elements(
                    lambda r: (r["rule"], r["loan_id"]) in waived, return_dtype=pl.Boolean
                )
            )
            .then(pl.lit("exception"))
            .otherwise(pl.lit(level.value))
        )
        for (rule, column, kind), group in cases.group_by(
            "rule", "column", "kind", maintain_order=True
        ):
            examples = tuple(group.select("loan_id", "value").head(MAX_EXAMPLES).iter_rows())
            findings.append(Finding(str(rule), str(kind), stream, column, group.height, examples))
    return findings
