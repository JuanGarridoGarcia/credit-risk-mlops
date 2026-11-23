"""Tests T4.1 to T4.9 of validation, approved by Juan on 2026-11-23 (docs/validation_rules.md).

Every case starts from rows that pass every rule (``tests/valid_rows.py``) and changes
one thing, so the finding comes from the rule under test and from no other (T4.2).
"""

import re
from datetime import date
from importlib.resources import files
from pathlib import Path

import polars as pl
import pytest

from credit_risk.cleaning import CLEANERS, CleaningError, clean_listings
from credit_risk.contracts import LISTING_COLUMNS, LISTINGS, OUTCOME_COLUMNS, OUTCOMES
from credit_risk.validation import report
from credit_risk.validation.contract import CHANGES, contract_at
from credit_risk.validation.report import null_findings, volume_findings
from credit_risk.validation.rules import CATALOGUE, SCHEMAS, Engine, Finding, Level, validate_month
from tests import valid_rows
from tests.valid_rows import MONTH, Row

ROOT = Path(__file__).resolve().parents[2]


def _frame(stream: str, rows: list[Row]) -> pl.DataFrame:
    columns = LISTING_COLUMNS if stream == LISTINGS else OUTCOME_COLUMNS
    raw = pl.DataFrame(rows, schema=dict.fromkeys(columns, pl.String))
    return CLEANERS[stream](raw)


def _validate(stream: str, rows: list[Row], period: date = MONTH) -> list[Finding]:
    return validate_month(_frame(stream, rows), stream, period, contract_at(period))


def _rules(findings: list[Finding], level: str) -> set[str]:
    return {f.rule for f in findings if f.level == level}


def _listing(id_: int = 1, period: date = MONTH, /, **values: str | None) -> Row:
    return valid_rows.listing(id_, period, **values)


def _outcome(id_: int = 1, period: date = MONTH, /, **values: str | None) -> Row:
    return valid_rows.outcome(id_, period, **values)


_JOINT: dict[str, str | None] = {
    "application_type": "Joint App",
    "annual_inc_joint": "120000.0",
    "dti_joint": "15.0",
    "verification_status_joint": "Verified",
}
OCTOBER = date(2015, 10, 1)


# T4.1
def test_a_valid_month_passes_every_rule() -> None:
    listings = [_listing(1), _listing(2), _listing(3, OCTOBER, **_JOINT)]
    assert _validate(LISTINGS, listings[:2]) == []
    assert _validate(LISTINGS, [_listing(4, OCTOBER), listings[2]], OCTOBER) == []
    assert _validate(OUTCOMES, [_outcome(1), _outcome(2)]) == []


