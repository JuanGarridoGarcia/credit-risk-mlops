"""Model cards (D-095): one ``model_card.md`` for every registered version, stored with it.

The numbers come from what the version's run recorded in MLflow (tags, metrics and the
promotion evidence), never from a separate computation, so the card cannot disagree with
the model. The global importance is computed from the stored model itself, on the same
validation loans. The parts that do not come from data are the fixed text below,
reviewed in every pull request.
"""

import logging
from typing import Any, Final

import mlflow
import polars as pl
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException

from credit_risk import registry
from credit_risk.explain import importance
from credit_risk.features import build_features

log = logging.getLogger(__name__)

CARD_FILE: Final = "model_card.md"

#: Every card has these sections, in this order (T14.2).
SECTIONS: Final = (
    "Model",
    "Intended use",
    "Uses not intended",
    "Data",
    "Performance",
    "Segments",
    "Behavioural battery",
    "Most important features",
    "Features left out on purpose",
    "Known limits",
)

INTENDED: Final = {
    "pd": "Estimate the probability that a Lending Club loan listed now defaults before the "
    "end of its term, for an investor who decides which notes to buy (D-001). It is used "
    "with the LGD in the buy rule (D-084), and served with its four main reasons (D-083).",
    "lgd": "Estimate the share of the amount lent that is lost when a Lending Club loan "
    "defaults (D-017), for the expected return of the buy rule (D-084).",
}

NOT_INTENDED: Final = (
    "Deciding whether a person gets credit: the model ranks notes for an investor, it was "
    "never built or validated as a lending decision.",
    "Loans of a term it does not cover (D-070): they get no prediction.",
    "Loans listed long after its cutoff without a newer training: the data drift (the LGD "
    "rose every year up to 2010, D-094).",
    "Any other lender or population: it learned Lending Club's listings only.",
)

LEFT_OUT: Final = (
    ("State and zip code", "they can stand in for protected characteristics such as race "
     "(D-018); a credit model that uses them risks unfair treatment of whole areas"),
    ("Free text (employment title, description)", "not reliable, and can carry personal "
     "information (D-015)"),
    ("`installment`", "it is computed from the amount funded, known only after listing "
     "(leak, decided in F3)"),
    ("Payment and outcome columns", "they are known only after the loan is listed (D-014)"),
    ("Identifiers", "they carry no information about risk"),
)  # fmt: skip

LIMITS: Final = (
    "Trained on the loans known at its cutoff only; validation is the last six matured "
    "months of each term (D-069), so the newest loans it scores are a year or more younger.",
    "Built on a simulation of Lending Club's history replayed month by month (D-008); "
    "the real platform closed its note programme in 2020.",
    "Calibrated on validation (Platt for the PD, D-076; a level shift for the LGD, D-094); "
    "a trend after validation is not in the model and is watched by monitoring (F6).",
    "Reasons are contributions to the model's log-odds, not causes.",
    "Ranking better than the grade baseline does not by itself earn more: at T0 the buy "
    "rule with these models earned less than with the baseline at caps of 10% and 20% "
    "(D-097).",
)


class CardError(ValueError):
    """A model card cannot be built as required."""


def check_sections(text: str) -> None:
    """Fail, naming them, if any required section is missing from ``text`` (T14.2)."""
    missing = [s for s in SECTIONS if f"\n## {s}\n" not in f"\n{text}"]
    if missing:
        raise CardError(f"model card is missing sections: {', '.join(missing)}")


def _metrics(run: Any) -> list[tuple[str, float, float, float]]:
    metrics = run.data.metrics
    return [
        (name, metrics[name], metrics[f"{name}.low"], metrics[f"{name}.high"])
        for name in sorted(metrics)
        if "." not in name and f"{name}.low" in metrics
    ]


def _evidence(run_id: str) -> dict[str, Any] | None:
    try:
        evidence: dict[str, Any] = mlflow.artifacts.load_dict(
            f"runs:/{run_id}/promotion/evidence.json"
        )
    except MlflowException:
        return None
    return evidence


