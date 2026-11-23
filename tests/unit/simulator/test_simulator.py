"""Tests T1 of the simulator, approved by Juan on 2026-11-23 (docs/technical.md, step 2.1)."""

import ast
import gzip
from collections.abc import Callable
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from credit_risk.contracts import LISTING_COLUMNS, OUTCOME_COLUMNS, OUTCOME_ONLY_COLUMNS
from credit_risk.simulator import core
from credit_risk.simulator.io import read_source, sha256, write_delivery
from credit_risk.simulator.publish import prepare, publish

from .rows import Row, loan

ROOT = Path(__file__).resolve().parents[3]
FrameMaker = Callable[[list[Row]], pl.DataFrame]
SourceMaker = Callable[[list[Row]], Path]


def _read_delivery(path: Path) -> pl.DataFrame:
    return pl.read_csv(path, infer_schema=False)


def _published(
    rows: list[Row], make_source: SourceMaker, landing: Path, until: date = date(2019, 3, 1)
) -> list[Path]:
    src = make_source(rows)
    prepared = prepare(read_source(src, expected_sha256=sha256(src)))
    return publish(prepared, landing, until)


def _all(landing: Path, stream: str) -> pl.DataFrame:
    files = sorted(landing.glob(f"*/{stream}.csv.gz"))
    frames = [_read_delivery(f).with_columns(delivery=pl.lit(f.parent.name)) for f in files]
    return pl.concat([f for f in frames if f.height], how="vertical")


# T1.1
def test_source_with_wrong_hash_is_rejected(
    basic_rows: list[Row], make_source: SourceMaker
) -> None:
    src = make_source(basic_rows)
    with pytest.raises(core.SourceError, match="does not match the expected"):
        read_source(src, expected_sha256="0" * 64)


# T1.2
def test_each_loan_is_listed_once_in_its_issue_month(
    basic_rows: list[Row], make_source: SourceMaker, tmp_path: Path
) -> None:
    landing = tmp_path / "landing"
    _published(basic_rows, make_source, landing)
    listed = _all(landing, "listings")
    assert sorted(listed["id"].to_list()) == [str(i) for i in range(101, 110)]
    month_of = dict(zip(listed["id"], listed["delivery"], strict=True))
    assert month_of["101"] == "2015-01"
    assert month_of["103"] == "2015-02"
    assert month_of["108"] == "2015-03"


# T1.3
def test_listings_hold_exactly_the_listing_columns() -> None:
    dictionary = pl.read_csv(ROOT / "reports/data_audit/data_dictionary.csv")
    expected = {
        c
        for c, a in zip(dictionary["column"], dictionary["available_at_listing"], strict=True)
        if a == "yes"
    } | {"issue_d", "mths_since_recent_bc_dlq"}
    assert set(LISTING_COLUMNS) == expected
    assert not set(LISTING_COLUMNS) & set(OUTCOME_ONLY_COLUMNS)
    assert "loan_status" not in LISTING_COLUMNS


def test_listing_delivery_has_the_contract_columns(
    basic_rows: list[Row], make_source: SourceMaker, tmp_path: Path
) -> None:
    landing = tmp_path / "landing"
    _published(basic_rows, make_source, landing)
    for path in landing.glob("*/listings.csv.gz"):
        assert tuple(_read_delivery(path).columns) == LISTING_COLUMNS


# T1.4
def test_outcome_delivery_has_id_and_only_outcome_columns(
    basic_rows: list[Row], make_source: SourceMaker, tmp_path: Path
) -> None:
    landing = tmp_path / "landing"
    _published(basic_rows, make_source, landing)
    assert OUTCOME_COLUMNS[0] == "id"
    for path in landing.glob("*/outcomes.csv.gz"):
        assert tuple(_read_delivery(path).columns) == OUTCOME_COLUMNS


# T1.5
@pytest.mark.parametrize(
    ("status", "issue", "last_payment", "expected"),
    [
        pytest.param("Fully Paid", "Jan-2015", "Jun-2016", date(2016, 6, 1), id="paid"),
        pytest.param("Charged Off", "Jan-2015", "Feb-2016", date(2016, 7, 1), id="bad"),
        pytest.param("Charged Off", "Feb-2015", None, date(2015, 7, 1), id="bad-never-paid"),
        pytest.param("Charged Off", "Jan-2017", "Jan-2019", date(2019, 3, 1), id="capped"),
        pytest.param("Default", "Mar-2015", "Dec-2017", date(2018, 5, 1), id="default-is-bad"),
        pytest.param(
            "Does not meet the credit policy. Status:Charged Off",
            "Jan-2009",
            "Mar-2010",
            date(2010, 8, 1),
            id="old-policy-bad",
        ),
    ],
)
def test_resolution_month(
    make_frame: FrameMaker, status: str, issue: str, last_payment: str | None, expected: date
) -> None:
    rows = [loan("1", issue, status, last_payment), loan("2", "Jan-2015", "Current", "Mar-2019")]
    out = core.add_periods(make_frame(rows), snapshot=date(2019, 3, 1))
    assert out.filter(pl.col("id") == "1")["resolution_period"].item() == expected


