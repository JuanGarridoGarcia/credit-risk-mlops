"""Scoring of listings by the champion pair: the core of the API, with no web framework.

The same functions as everywhere else: :func:`credit_risk.cleaning.convert` with the
rules of the delivery contract (D-045, D-116), :func:`credit_risk.features.build_features`,
the models' own ``predict_pd`` and ``predict_lgd``, the explanations of D-083 and the
expected return of the buy rule (D-084). Each loan is scored on its own row, so a loan
gets exactly the same answer alone or inside a batch (D-086, T18.4).
"""

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np
import polars as pl

from credit_risk.business import expected_return, scheduled_interest
from credit_risk.buy_rule import BuyRule
from credit_risk.cleaning import LISTING_RULES, convert
from credit_risk.contracts import LISTING_COLUMNS
from credit_risk.explain import explain, reasons
from credit_risk.features import FEATURES, build_features
from credit_risk.model import LGDModel, PDModel

#: Answer of a loan whose term has no model (D-070).
NOT_COVERED = "not covered: no model for this term (D-070)"


@dataclass(frozen=True)
class Champions:
    """The models in use, loaded together and replaced together (D-111)."""

    pd: PDModel
    lgd: LGDModel
    pd_version: str
    lgd_version: str
    rule: BuyRule | None = None
    rule_version: str | None = None

    @property
    def threshold(self) -> BuyRule | None:
        """The buy rule, only when it was chosen with this very pair (T18.10)."""
        if self.rule is not None and self.rule.matches(self.pd_version, self.lgd_version):
            return self.rule
        return None

    def versions(self) -> dict[str, str | None]:
        return {"pd": self.pd_version, "lgd": self.lgd_version, "buy_rule": self.rule_version}


@dataclass(frozen=True)
class Scored:
    """Everything the API answers and stores for one loan."""

    loan_id: int
    listed: date | None
    covered: bool
    pd: float | None
    lgd: float | None
    ead: float | None
    expected_loss: float | None
    el_rate: float | None
    expected_return: float | None
    minimum: float | None
    passes: bool | None
    base_value: float | None
    contributions: dict[str, float] | None
    reasons: list[dict[str, Any]]
    features: dict[str, Any]
    request: dict[str, str | None] = field(repr=False)


def frame_of(items: list[dict[str, str | None]]) -> pl.DataFrame:
    """Delivered listings as text, every contract column in order (absent ones null)."""
    return pl.DataFrame(
        [{c: item.get(c) for c in LISTING_COLUMNS} for item in items],
        schema=dict.fromkeys(LISTING_COLUMNS, pl.String()),
    )


def cleaning_errors(raw: pl.DataFrame) -> tuple[pl.DataFrame, list[list[dict[str, Any]]]]:
    """Clean every listing; return the typed frame and the errors of each row.

    A value that does not fit the rule of its column is an error of that loan only
    (D-117); the cleaning rules are those of the monthly load (D-045, D-116).
    """
    typed, masks = convert(raw, LISTING_RULES)
    errors: list[list[dict[str, Any]]] = [[] for _ in range(raw.height)]
    for column, mask in masks.items():
        rule = LISTING_RULES[column]
        for i in np.flatnonzero(mask.to_numpy()):
            errors[i].append(
                {
                    "column": column,
                    "rule": rule.value,
                    "value": raw[column][int(i)],
                    "message": f"value does not fit the {rule.value} rule of {column}",
                }
            )
    return typed, errors


def _number(value: float) -> float | None:
    return None if value is None or math.isnan(value) else float(value)


def score(champions: Champions, typed: pl.DataFrame, raw: pl.DataFrame) -> list[Scored]:
    """Score cleaned listings ``typed`` (``raw`` is what was delivered, stored as is)."""
    if typed.height == 0:
        return []
    features = build_features(typed)
    # The PD's model matrix once, for the PD and its explanation.
    x = champions.pd.prepare.transform(features)
    pd_ = champions.pd.predict_pd(features, x).to_numpy().astype(np.float64)
    lgd = champions.lgd.predict_lgd(features).to_numpy().astype(np.float64)
    pd_ = np.where(np.isnan(lgd), np.nan, pd_)
    lgd = np.where(np.isnan(pd_), np.nan, lgd)
    ead = features["loan_amnt"].cast(pl.Float64).to_numpy()
    interest = scheduled_interest(
        features["int_rate"].cast(pl.Float64).to_numpy(), features["term"].to_numpy()
    )
    returns = expected_return(pd_, lgd, interest)
    rule = champions.threshold
    explanation = explain(champions.pd, features, x)
    main = reasons(explanation, features)
    listed = typed["issue_d"].to_list()
    rows = features.to_dicts()
    requests = raw.to_dicts()
    out = []
    for i, row in enumerate(rows):
        covered = not (math.isnan(pd_[i]) or math.isnan(lgd[i]))
        contributions = explanation.contributions[i]
        er = _number(returns[i]) if covered else None
        out.append(
            Scored(
                loan_id=int(row["id"]),
                listed=listed[i].replace(day=1) if listed[i] is not None else None,
                covered=covered,
                pd=_number(pd_[i]) if covered else None,
                lgd=_number(lgd[i]) if covered else None,
                ead=_number(ead[i]),
                expected_loss=_number(pd_[i] * lgd[i] * ead[i]) if covered else None,
                el_rate=_number(pd_[i] * lgd[i]) if covered else None,
                expected_return=er,
                minimum=rule.minimum if rule is not None and covered else None,
                passes=(er is not None and er >= rule.minimum)
                if rule is not None and covered
                else None,
                base_value=explanation.base if covered else None,
                contributions=dict(zip(FEATURES, map(float, contributions), strict=True))
                if covered
                else None,
                reasons=[
                    {"feature": r.feature, "contribution": r.contribution, "value": r.value}
                    for r in main[i]
                ]
                if covered
                else [],
                features={k: v for k, v in row.items() if k != "id"},
                request={k: v for k, v in requests[i].items() if v is not None},
            )
        )
    return out
