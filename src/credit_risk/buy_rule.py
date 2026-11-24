"""The buy rule as a registered policy (D-084, D-112, D-120).

The minimum expected return of the buy rule is chosen on validation with one pair of
models, the PD and the LGD (D-084, D-096). It is stored as a small object of its own in
the MLflow registry, ``buy_rule``, with the alias ``champion``: the minimum, the two
model versions it was chosen with and the training set version. The flow chooses a new
one whenever the champion of the PD or of the LGD changes; the API serves the threshold
only when the rule matches the pair it is using (T18.10).

Like the models, a rule is registered once per key (D-101): asking again for the same
pair finds the registered rule and only moves the alias.
"""

import json
import logging
import tempfile
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Final

import numpy as np
import polars as pl
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException

from credit_risk import registry
from credit_risk.business import CAP, NOTE, buy, candidates, caps, choose_minimum, received
from credit_risk.model import LGDModel, PDModel
from credit_risk.snapshot import LABEL, SPLIT
from credit_risk.tracking import Interval, RunRecord, library_versions, log_run

log = logging.getLogger(__name__)

NAME: Final = "buy_rule"
#: Tags of a registered rule that make up its key (D-101).
PD_VERSION: Final = "pd_version"
LGD_VERSION: Final = "lgd_version"
OUTCOMES: Final = ("id", LABEL, "funded_amnt", "total_pymnt", "collection_recovery_fee")
RESAMPLES: Final = 1_000


@dataclass(frozen=True)
class BuyRule:
    """Buy a loan when its expected return is at least ``minimum`` (D-084).

    ``pd_version`` and ``lgd_version`` are the registered versions the minimum was chosen
    with; the rule holds only for that pair.
    """

    minimum: float
    pd_version: str
    lgd_version: str
    training_set: str
    cap: float = CAP

    def matches(self, pd_version: str, lgd_version: str) -> bool:
        """Whether the rule was chosen with exactly this pair of models."""
        return (self.pd_version, self.lgd_version) == (pd_version, lgd_version)


@dataclass(frozen=True)
class Choice:
    """A chosen minimum and the realised net return it gave on validation."""

    minimum: float
    net_return: Interval
    notes: int


def listed(conn: Any) -> dict[date, int]:
    """Loans listed each month so far, from ``clean.listings`` (the monthly cap, D-085)."""
    rows = conn.execute(
        "SELECT date_trunc('month', issue_d)::date, count(*) FROM clean.listings GROUP BY 1"
    ).fetchall()
    return {d: int(n) for d, n in rows}


def months_of(frame: pl.DataFrame) -> list[date]:
    return sorted({d.replace(day=1) for d in frame["issue_d"].to_list()})


def choose(
    pd_model: PDModel,
    lgd_model: LGDModel,
    training_set: pl.DataFrame,
    evaluation: pl.DataFrame,
    listed: Mapping[date, int],
    *,
    seed: int = 0,
    resamples: int = RESAMPLES,
) -> Choice:
    """Choose the minimum on the validation split of ``training_set`` (D-084, D-096).

    ``evaluation`` holds the outcomes of the training set; ``listed`` the loans listed
    each month (the monthly cap, D-085). The net return at the chosen minimum comes with
    a bootstrap interval over the notes bought (D-075).
    """
    validation = training_set.filter(pl.col(SPLIT) == "validation")
    outcomes = evaluation.join(training_set.select("id", LABEL), on="id").select(OUTCOMES)
    k = caps(listed, months_of(validation))
    scored = candidates(pd_model, lgd_model, validation)
    minimum = choose_minimum(scored, outcomes, k)
    values, _ = received(buy(scored, minimum, k), outcomes)
    budget = NOTE * sum(k.values())

    def net(sample: np.ndarray) -> float:
        return float((sample.sum() - NOTE * len(sample)) / budget) if budget else 0.0

    rng = np.random.default_rng(seed)
    draws = [
        net(values[rng.integers(0, len(values), len(values))]) if len(values) else 0.0
        for _ in range(resamples)
    ]
    low, high = np.percentile(draws, [2.5, 97.5]) if draws else (0.0, 0.0)
    return Choice(minimum, Interval(net(values), float(low), float(high)), len(values))