# T4.2: one case per critical pandera rule; (rule, stream, rows, period).
CRITICAL_CASES: list[tuple[str, str, list[Row], date]] = [
    ("R1.2", LISTINGS, [_listing(1), _listing(1)], MONTH),
    ("R1.2", OUTCOMES, [_outcome(1), _outcome(1)], MONTH),
    ("R1.4", LISTINGS, [_listing(issue_d="Feb-2015")], MONTH),
    (
        "R1.7",
        LISTINGS,
        [_listing(url="https://lendingclub.com/browse/loanDetail.action?loan_id=2")],
        MONTH,
    ),
    ("R2.1", LISTINGS, [_listing(grade="H", sub_grade="H1")], MONTH),
    ("R2.1", LISTINGS, [_listing(zip_code="12345")], MONTH),
    ("R2.1", OUTCOMES, [_outcome(loan_status="Current")], MONTH),
    ("R2.2", LISTINGS, [_listing(loan_amnt="35001.0")], MONTH),
    ("R2.3", LISTINGS, [_listing(revol_bal="-5.0")], MONTH),
    ("R2.3", OUTCOMES, [_outcome(collection_recovery_fee="-1.0")], MONTH),
    ("R2.4", LISTINGS, [_listing(delinq_2yrs="1.5")], MONTH),
    ("R2.4", LISTINGS, [_listing(open_acc="-1.0")], MONTH),
    ("R2.5", LISTINGS, [_listing(int_rate="0.0")], MONTH),
    ("R2.6", LISTINGS, [_listing(pct_tl_nvr_dlq="101.0")], MONTH),
    ("R2.7", LISTINGS, [_listing(revol_util="-1.0")], MONTH),
    ("R2.8", LISTINGS, [_listing(fico_range_low="250.0", fico_range_high="254.0")], MONTH),
    ("R2.8", LISTINGS, [_listing(fico_range_high="710.0")], MONTH),
    ("R2.9", OUTCOMES, [_outcome(last_fico_range_high="900.0")], MONTH),
    ("R3.1", LISTINGS, [_listing(sub_grade="C3")], MONTH),
    ("R3.2", LISTINGS, [_listing(earliest_cr_line="Apr-2015")], MONTH),
    ("R3.3", LISTINGS, [_listing(dti_joint="10.0")], MONTH),
    ("R3.4", LISTINGS, [_listing(1, OCTOBER, **{**_JOINT, "annual_inc_joint": None})], OCTOBER),
    ("R3.5", LISTINGS, [_listing(open_acc="20.0")], MONTH),
    ("R3.5", LISTINGS, [_listing(num_actv_bc_tl="5.0")], MONTH),
    ("R3.6", OUTCOMES, [_outcome(total_pymnt="99.0", total_pymnt_inv="99.0")], MONTH),
    ("R3.7", OUTCOMES, [_outcome(out_prncp="5.0")], MONTH),
    ("R3.8", OUTCOMES, [_outcome(recoveries="10.0", total_pymnt="10510.0")], MONTH),
    ("R3.9", OUTCOMES, [_outcome(debt_settlement_flag="Y")], MONTH),
    (
        "R3.9",
        OUTCOMES,
        [_outcome(hardship_type="INTEREST ONLY-3 MONTHS DEFERRAL")],
        date(2017, 6, 1),
    ),
    ("R3.10", OUTCOMES, [_outcome(funded_amnt_inv="10001.0")], MONTH),
    ("R4.1", LISTINGS, [_listing(home_ownership=None)], MONTH),
    ("R4.2", LISTINGS, [_listing(tot_cur_bal=None)], MONTH),
    ("R4.3", LISTINGS, [_listing(dti=None)], MONTH),
    ("R4.4", OUTCOMES, [_outcome(last_pymnt_amnt=None)], MONTH),
    ("R4.4", OUTCOMES, [_outcome(last_pymnt_d=None)], MONTH),
    ("R4.5", LISTINGS, [_listing(member_id="123")], MONTH),
]


@pytest.mark.parametrize(
    ("rule", "stream", "rows", "period"),
    CRITICAL_CASES,
    ids=[f"{c[0]}-{c[1]}-{i}" for i, c in enumerate(CRITICAL_CASES)],
)
def test_each_critical_rule_names_itself_the_loan_and_the_value(
    rule: str, stream: str, rows: list[Row], period: date
) -> None:
    findings = _validate(stream, rows, period)
    assert _rules(findings, "critical") == {rule}
    found = next(f for f in findings if f.rule == rule)
    assert found.examples[0][0] == int(str(rows[-1]["id"]))


def test_every_critical_pandera_rule_has_a_case() -> None:
    expected = {
        r.id for r in CATALOGUE.values() if r.engine is Engine.PANDERA and r.level is Level.CRITICAL
    }
    assert {c[0] for c in CRITICAL_CASES} == expected


# T4.3
WARNING_CASES: list[tuple[str, str, list[Row]]] = [
    ("R2.10", LISTINGS, [_listing(dti="150.0")]),
    ("R2.10", LISTINGS, [_listing(dti="-1.0")]),
    ("R2.11", LISTINGS, [_listing(annual_inc="20000000.0")]),
    ("R2.12", LISTINGS, [_listing(mo_sin_old_il_acct="999.0")]),
    ("R2.12", LISTINGS, [_listing(tot_hi_cred_lim="9999999.0")]),
    ("R3.13", LISTINGS, [_listing(annual_inc="0.0")]),
    ("R3.14", OUTCOMES, [_outcome(total_rec_prncp="9990.0", total_pymnt="10490.0")]),
]