def build(name: str, version: str, target: registry.Target, validation: pl.DataFrame) -> str:
    """The card of ``version`` of ``name``; ``validation``: the run's validation listings."""
    client = MlflowClient()
    run_id = str(client.get_model_version(name, version).run_id)
    run = client.get_run(run_id)
    tags = run.data.tags
    model = registry.load(name, version)
    features = build_features(validation)
    evidence = _evidence(run_id)
    lines = [f"# Model card: {name} version {version}", ""]

    lines += ["## Model", ""]
    lines += [
        f"- Model: {tags.get('model', 'unknown')}",
        f"- Target: {target.upper()}",
        f"- Cutoff: {tags.get('cutoff', 'unknown')}",
        f"- Training set version: `{tags.get('snapshot', 'unknown')}`",
        f"- Commit: `{tags.get('commit', 'unknown')}`",
        f"- Seed: {run.data.params.get('seed', 'unknown')}",
        f"- Run: `{run_id}`",
        f"- Terms covered: {tags.get('covered_terms', 'none')} months (D-070)",
    ]
    if target == "pd":
        lines.append(
            f"- Features removed for a wrong sign (D-092): {tags.get('removed_features', 'none')}"
        )
        lines.append(
            f"- Platt scaling (a, b) on validation (D-076): {tags.get('platt', 'unknown')}"
        )
    else:
        lines.append(
            f"- Level shift fitted on validation (D-094): {tags.get('level_shift', 'none')}"
        )
    lines.append("")

    lines += ["## Intended use", "", INTENDED[target], ""]
    lines += ["## Uses not intended", "", *(f"- {u}" for u in NOT_INTENDED), ""]

    lines += ["## Data", "", "| Split | Loans | Defaults |", "|---|---|---|"]
    for split in ("train", "validation"):
        lines.append(
            f"| {split} | {tags.get(f'rows.{split}', 'unknown')} "
            f"| {tags.get(f'defaults.{split}', 'unknown')} |"
        )
    lines.append("")

    lines += ["## Performance", "", "On validation, with 95% bootstrap intervals (D-075).", ""]
    lines += ["| Metric | Value | Low | High |", "|---|---|---|---|"]
    lines += [f"| {m} | {v:.4f} | {lo:.4f} | {hi:.4f} |" for m, v, lo, hi in _metrics(run)]
    lines.append("")
    if evidence is not None:
        overall = evidence["overall"]
        lines += [
            f"Against the champion it was judged with: {overall['metric']} "
            f"{overall['new']:.4f} against {overall['current']:.4f}, improvement interval "
            f"[{overall['low']:.4f}, {overall['high']:.4f}]. "
            f"Outcome: {tags.get('promotion.outcome', 'unknown')}; reasons: "
            f"{tags.get('promotion.reasons', 'none')}.",
            "",
        ]

    lines += ["## Segments", ""]
    if evidence is None:
        lines += ["Not judged: this version is the reference the first challenger was "
                  "compared with (D-090).", ""]  # fmt: skip
    else:
        lines += ["| Segment | Metric | New | Current | Low | High | Margin | Blocking |"]
        lines += ["|---|---|---|---|---|---|---|---|"]
        lines += [
            f"| {s['segment']} | {s['metric']} | {s['new']:.4f} | {s['current']:.4f} "
            f"| {s['low']:.4f} | {s['high']:.4f} | {s['margin']} | {s['blocking']} |"
            for s in evidence["segments"]
        ]
        lines.append("")

    lines += ["## Behavioural battery", ""]
    if target == "lgd":
        lines += ["Not applicable: the battery checks the PD (D-086).", ""]
    elif evidence is None or "battery" not in evidence:
        lines += ["Not run: this version was not judged as a challenger (D-090).", ""]
    else:
        lines += ["| Check | Passed |", "|---|---|"]
        lines += [f"| {c} | {ok} |" for c, ok in evidence["battery"]["checks"].items()]
        lines.append("")

    unit = "log-odds" if target == "pd" else "LGD"
    lines += ["## Most important features", ""]
    lines += [f"Mean absolute contribution on validation, in {unit} (D-083).", ""]
    lines += ["| Feature | Mean absolute contribution |", "|---|---|"]
    lines += [f"| {f} | {v:.4f} |" for f, v in importance(model, features).items()]
    lines.append("")

    lines += ["## Features left out on purpose", ""]
    lines += [f"- {what}: {why}." for what, why in LEFT_OUT]
    lines.append("")
    lines += ["## Known limits", "", *(f"- {limit}" for limit in LIMITS), ""]

    text = "\n".join(lines)
    check_sections(text)
    return text


def write(name: str, version: str, target: registry.Target, validation: pl.DataFrame) -> str:
    """Build the card of ``version`` and store it in its run; return the text."""
    text = build(name, version, target, validation)
    run_id = str(MlflowClient().get_model_version(name, version).run_id)
    MlflowClient().log_text(run_id, text, CARD_FILE)
    log.info("model card of %s version %s stored", name, version)
    return text