# T1.6
def test_running_loans_produce_no_outcome(
    basic_rows: list[Row], make_source: SourceMaker, tmp_path: Path
) -> None:
    landing = tmp_path / "landing"
    _published(basic_rows, make_source, landing)
    resolved = set(_all(landing, "outcomes")["id"].to_list())
    assert resolved == {"101", "102", "103", "105", "109"}
    assert not resolved & {"104", "106", "107", "108"}


def test_unknown_status_stops_the_simulator(make_frame: FrameMaker) -> None:
    rows = [loan("1", "Jan-2015", "Paid Off Early", "Jun-2016")]
    with pytest.raises(core.SourceError, match="unknown loan_status"):
        core.add_periods(make_frame(rows), snapshot=date(2019, 3, 1))


# T1.7
def test_text_arrives_unchanged(make_source: SourceMaker, tmp_path: Path) -> None:
    tricky = 'Line one, with a comma\nline two "quoted" <br/>'
    rows = [
        loan(
            "1",
            "Jan-2015",
            "Fully Paid",
            "Jun-2016",
            emp_length="10+ years",
            desc=tricky,
            emp_title="  Nurse ",
            dti=None,
        )
    ]
    landing = tmp_path / "landing"
    _published(rows, make_source, landing)
    got = _read_delivery(landing / "2015-01" / "listings.csv.gz").row(0, named=True)
    assert got["term"] == " 36 months"
    assert got["emp_length"] == "10+ years"
    assert got["desc"] == tricky
    assert got["emp_title"] == "  Nurse "
    assert got["dti"] is None
    assert got["loan_amnt"] == "10000.0"


# T1.8
def test_publishing_twice_gives_identical_bytes(
    basic_rows: list[Row], make_source: SourceMaker, tmp_path: Path
) -> None:
    first = _published(basic_rows, make_source, tmp_path / "a")
    second = _published(basic_rows, make_source, tmp_path / "b")
    assert [p.relative_to(tmp_path / "a") for p in first] == [
        p.relative_to(tmp_path / "b") for p in second
    ]
    for a, b in zip(first, second, strict=True):
        assert a.read_bytes() == b.read_bytes()


def test_gzip_header_has_no_timestamp(tmp_path: Path) -> None:
    path = tmp_path / "x.csv.gz"
    write_delivery(pl.DataFrame({"id": ["1"]}), path)
    header = path.read_bytes()[:10]
    assert header[4:8] == b"\x00\x00\x00\x00"  # MTIME field of the gzip header
    assert gzip.decompress(path.read_bytes()) == b"id\n1\n"


# T1.9
def test_summary_rows_are_dropped_wherever_they_are(
    basic_rows: list[Row], make_frame: FrameMaker, make_source: SourceMaker, tmp_path: Path
) -> None:
    loans, dropped = core.drop_summary_rows(make_frame(basic_rows))
    assert dropped == 5  # c) counted
    assert loans["id"].str.contains(r"^\d+$").all()
    landing = tmp_path / "landing"
    _published(basic_rows, make_source, landing)
    delivered = _all(landing, "listings")["id"].to_list()
    assert not [i for i in delivered if not i.isdigit()]  # a) none delivered
    assert sorted(delivered) == [str(i) for i in range(101, 110)]  # b) no loan lost


def test_a_row_that_is_not_a_loan_nor_a_summary_stops_the_simulator(
    make_frame: FrameMaker,
) -> None:
    rows = [loan("1", "Jan-2015", "Fully Paid", "Jun-2016"), loan("2", None, "Current", None)]  # type: ignore[arg-type]
    with pytest.raises(core.SourceError, match="neither loans nor summary rows"):
        core.drop_summary_rows(make_frame(rows))


# T1.10
def test_no_outcome_arrives_before_its_listing(
    basic_rows: list[Row], make_frame: FrameMaker
) -> None:
    loans, _ = core.drop_summary_rows(make_frame(basic_rows))
    out = core.add_periods(loans, snapshot=date(2019, 3, 1))
    resolved = out.filter(pl.col("resolution_period").is_not_null())
    assert (resolved["resolution_period"] >= resolved["listing_period"]).all()


def test_nothing_after_the_simulated_date_is_published(
    basic_rows: list[Row], make_source: SourceMaker, tmp_path: Path
) -> None:
    landing = tmp_path / "landing"
    _published(basic_rows, make_source, landing, until=date(2015, 2, 1))
    assert sorted(p.name for p in landing.iterdir()) == ["2015-01", "2015-02"]


# T1.11
def test_system_code_never_touches_the_simulator() -> None:
    package = ROOT / "src" / "credit_risk"
    offenders = []
    for path in package.rglob("*.py"):
        if "simulator" in path.relative_to(package).parts:
            continue
        text = path.read_text()
        if "accepted_2007_to_2018Q4" in text:
            offenders.append(f"{path}: mentions the source file")
        for node in ast.walk(ast.parse(text)):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            offenders += [f"{path}: imports {n}" for n in names if "simulator" in n]
    assert not offenders