@pytest.mark.parametrize(("rule", "stream", "rows"), WARNING_CASES)
def test_each_warning_rule_reports_and_lets_the_month_pass(
    rule: str, stream: str, rows: list[Row]
) -> None:
    findings = _validate(stream, rows)
    assert _rules(findings, "critical") == set()
    assert _rules(findings, "warning") == {rule}
    assert next(f for f in findings if f.rule == rule).count == 1


def test_every_warning_pandera_rule_has_a_case() -> None:
    expected = {
        r.id for r in CATALOGUE.values() if r.engine is Engine.PANDERA and r.level is Level.WARNING
    }
    assert {c[0] for c in WARNING_CASES} == expected


# T4.4
def test_all_failures_of_a_month_are_reported_at_once() -> None:
    rows = [
        _listing(1, grade="H", sub_grade="H1"),
        _listing(2, int_rate="0.0"),
        _listing(3, dti=None),
    ]
    findings = _validate(LISTINGS, rows)
    assert _rules(findings, "critical") == {"R2.1", "R2.5", "R4.3"}
    assert {f.examples[0][0] for f in findings} == {1, 2, 3}


# T4.5
@pytest.mark.parametrize(
    ("values", "period", "fails"),
    [
        ({"loan_amnt": "35000.0"}, MONTH, False),
        ({"loan_amnt": "35001.0"}, MONTH, True),
        ({"loan_amnt": "40000.0"}, date(2016, 3, 1), False),
        ({"loan_amnt": "40001.0"}, date(2016, 3, 1), True),
        ({"loan_amnt": "500.0"}, MONTH, False),
        ({"loan_amnt": "499.0"}, MONTH, True),
        ({"int_rate": "100.0"}, MONTH, False),
        ({"int_rate": "100.01"}, MONTH, True),
        ({"revol_bal": "-0.01"}, MONTH, False),
        ({"revol_bal": "-0.02"}, MONTH, True),
        ({"fico_range_low": "300.0", "fico_range_high": "304.0"}, MONTH, False),
        ({"fico_range_low": "846.0", "fico_range_high": "851.0"}, MONTH, True),
    ],
)
def test_critical_limits_are_inclusive(values: dict[str, str], period: date, fails: bool) -> None:
    findings = _validate(LISTINGS, [_listing(1, period, **values)], period)
    assert bool(_rules(findings, "critical")) is fails


@pytest.mark.parametrize(("dti", "warns"), [("100.0", False), ("100.01", True), ("0.0", False)])
def test_warning_limits_are_inclusive(dti: str, warns: bool) -> None:
    assert bool(_rules(_validate(LISTINGS, [_listing(dti=dti)]), "warning")) is warns


@pytest.mark.parametrize(
    ("median", "rows", "rule"),
    [
        (1000, 100, "R5.2"),  # ratio 0.1: not critical, but below half
        (1000, 99, "R5.1"),
        (1000, 5000, "R5.2"),  # ratio 5: not critical, but above twice
        (1000, 5001, "R5.1"),
        (1000, 2000, None),
        (1000, 2001, "R5.2"),
        (1000, 500, None),
        (1000, 499, "R5.2"),
        (999, 0, None),  # R5.3: median below 1,000, nothing applies
    ],
)
def test_volume_limits(median: int, rows: int, rule: str | None) -> None:
    findings, notes = volume_findings(LISTINGS, rows, [median] * 12)
    assert [f.rule for f in findings] == ([rule] if rule else [])
    if median < 1000:
        assert "R5.3" in notes[0]


def test_volume_needs_twelve_months_of_history() -> None:
    findings, notes = volume_findings(LISTINGS, 0, [5000] * 11)
    assert findings == []
    assert "11 of 12" in notes[0]


def test_missing_share_limit_is_ten_points() -> None:
    previous = {"desc": (100, 50)}
    assert null_findings(LISTINGS, {"desc": (100, 60)}, previous) == []
    assert [f.rule for f in null_findings(LISTINGS, {"desc": (100, 61)}, previous)] == ["R4.6"]
    assert [f.rule for f in null_findings(LISTINGS, {"desc": (100, 39)}, previous)] == ["R4.6"]


# T4.6: (change, stream, column changes, month it enters into force)
def _before(period: date) -> date:
    return date(period.year - (period.month == 1), (period.month - 2) % 12 + 1, 1)


