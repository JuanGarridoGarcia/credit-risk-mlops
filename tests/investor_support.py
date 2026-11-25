"""Checks of the simulated investor shared by the clock story (T21.2, T21.5) and the real
year (T17.9): every listing of a month has one prediction, and what was bought is what
the investor's rule gives on those predictions (D-085, D-123 to D-129).
"""

from datetime import date
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from credit_risk import business
from credit_risk.contracts import LISTINGS, delivery_path
from credit_risk.ingest import read_delivery
from credit_risk.simulator.replayer import NOTE, choose, k_of


def _ids(landing: str, month: date) -> list[int]:
    frame = read_delivery(delivery_path(Path(landing), month, LISTINGS), LISTINGS)
    return [int(i) for i in frame["id"].to_list()]


def check_month(conninfo: str, landing: str, month: date) -> dict[str, Any]:
    """Assert the investor's month; return its counts."""
    listed = _ids(landing, month)
    with psycopg.connect(conninfo, row_factory=dict_row) as conn:
        rows = conn.execute(
            "SELECT prediction_id, loan_id, expected_return, passes, minimum"
            " FROM serving.predictions WHERE listed = %s",
            (month,),
        ).fetchall()
        bought = conn.execute(
            "SELECT order_id, prediction_id, loan_id, amount, policy FROM serving.purchases"
            " WHERE client = 'replayer' AND order_id LIKE %s ORDER BY loan_id",
            (f"{month:%Y-%m}-%",),
        ).fetchall()
        invested = conn.execute(
            "SELECT listings, scored, refused, k, bought FROM sim.invested WHERE month = %s",
            (month,),
        ).fetchone()
    # Every listing of the month was sent once, and only those.
    assert sorted(r["loan_id"] for r in rows) == sorted(listed), month
    k = k_of(month, len(_ids(landing, business.previous(month))))
    answers = [
        {
            "prediction_id": r["prediction_id"],
            "loan_id": r["loan_id"],
            "expected_return": r["expected_return"],
            "threshold": None if r["minimum"] is None else {"passes": r["passes"]},
        }
        for r in rows
    ]
    expected = choose(answers, month, k)
    assert [(b["loan_id"], b["prediction_id"]) for b in bought] == [
        (a["loan_id"], a["prediction_id"]) for a in expected
    ], month
    assert all(b["amount"] == NOTE and b["policy"] == "passes" for b in bought), month
    assert all(b["order_id"] == f"{month:%Y-%m}-{b['loan_id']}" for b in bought), month
    assert invested == {
        "listings": len(listed), "scored": len(listed), "refused": 0, "k": k,
        "bought": len(bought),
    }, month  # fmt: skip
    passing = sum(1 for a in answers if (a["threshold"] or {}).get("passes"))
    return {"listings": len(listed), "passing": passing, "k": k, "bought": len(bought)}
