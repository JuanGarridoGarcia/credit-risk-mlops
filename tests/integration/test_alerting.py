"""T30.1 to T30.3: the alerts of the monitoring inside the month, in ``ops.alerts``
(D-147, D-149, D-156). Approved by Juan on 2026-11-26.

Postgres only, like ``test_monitoring.py``: the reference of the pair is a made-up set of
predictions (the scoring of the API is replaced), and the month's predictions are
written straight into ``serving.predictions``.
"""

import json
import uuid
from datetime import date
from typing import Any

import numpy as np
import psycopg
import pytest
from psycopg import Connection as PgConnection
from psycopg import errors

from credit_risk import alerts
from credit_risk.monitoring import alerting, store

from .test_monitoring import mdb  # noqa: F401 - the fixture of the monitoring tests

pytestmark = pytest.mark.integration

PAIR = ("1", "1")
CALM = date(2010, 2, 1)
SHIFTED = date(2010, 3, 1)
LOANS = 600


def _pds(seed: int, scale: float = 1.0) -> np.ndarray:
    return np.clip(np.random.default_rng(seed).beta(2, 12, LOANS) * scale, 0.001, 0.99)


def _frame(pds: np.ndarray) -> Any:
    rows = [{"pd": float(p), "lgd": 0.6, "el_rate": float(p) * 0.6} for p in pds]
    return store._frame(rows)


def _write_month(conn: PgConnection, listed: date, pds: np.ndarray, first_id: int) -> None:
    request = uuid.uuid4()
    conn.execute(
        "INSERT INTO serving.requests (request_id, endpoint, status, latency_ms, api_version)"
        " VALUES (%s, '/predict/batch', 200, 1, 'test')",
        (request,),
    )
    with conn.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO serving.predictions
                (request_id, loan_id, listed, pd_version, lgd_version, api_version, covered,
                 pd, lgd, ead, expected_loss, el_rate, contributions, features, request)
            VALUES (%s, %s, %s, '1', '1', 'test', true, %s, 0.6, 10000, %s, %s, '{}', %s,
                    '{}')
            """,
            [
                (request, first_id + i, listed, float(p), float(p) * 6000, float(p) * 0.6,
                 json.dumps({"term": 36, "grade": "B"}))
                for i, p in enumerate(pds)
            ],
        )  # fmt: skip


def _monitoring_alerts(conn: PgConnection) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cursor:
        return cursor.execute(
            "SELECT * FROM ops.alerts WHERE kind IN ('prediction_drift', 'early_warning',"
            " 'performance_drop') ORDER BY alert_id"
        ).fetchall()


@pytest.fixture
def months(mdb: PgConnection, monkeypatch: pytest.MonkeyPatch) -> PgConnection:  # noqa: F811
    """A reference of 600 PDs, a calm month drawn alike, and a month with the PD doubled."""
    reference = _frame(_pds(0))
    monkeypatch.setattr(store, "scored_reference", lambda _conn, _champions, _months: reference)
    monkeypatch.setattr(store, "_champions", lambda pair, _prefix: pair)
    _write_month(mdb, CALM, _pds(1), 10_000)
    _write_month(mdb, SHIFTED, _pds(2, scale=2.0), 20_000)
    return mdb


# T30.1
def test_an_injected_change_of_the_pd_raises_the_alert(months: PgConnection) -> None:
    t = alerting.load()
    calm = store.monitor(months, CALM)
    assert (calm.alerts, _monitoring_alerts(months)) == (0, [])
    drifts = {r["subject"]: r["psi"] for r in _drift(months, CALM)}
    assert drifts["pd"] < t.psi["pd"], "the calm month is drawn like the reference"

    shifted = store.monitor(months, SHIFTED)
    found = _monitoring_alerts(months)
    subjects = {a["details"]["subject"] for a in found}
    assert shifted.alerts == shifted.alerts_recorded == len(found)
    assert "pd" in subjects
    assert "lgd" not in subjects, "the LGD did not move"
    pd_alert = next(a for a in found if a["details"]["subject"] == "pd")
    assert (pd_alert["kind"], pd_alert["severity"], pd_alert["period"]) == (
        "prediction_drift", "warning", SHIFTED,
    )  # fmt: skip
    assert pd_alert["details"]["psi"] > t.psi["pd"]
    assert pd_alert["details"]["psi"] == pytest.approx(
        {r["subject"]: r["psi"] for r in _drift(months, SHIFTED)}["pd"]
    )


def _drift(conn: PgConnection, period: date) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cursor:
        return cursor.execute(
            "SELECT * FROM monitoring.drift WHERE period = %s", (period,)
        ).fetchall()


# T30.2
def test_measuring_a_month_again_records_each_alert_once(months: PgConnection) -> None:
    first = store.monitor(months, SHIFTED)
    stored = _monitoring_alerts(months)
    again = store.monitor(months, SHIFTED)
    assert first.alerts_recorded == len(stored) > 0
    assert (again.alerts, again.alerts_recorded) == (first.alerts, 0)
    assert _monitoring_alerts(months) == stored


# T30.3
def test_the_new_kinds_are_accepted_with_their_severity_and_others_refused(
    mdb: PgConnection,  # noqa: F811
) -> None:
    period = date(2015, 1, 1)
    kinds = {
        "prediction_drift": alerts.Alert(
            "prediction_drift", "drift", period=period, details={"signal": "pd|pd=1|lgd=1"}
        ),
        "early_warning": alerts.Alert(
            "early_warning", "early", period=period, details={"signal": "term=36|pd=1"}
        ),
        "performance_drop": alerts.Alert(
            "performance_drop", "drop", period=period, details={"signal": "auc|term=36"}
        ),
        "lgd_level_shift": alerts.Alert(
            "lgd_level_shift", "level", period=period, model="lgd", version="3"
        ),
    }
    for alert in kinds.values():
        assert alerts.record(alert, mdb)
        assert not alerts.record(alert, mdb), "the same signal or version only once"
    with mdb.cursor() as cursor:
        found: dict[str, str] = dict(
            cursor.execute(
                "SELECT kind, severity FROM ops.alerts WHERE kind = ANY(%s)", (list(kinds),)
            ).fetchall()
        )
    assert found == {k: alerts.KINDS[k] for k in kinds}
    assert found["performance_drop"] == "error"
    with pytest.raises(errors.CheckViolation):
        mdb.execute(
            "INSERT INTO ops.alerts (kind, severity, message) VALUES ('drift', 'warning', 'x')"
        )
    with pytest.raises(errors.CheckViolation):  # a monitoring alert names its signal
        mdb.execute(
            "INSERT INTO ops.alerts (kind, severity, period, message)"
            " VALUES ('early_warning', 'warning', '2015-01-01', 'x')"
        )
