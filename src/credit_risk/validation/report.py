"""The run report of a month (D-053) and the rules computed from history (R4.6, R5).

Every validation run writes a JSON report and a readable summary with every finding:
rule, level, stream, column, count and up to 20 examples (loan id, value).
"""

import json
import statistics
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Final

import polars as pl

from credit_risk.cleaning import CleaningError
from credit_risk.validation.rules import CATALOGUE, MAX_EXAMPLES, Finding

NULL_SHIFT: Final = 0.10  # R4.6
VOLUME_CRITICAL: Final = (0.1, 5.0)  # R5.1
VOLUME_WARNING: Final = (0.5, 2.0)  # R5.2
VOLUME_MIN_MEDIAN: Final = 1_000  # R5.3
VOLUME_MONTHS: Final = 12


def cleaning_findings(stream: str, error: CleaningError) -> list[Finding]:
    """Cleaning failures (formats, engine C) as critical findings of the report."""
    return [
        Finding(
            "cleaning",
            "critical",
            stream,
            f.column,
            f.count,
            ((int(f.loan_id) if f.loan_id and f.loan_id.isdigit() else None, f.value),),
        )
        for f in error.failures
    ]


def profile(frame: pl.DataFrame) -> dict[str, tuple[int, int]]:
    """Rows and missing values of every column of a month."""
    nulls = frame.null_count().row(0, named=True)
    return {c: (frame.height, int(n)) for c, n in nulls.items()}


def null_findings(
    stream: str,
    current: Mapping[str, tuple[int, int]],
    previous: Mapping[str, tuple[int, int]],
) -> list[Finding]:
    """R4.6: the share of missing values moves more than 10 points from the previous month."""
    findings = []
    for column, (rows, nulls) in current.items():
        before = previous.get(column)
        if rows == 0 or before is None or before[0] == 0:
            continue
        share, share_before = nulls / rows, before[1] / before[0]
        if abs(share - share_before) > NULL_SHIFT:
            value = f"{share_before:.1%} -> {share:.1%}"
            findings.append(Finding("R4.6", "warning", stream, column, rows, ((None, value),)))
    return findings


def volume_findings(
    stream: str, rows: int, history: Iterable[int], *, expected: bool = True
) -> tuple[list[Finding], list[str]]:
    """R5.1 to R5.3 against the median of the 12 previous months; returns findings and notes."""
    if not expected:
        if rows > 0:
            return [Finding("R5.1", "critical", stream, None, rows, ((None, f"{rows} rows"),))], []
        return [], [
            f"{stream}: the source delivers no rows from here on (contract), R5 not applied"
        ]
    months = list(history)
    if len(months) < VOLUME_MONTHS:
        return [], [f"{stream}: {len(months)} of 12 previous months in clean, R5 not applied"]
    median = statistics.median(months)
    if median < VOLUME_MIN_MEDIAN:
        return [], [f"{stream}: 12-month median {median:g} below 1,000 (R5.3), R5 not applied"]
    ratio = rows / median
    value = ((None, f"{rows} rows, median {median:g}, ratio {ratio:.2f}"),)
    low, high = VOLUME_CRITICAL
    if not low <= ratio <= high:
        return [Finding("R5.1", "critical", stream, None, max(rows, 1), value)], []
    low, high = VOLUME_WARNING
    if not low <= ratio <= high:
        return [Finding("R5.2", "warning", stream, None, max(rows, 1), value)], []
    return [], []


def sql_findings(rows: Iterable[tuple[str, str, str | None, int, str | None]]) -> list[Finding]:
    """Group the failing values returned by validate_month.sql into findings."""
    groups: dict[tuple[str, str, str | None], list[tuple[int | None, str | None]]] = {}
    for rule, stream, column, loan_id, value in rows:
        groups.setdefault((rule, stream, column), []).append((int(loan_id), value))
    return [
        Finding(
            rule,
            CATALOGUE[rule].level.value,
            stream,
            column,
            len(items),
            tuple(items[:MAX_EXAMPLES]),
        )
        for (rule, stream, column), items in groups.items()
    ]


@dataclass
class Report:
    """Everything a validation run found for one month."""

    period: date
    contract_changes: tuple[str, ...]
    rows: dict[str, int]
    findings: list[Finding] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    run_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def of_level(self, level: str) -> list[Finding]:
        return [f for f in self.findings if f.level == level]

    @property
    def passed(self) -> bool:
        return not self.of_level("critical")

    def failed_rules(self) -> list[str]:
        return sorted({f.rule for f in self.of_level("critical")})

    def to_dict(self) -> dict[str, object]:
        return {
            "period": f"{self.period:%Y-%m}",
            "run_at": self.run_at.isoformat(timespec="seconds"),
            "status": "passed" if self.passed else "failed",
            "contract_changes": list(self.contract_changes),
            "rows": self.rows,
            "counts": {
                lvl: len(self.of_level(lvl)) for lvl in ("critical", "warning", "exception")
            },
            "findings": [
                {
                    **asdict(f),
                    "text": CATALOGUE[f.rule].text if f.rule in CATALOGUE else "Cleaning rule",
                }
                for f in self.findings
            ],
            "notes": self.notes,
        }

    def summary(self) -> str:
        lines = [
            f"# Validation {self.period:%Y-%m}: {'passed' if self.passed else 'FAILED'}",
            "",
            f"Run at {self.run_at:%Y-%m-%d %H:%M:%S} UTC. Rows: "
            + ", ".join(f"{s} {n:,}" for s, n in self.rows.items())
            + ". Contract changes in force: "
            + (", ".join(self.contract_changes) or "none")
            + ".",
            "",
        ]
        for level in ("critical", "warning", "exception"):
            found = self.of_level(level)
            lines.append(f"## {level.capitalize()} ({len(found)})")
            lines.append("")
            if found:
                lines += [
                    "| Rule | Stream | Column | Rows | First example |",
                    "|---|---|---|---|---|",
                ]
                for f in found:
                    first = f.examples[0] if f.examples else (None, None)
                    lines.append(
                        f"| {f.rule} | {f.stream} | {f.column or ''} | {f.count:,} "
                        f"| loan {first[0]}, value {first[1]} |"
                    )
                lines.append("")
        if self.notes:
            lines += ["## Notes", "", *[f"- {n}" for n in self.notes], ""]
        return "\n".join(lines)

    def write(self, directory: Path) -> Path:
        """Write ``<directory>/<YYYY-MM>/validation_<timestamp>.json`` and its ``.md``."""
        folder = directory / f"{self.period:%Y-%m}"
        folder.mkdir(parents=True, exist_ok=True)
        stem = folder / f"validation_{self.run_at:%Y%m%dT%H%M%S%fZ}"
        path = stem.with_suffix(".json")
        path.write_text(json.dumps(self.to_dict(), indent=2, default=str) + "\n")
        stem.with_suffix(".md").write_text(self.summary())
        return path


class ValidationFailed(RuntimeError):  # noqa: N818 - the name reads as the event it reports
    """A critical rule failed: the month did not enter clean (D-055)."""

    def __init__(self, report: Report, path: Path) -> None:
        self.report = report
        self.path = path
        rules = ", ".join(report.failed_rules())
        super().__init__(f"validation of {report.period:%Y-%m} failed: rules {rules}; see {path}")
