"""Helpers of the API tests (T18): made-up champions, a registry in a dictionary and a
store in memory that keeps the same promise as Postgres (one row per loan and pair).
"""

import threading
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Final

import polars as pl
import psycopg

from credit_risk.api.champions import Versions
from credit_risk.api.purchases import Order, Outcome, Prediction, Stored, judge
from credit_risk.api.scoring import Scored
from credit_risk.api.settings import ApiSettings
from credit_risk.api.store import ANSWER, Answer, Describe, RequestRow
from credit_risk.buy_rule import BuyRule
from credit_risk.lgd import train_lgd
from credit_risk.model import LGDModel, PDModel
from credit_risk.train import prepare_frame, train_pd
from tests.synthetic import CUTOFF, training_set
from tests.valid_rows import listing

PREDICT_KEY: Final = "p" * 40
NEXT_PREDICT_KEY: Final = "q" * 40
ADMIN_KEY: Final = "a" * 40


def settings(**values: Any) -> ApiSettings:
    base: dict[str, Any] = {
        "keys_predict": f"replayer:{PREDICT_KEY},replayer-next:{NEXT_PREDICT_KEY}",
        "keys_admin": f"flow:{ADMIN_KEY}",
        "reload_seconds": 0.2,
    }
    return ApiSettings(**{**base, **values})


def toy_models(seed: int = 13) -> tuple[PDModel, LGDModel]:
    """A PD and an LGD trained on made-up 36-month loans: 60 months is not covered."""
    frame = prepare_frame(training_set(seed=seed))
    pd_ = train_pd(frame, CUTOFF, trials=3)
    lgd = train_lgd(frame, CUTOFF, pd_.covered_terms, trials=3)
    return pd_.logistic, lgd.ridge


class FakeRegistry:
    """Aliases and models in a dictionary; ``broken`` versions fail to load."""

    def __init__(self) -> None:
        self.aliases: dict[str, str | None] = {"pd": None, "lgd": None, "buy_rule": None}
        self.models: dict[tuple[str, str], Any] = {}
        self.broken: set[tuple[str, str]] = set()
        self.down = False

    def put(self, kind: str, version: str, model: Any, *, champion: bool = True) -> None:
        self.models[(kind, version)] = model
        if champion:
            self.aliases[kind] = version

    def versions(self) -> Versions:
        if self.down:
            raise ConnectionError("registry down")
        return (self.aliases["pd"], self.aliases["lgd"], self.aliases["buy_rule"])

    def load(self, kind: str, version: str) -> Any:
        if (kind, version) in self.broken:
            raise OSError(f"cannot read {kind} v{version}")
        return self.models[(kind, version)]


def rule(minimum: float = 0.05, pd_version: str = "1", lgd_version: str = "1") -> BuyRule:
    return BuyRule(minimum, pd_version, lgd_version, "made-up")


class MemoryStore:
    """What :class:`credit_risk.api.store.Store` promises, in memory."""

    def __init__(self) -> None:
        self.requests: list[RequestRow] = []
        self.predictions: dict[tuple[int, Any, Any], dict[str, Any]] = {}
        self.purchases: dict[tuple[str, str], Stored] = {}
        self.up = True
        self.lock = threading.Lock()

    def open(self) -> None:
        pass

    def close(self) -> None:
        pass

    def alive(self) -> bool:
        return self.up

    def save(self, row: RequestRow, scored: Sequence[Scored]) -> list[Answer]:
        if not self.up:
            raise psycopg.OperationalError("database down")
        v = row.versions or {}
        with self.lock:
            self.requests.append(row)
            answers = []
            for s in scored:
                key = (s.loan_id, v.get("pd"), v.get("lgd"))
                earlier = key in self.predictions
                if not earlier:
                    values = {k: asdict(s).get(k) for k in ANSWER}
                    values["prediction_id"] = len(self.predictions) + 1
                    values["listed"] = s.listed.isoformat() if s.listed else None
                    values.update(
                        pd_version=v.get("pd"),
                        lgd_version=v.get("lgd"),
                        rule_version=v.get("buy_rule"),
                        api_version=row.api_version,
                    )
                    self.predictions[key] = values
                answers.append(Answer(self.predictions[key], earlier))
            return answers

    def purchase(
        self, row: RequestRow, orders: Sequence[Order], describe: Describe
    ) -> list[Outcome]:
        if not self.up:
            raise psycopg.OperationalError("database down")
        client = str(row.client)
        by_id = {v["prediction_id"]: v for v in self.predictions.values()}
        with self.lock:
            outcomes = []
            for order in orders:
                existing = self.purchases.get((client, order.order_id))
                v = by_id.get(order.prediction_id)
                prediction = None if v is None else Prediction(
                    v["prediction_id"], v["loan_id"], v["ead"], v["covered"], v["minimum"],
                    v["passes"],
                )  # fmt: skip
                held = sum(
                    (p.amount for p in self.purchases.values()
                     if prediction is not None and (p.client, p.loan_id)
                     == (client, prediction.loan_id)),
                    Decimal(0),
                )  # fmt: skip
                o = judge(order, existing, prediction, held)
                if o.status == "created":
                    assert o.loan_id is not None
                    assert o.policy is not None
                    stored = Stored(
                        len(self.purchases) + 1, client, order.order_id, order.prediction_id,
                        o.loan_id, Decimal(order.amount), o.policy, datetime.now(UTC),
                    )  # fmt: skip
                    self.purchases[(client, order.order_id)] = stored
                    o = Outcome("created", loan_id=o.loan_id, policy=o.policy, stored=stored)
                outcomes.append(o)
            describe(outcomes)
            self.requests.append(row)
            return outcomes

    def record(self, row: RequestRow) -> bool:
        if not self.up:
            return False
        with self.lock:
            self.requests.append(row)
        return True


def loan(id_: int, period: date = date(2015, 3, 1), **values: str | None) -> dict[str, Any]:
    """A delivered listing as the API receives it (every contract column, as text)."""
    return listing(id_, period, **values)


def raw_frame(items: list[dict[str, Any]]) -> pl.DataFrame:
    from credit_risk.api.scoring import frame_of

    return frame_of(items)