def _registered(name: str, pd_version: str, lgd_version: str) -> str | None:
    """The registered rule of this pair, if any (newest when repeated)."""
    client = MlflowClient()
    try:
        client.get_registered_model(name)
    except MlflowException:
        return None
    found = client.search_model_versions(
        f"name='{name}' and tags.{PD_VERSION}='{pd_version}' and tags.{LGD_VERSION}='{lgd_version}'"
    )
    versions = sorted((int(v.version) for v in found), reverse=True)
    return str(versions[0]) if versions else None


def register(rule: BuyRule, choice: Choice, *, prefix: str, commit: str, seed: int) -> str:
    """Log the rule as a run with every required field (D-079) and register it."""
    name = f"{prefix}{NAME}"
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "rule.json"
        path.write_text(json.dumps(asdict(rule), indent=1))
        run_id = log_run(
            RunRecord(
                experiment=name,
                name=f"buy rule pd v{rule.pd_version} lgd v{rule.lgd_version}",
                commit=commit,
                snapshot=rule.training_set,
                seed=seed,
                versions=library_versions(),
                metrics={"net_return": choice.net_return},
                params={"minimum": rule.minimum, "cap": rule.cap, "notes": choice.notes},
                tags={PD_VERSION: rule.pd_version, LGD_VERSION: rule.lgd_version},
                files={"rule": path},
            )
        )
    registry.log_model(run_id, rule)
    source = f"runs:/{run_id}/{registry.MODEL_DIR}"
    tags = {PD_VERSION: rule.pd_version, LGD_VERSION: rule.lgd_version}
    return registry.register(name, run_id, source, tags)


def update(
    training_set_version: str,
    training_set: pl.DataFrame,
    evaluation: pl.DataFrame,
    listed: Mapping[date, int],
    *,
    prefix: str = "",
    commit: str,
    seed: int = 0,
) -> tuple[str | None, bool]:
    """Make the champion rule match the champion pair; return (its version, whether the
    alias moved).

    Nothing changes while the champion rule already matches the pair. A pair that already
    has a registered rule reuses it (D-101); otherwise its minimum is chosen on the
    validation of ``training_set`` and registered. With no champion PD or LGD yet there is
    no rule.
    """
    name = f"{prefix}{NAME}"
    pd_version = registry.champion(f"{prefix}pd")
    lgd_version = registry.champion(f"{prefix}lgd")
    if pd_version is None or lgd_version is None:
        return None, False
    current = registry.champion(name)
    if current is not None and load(name, current).matches(pd_version, lgd_version):
        return current, False
    version = _registered(name, pd_version, lgd_version)
    if version is None:
        choice = choose(
            registry.load(f"{prefix}pd", pd_version),
            registry.load(f"{prefix}lgd", lgd_version),
            training_set,
            evaluation,
            listed,
            seed=seed,
        )
        rule = BuyRule(choice.minimum, pd_version, lgd_version, training_set_version)
        version = register(rule, choice, prefix=prefix, commit=commit, seed=seed)
        log.info("%s v%s: minimum %+.3f for pd v%s, lgd v%s", name, version, rule.minimum,
                 pd_version, lgd_version)  # fmt: skip
    MlflowClient().set_registered_model_alias(name, registry.CHAMPION, version)
    return version, True


def load(name: str, version: str) -> BuyRule:
    """A registered rule."""
    rule: Any = registry.load(name, version)
    if not isinstance(rule, BuyRule):
        raise registry.RegistryError(f"{name} v{version} is not a buy rule")
    return rule