_DATED: list[tuple[str, str, dict[str, str | None]]] = [
    ("C1", LISTINGS, {"home_ownership": "ANY"}),
    ("C2", LISTINGS, {"addr_state": "ND"}),
    ("C3", LISTINGS, _JOINT),
    ("C4", LISTINGS, {"disbursement_method": "DirectPay"}),
    ("C5", LISTINGS, {"loan_amnt": "40000.0"}),
    (
        "C6",
        OUTCOMES,
        {
            "hardship_type": "INTEREST ONLY-3 MONTHS DEFERRAL",
            "hardship_reason": "MEDICAL",
            "hardship_status": "COMPLETED",
            "hardship_loan_status": "Current",
            "hardship_start_date": "Jan-2017",
        },
    ),
    ("C7", OUTCOMES, {"loan_status": "Default", "out_prncp": "1000.0"}),
    ("C9", OUTCOMES, {"last_credit_pull_d": None}),
]


@pytest.mark.parametrize(("change", "stream", "values"), _DATED, ids=[c[0] for c in _DATED])
def test_a_value_fails_the_month_before_its_change_and_passes_from_it(
    change: str, stream: str, values: dict[str, str | None]
) -> None:
    in_force = next(c.in_force for c in CHANGES if c.id == change)
    make = _listing if stream == LISTINGS else _outcome
    for period, fails in ((_before(in_force), True), (in_force, False)):
        findings = _validate(stream, [make(1, period, **values)], period)
        assert bool(_rules(findings, "critical")) is fails, (change, period)


def test_listings_must_be_empty_once_the_source_ends() -> None:
    in_force = next(c.in_force for c in CHANGES if c.id == "C8")
    assert contract_at(_before(in_force)).listings_expected
    assert not contract_at(in_force).listings_expected
    findings, _ = volume_findings(LISTINGS, 1, [40_000] * 12, expected=False)
    assert [(f.rule, f.level) for f in findings] == [("R5.1", "critical")]
    assert volume_findings(LISTINGS, 0, [40_000] * 12, expected=False)[0] == []


# T4.7
def test_a_reviewed_exception_passes_only_its_rule_loan_and_month() -> None:
    september = date(2007, 9, 1)
    broken = {"open_acc": "4.0", "total_acc": "3.0"}
    findings = _validate(LISTINGS, [_listing(124624, september, **broken)], september)
    assert [(f.rule, f.level) for f in findings] == [("R3.5", "exception")]
    other = _validate(LISTINGS, [_listing(999, september, **broken)], september)
    assert _rules(other, "critical") == {"R3.5"}
    elsewhere = _validate(LISTINGS, [_listing(124624, MONTH, **broken)])
    assert _rules(elsewhere, "critical") == {"R3.5"}


# T4.8
def test_cleaning_reports_every_failing_column_at_once() -> None:
    raw = pl.DataFrame(
        [_listing(1, term="72 months", emp_length="11 years")],
        schema=dict.fromkeys(LISTING_COLUMNS, pl.String),
    )
    with pytest.raises(CleaningError) as info:
        clean_listings(raw)
    assert [f.column for f in info.value.failures] == ["term", "emp_length"]


# T4.9
def test_every_rule_in_the_code_is_in_the_catalogue_and_the_other_way_round() -> None:
    doc = (ROOT / "docs" / "validation_rules.md").read_text()
    documented = set(re.findall(r"^\| (R\d\.\d+) \|", doc, flags=re.MULTILINE))
    assert documented == set(CATALOGUE)
    used: set[str] = set()
    for build in SCHEMAS.values():
        for period in (date(2007, 6, 1), date(2019, 3, 1)):
            for schema in build(period, contract_at(period)).values():
                used |= {c.name for c in schema.checks}
                used |= {c.name for col in schema.columns.values() for c in col.checks}
    # The installed package, so the test also works in the image, where src/ is removed.
    sql = files("credit_risk.sql").joinpath("validate_month.sql").read_text()
    used |= set(re.findall(r"'(R\d\.\d+)'", sql))
    used |= set(re.findall(r"R\d\.\d+", Path(report.__file__).read_text()))
    assert used | {"R1.1"} == set(CATALOGUE)  # R1.1 is the delivery reader (step 2.1)
