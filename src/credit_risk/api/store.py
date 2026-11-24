"""What the API writes to Postgres: ``serving.requests`` and ``serving.predictions``.

A prediction is written before it is answered, in the same transaction as its request
(D-121): if the database cannot take it, the client gets a 503 and no prediction. A
batch is one transaction. A loan already scored by the same pair of models is not
stored again (D-114): the stored prediction is read back and answered instead.
"""

import json
import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, Final, Protocol

from psycopg import Connection
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from credit_risk.api.scoring import Scored

log = logging.getLogger(__name__)

#: Columns of ``serving.predictions`` read back for an answer, in this order.
ANSWER: Final = (
    "loan_id", "listed", "covered", "pd", "lgd", "ead", "expected_loss", "el_rate",
    "expected_return", "minimum", "passes", "reasons", "pd_version", "lgd_version",
    "rule_version", "api_version",
)  # fmt: skip


@dataclass
class RequestRow:
    """One row of ``serving.requests`` (D-115)."""

    request_id: uuid.UUID
    endpoint: str
    api_version: str
    status: int = 200
    latency_ms: float = 0.0
    client: str | None = None
    loans: int = 0
    rejected: int = 0
    versions: dict[str, str | None] | None = None
    body: Any = None
    errors: Any = None


@dataclass(frozen=True)
class Answer:
    """A stored prediction as the API answers it; ``stored_earlier`` for a repeat."""

    values: dict[str, Any]
    stored_earlier: bool


def _json(value: Any) -> Jsonb | None:
    return None if value is None else Jsonb(value, dumps=lambda v: json.dumps(v, default=str))


def _insert_request(conn: Connection[Any], row: RequestRow) -> None:
    versions = row.versions or {}
    conn.execute(
        """
        INSERT INTO serving.requests (request_id, endpoint, client, status, latency_ms,
            loans, rejected, pd_version, lgd_version, rule_version, api_version, body, errors)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            row.request_id, row.endpoint, row.client, row.status, row.latency_ms, row.loans,
            row.rejected, versions.get("pd"), versions.get("lgd"), versions.get("buy_rule"),
            row.api_version, _json(row.body), _json(row.errors),
        ),
    )  # fmt: skip


def _values(s: Scored, row: RequestRow) -> tuple[Any, ...]:
    v = row.versions or {}
    return (
        row.request_id, s.loan_id, s.listed, v.get("pd"), v.get("lgd"), v.get("buy_rule"),
        row.api_version, s.covered, s.pd, s.lgd, s.ead, s.expected_loss, s.el_rate,
        s.expected_return, s.minimum, s.passes, s.base_value, _json(s.contributions),
        _json(s.reasons), _json(s.features), _json(s.request),
    )  # fmt: skip


INSERT_PREDICTION: Final = """
    INSERT INTO serving.predictions (request_id, loan_id, listed, pd_version, lgd_version,
        rule_version, api_version, covered, pd, lgd, ead, expected_loss, el_rate,
        expected_return, minimum, passes, base_value, contributions, reasons, features,
        request)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT ON CONSTRAINT predictions_once DO NOTHING
"""


class Saver(Protocol):
    """What the application needs from a store; tests use one in memory."""

    def open(self) -> None: ...

    def close(self) -> None: ...

    def alive(self) -> bool: ...

    def save(self, row: RequestRow, scored: Sequence[Scored]) -> list[Answer]: ...

    def record(self, row: RequestRow) -> bool: ...


class Store:
    """A small pool of connections to the project's Postgres."""

    def __init__(self, conninfo: str, size: int = 10) -> None:
        self.pool: ConnectionPool[Connection[Any]] = ConnectionPool(
            conninfo, min_size=1, max_size=size, open=False, timeout=5.0,
            kwargs={"connect_timeout": 3},
        )  # fmt: skip

    def open(self) -> None:
        self.pool.open(wait=False)

    def close(self) -> None:
        self.pool.close()

    def alive(self) -> bool:
        """Whether a query reaches the database now."""
        try:
            with self.pool.connection(timeout=2.0) as conn:
                conn.execute("SELECT 1")
            return True
        except Exception:  # noqa: BLE001 - any failure means "not now"
            return False

    def save(self, row: RequestRow, scored: Sequence[Scored]) -> list[Answer]:
        """Write the request and its predictions in one transaction; answer each loan.

        Loans already stored for this pair of models are not written again: their stored
        prediction is the answer (D-114).
        """
        with self.pool.connection() as conn, conn.transaction():
            _insert_request(conn, row)
            new: set[int] = set()
            with conn.cursor() as cur:
                for s in scored:
                    cur.execute(INSERT_PREDICTION, _values(s, row))
                    if cur.rowcount == 1:
                        new.add(s.loan_id)
            v = row.versions or {}
            stored = _read(conn, [s.loan_id for s in scored], v.get("pd"), v.get("lgd"))
        return [Answer(stored[s.loan_id], s.loan_id not in new) for s in scored]

    def record(self, row: RequestRow) -> bool:
        """Write a request with no prediction (rejected, refused, failed); best effort."""
        try:
            with self.pool.connection(timeout=2.0) as conn, conn.transaction():
                _insert_request(conn, row)
            return True
        except Exception as error:  # noqa: BLE001 - the answer must not depend on it
            log.warning("request %s not recorded: %r", row.request_id, error)
            return False


def _read(
    conn: Connection[Any], loans: list[int], pd_version: Any, lgd_version: Any
) -> dict[int, dict[str, Any]]:
    rows = conn.execute(
        f"SELECT {', '.join(ANSWER)} FROM serving.predictions "  # noqa: S608 - fixed names
        "WHERE loan_id = ANY(%s) AND pd_version = %s AND lgd_version = %s",
        (loans, pd_version, lgd_version),
    ).fetchall()
    out = {}
    for r in rows:
        values = dict(zip(ANSWER, r, strict=True))
        if isinstance(values["listed"], date):
            values["listed"] = values["listed"].isoformat()
        out[int(values["loan_id"])] = values
    return out
