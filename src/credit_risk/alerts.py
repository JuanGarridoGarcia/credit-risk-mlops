"""Alerts: every event a person should know about, recorded in ``ops.alerts`` (D-108).

Four kinds: a flow that failed, a model promoted to champion, a challenger rejected, and
a rollback. They are only recorded here; Grafana reads the table in F6 and sends them on,
together with the drift alerts, through the channel chosen then. A verdict on a registered
version is recorded once, however many times its month runs (unique index, D-101).
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Final

import psycopg

from credit_risk.settings import Settings

log = logging.getLogger(__name__)

KINDS: Final = {
    "flow_failed": "error",
    "promoted": "warning",
    "rejected": "info",
    "rolled_back": "warning",
}


@dataclass(frozen=True)
class Alert:
    """One event; ``severity`` follows from the kind."""

    kind: str
    message: str
    period: date | None = None
    flow: str | None = None
    task: str | None = None
    model: str | None = None
    version: str | None = None
    previous: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"unknown alert kind {self.kind!r}; known: {sorted(KINDS)}")

    @property
    def severity(self) -> str:
        return KINDS[self.kind]


def record(alert: Alert, conn: psycopg.Connection[Any] | None = None) -> bool:
    """Write ``alert``; return False when the same verdict was already recorded."""
    values = {**asdict(alert), "severity": alert.severity, "details": json.dumps(alert.details)}
    query = """
        INSERT INTO ops.alerts
            (kind, severity, period, flow, task, model, version, previous, message, details)
        VALUES (%(kind)s, %(severity)s, %(period)s, %(flow)s, %(task)s, %(model)s,
                %(version)s, %(previous)s, %(message)s, %(details)s)
        ON CONFLICT DO NOTHING
    """
    own = conn is None
    connection = conn or psycopg.connect(Settings().postgres_conninfo(), autocommit=True)
    try:
        written = connection.execute(query, values).rowcount == 1
    finally:
        if own:
            connection.close()
    level = logging.ERROR if alert.severity == "error" else logging.WARNING
    if written:
        log.log(level, "alert %s: %s", alert.kind, alert.message)
    return written


def verdict_alerts(
    name: str,
    challenger: str,
    passed: bool,
    reasons: tuple[str, ...],
    before: str | None,
    after: str | None,
    period: date | None,
) -> list[Alert]:
    """The alerts of one promotion: the challenger rejected and/or a new champion.

    ``before`` and ``after`` are the champion before and after the training. With no
    champion yet, a rejected challenger still leaves a champion: the baseline (D-090).
    """
    found = []
    if not passed:
        found.append(
            Alert(
                "rejected",
                f"{name} version {challenger} rejected: {', '.join(reasons) or 'no reason'}",
                period=period,
                model=name,
                version=challenger,
                previous=before,
                details={"reasons": list(reasons)},
            )
        )
    if after is not None and after != before:
        found.append(
            Alert(
                "promoted",
                f"{name} champion {before or 'none'} -> {after}",
                period=period,
                model=name,
                version=after,
                previous=before,
            )
        )
    return found


def rolled_back(name: str, current: str, previous: str) -> Alert:
    """The alert of a rollback (D-090): ``current`` was replaced by ``previous``."""
    return Alert(
        "rolled_back",
        f"{name} champion rolled back: {current} -> {previous}",
        model=name,
        version=previous,
        previous=current,
    )
