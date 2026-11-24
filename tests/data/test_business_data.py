"""T15.7: the business metric on real data (D-096): the T0 champions against the baseline
on the loans listed in the 12 months after T0, with their final outcomes.

Needs every delivery in ``data/landing`` and the compose Postgres (``make up``). The T0
training set comes from the shared fixtures of ``conftest.py``; the outcomes of the
following year from a version built on the full load.
"""

from datetime import date
from pathlib import Path
from typing import cast

import polars as pl
import psycopg
import pytest

from credit_risk import registry
from credit_risk.business import SENSITIVITY, buy, candidates, caps, choose_minimum, realise
from credit_risk.lgd import lgd_rows, train_lgd
from credit_risk.snapshot import (
    EVALUATION,
    FEATURES,
    LABEL,
    SPLIT,
    Manifest,
    build,
    read_evaluation,
    read_features,
)
from credit_risk.storage import LocalStore
from credit_risk.train import prepare_frame, train_pd
from tests.data.conftest import T0

pytestmark = pytest.mark.data

Connection = psycopg.Connection[tuple[object, ...]]

YEAR = [date(2014 + (m // 12), m % 12 + 1, 1) for m in range(1, 13)]  # 2014-02 to 2015-01
#: A cutoff where every 36-month loan of that year has matured (36 + 5 months, D-040).
LATER = date(2018, 12, 1)
OUTCOMES = ("id", LABEL, "funded_amnt", "total_pymnt", "collection_recovery_fee")


def _listed(conn: Connection) -> dict[date, int]:
    rows = conn.execute(
        "SELECT date_trunc('month', issue_d)::date, count(*) FROM clean.listings GROUP BY 1"
    ).fetchall()
    return {cast(date, d): cast(int, n) for d, n in rows}


# T15.7
def test_the_t0_models_against_the_baseline_on_the_next_year(
    first: Manifest,
    t0_store: LocalStore,
    t0_conn: Connection,
    conn: Connection,
    full_load: Path,
    tmp_path: Path,
) -> None:
    # The T0 models and their champions (D-090), as in T12.6.
    listings = pl.read_parquet(t0_store.local(first.version, FEATURES))
    frame = prepare_frame(listings)
    pd_training = train_pd(frame, T0)
    lgd_training = train_lgd(frame, T0, pd_training.covered_terms)
    validation = listings.filter(pl.col(SPLIT) == "validation")
    lgd_verdict = registry.judge(
        "lgd", lgd_training.chosen, lgd_training.baseline, lgd_rows(validation)
    )
    investors = {
        "model": (
            pd_training.chosen,
            lgd_training.chosen if lgd_verdict.passed else lgd_training.baseline,
        ),
        "baseline": (pd_training.baseline, lgd_training.baseline),
    }
    t0_outcomes = (
        pl.read_parquet(t0_store.local(first.version, EVALUATION))
        .join(listings.select("id", LABEL), on="id")
        .select(OUTCOMES)
    )
    validation_months = sorted({d.replace(day=1) for d in validation["issue_d"].to_list()})

    # The following year, with outcomes known only later: used to measure, nothing else.
    store = LocalStore(tmp_path)
    later = build(conn, LATER, store, commit="data-test")
    later_listings = read_features(conn, store, later.version)
    year = later_listings.filter(pl.col("issue_d").dt.truncate("1mo").is_in(YEAR))
    year_outcomes = (
        read_evaluation(conn, store, later.version)
        .join(later_listings.select("id", LABEL), on="id")
        .select(OUTCOMES)
    )
    listed_before, listed_after = _listed(t0_conn), _listed(conn)

    seen: set[int] = set()
    lines = []
    for share in SENSITIVITY:
        k_validation = caps(listed_before, validation_months, share)
        k_year = caps(listed_after, YEAR, share)
        results = {}
        for name, (pd_model, lgd_model) in investors.items():
            minimum = choose_minimum(
                candidates(pd_model, lgd_model, validation), t0_outcomes, k_validation,
                seen=lambda ids: seen.update(ids.to_list()),
            )  # fmt: skip
            bought = buy(candidates(pd_model, lgd_model, year), minimum, k_year)
            assert set(bought["id"].to_list()) <= set(year["id"].to_list())
            terms = year.filter(pl.col("id").is_in(bought["id"].to_list()))["term"].unique()
            assert set(terms.to_list()) <= set(pd_training.covered_terms)
            results[name] = (minimum, realise(bought, year_outcomes, k_year))
        assert results["model"][1].budget == results["baseline"][1].budget
        for name, (minimum, p) in results.items():
            lines.append(
                f"cap {share:.0%} {name:8s} minimum {minimum:+.3f}: notes {p.notes}, "
                f"budget {p.budget:,.0f}, default rate {p.default_rate:.3f}, "
                f"loss {p.loss:.3f}, net return {p.net_return:+.4f}"
            )
    # Nothing of the measured year chose a minimum: only validation loans of T0.
    assert seen <= set(validation["id"].to_list())
    assert seen.isdisjoint(year["id"].to_list())
    print("\n" + "\n".join(lines))
