"""T18.15: a real month through the API gives exactly what scoring it in process gives
(step 5.1, D-008), approved by Juan on 2026-11-24.

The models are trained on the real first training set (T0 = 2014-01); the month sent is
the delivery of 2014-02, as the provider wrote it, in batches of 1,000 (D-117), and every
answer is compared with :func:`credit_risk.api.scoring.score` on the whole month at once.
"""

from datetime import date

import polars as pl
import pytest
from fastapi.testclient import TestClient

from credit_risk.api.app import create_app
from credit_risk.api.champions import Holder
from credit_risk.api.scoring import Champions, cleaning_errors, score
from credit_risk.api.store import Store
from credit_risk.buy_rule import BuyRule, choose, listed
from credit_risk.contracts import LISTINGS, delivery_path
from credit_risk.ingest import read_delivery
from credit_risk.lgd import train_lgd
from credit_risk.settings import Settings
from credit_risk.snapshot import Manifest, read_evaluation, read_features
from credit_risk.storage import LocalStore
from credit_risk.train import prepare_frame, train_pd
from tests.api_support import PREDICT_KEY, FakeRegistry, settings
from tests.data.conftest import LANDING, T0, Connection

pytestmark = pytest.mark.data

MONTH = date(2014, 2, 1)
BATCH = 1_000


# T18.15
def test_a_real_month_through_the_api_equals_scoring_in_process(
    first: Manifest, t0_store: LocalStore, t0_conn: Connection
) -> None:
    training_set = read_features(t0_conn, t0_store, first.version)
    frame = prepare_frame(training_set)
    pd_model = train_pd(frame, T0, trials=5).chosen
    lgd_model = train_lgd(frame, T0, pd_model.covered_terms, trials=5).chosen
    choice = choose(
        pd_model,
        lgd_model,
        training_set,
        read_evaluation(t0_conn, t0_store, first.version),
        listed(t0_conn),
    )
    source = FakeRegistry()
    source.put("pd", "1", pd_model)
    source.put("lgd", "1", lgd_model)
    source.put("buy_rule", "1", BuyRule(choice.minimum, "1", "1", first.version))

    raw = read_delivery(delivery_path(LANDING, MONTH, LISTINGS), LISTINGS)
    typed, errors = cleaning_errors(raw)
    assert not any(errors)
    champions = Champions(pd_model, lgd_model, "1", "1", source.models[("buy_rule", "1")], "1")
    expected = {s.loan_id: s for s in score(champions, typed, raw)}

    dbname = t0_conn.info.dbname
    conninfo = (
        Settings()
        .postgres_conninfo()
        .replace(f"dbname={Settings().postgres_db}", f"dbname={dbname}")
    )
    t0_conn.execute("DELETE FROM serving.predictions")
    app = create_app(
        settings(), Holder(source, alert=lambda _: None), Store(conninfo, 2), polling=False
    )
    # Every column of the delivery, empty ones as null, as the replayer will send them.
    items = raw.to_dicts()
    answers = []
    with TestClient(app) as client:
        for start in range(0, len(items), BATCH):
            body = client.post(
                "/predict/batch",
                json={"loans": items[start : start + BATCH]},
                headers={"X-API-Key": PREDICT_KEY},
            )
            assert body.status_code == 200, body.text
            answers += body.json()["results"]
    assert len(answers) == raw.height
    rejected = [a for a in answers if "errors" in a]
    assert rejected == []
    covered = 0
    for a in answers:
        p = a["prediction"]
        s = expected[p["loan_id"]]
        assert p["covered"] == s.covered
        assert (p["pd"], p["lgd"], p["expected_loss"], p["expected_return"]) == (
            s.pd, s.lgd, s.expected_loss, s.expected_return
        )  # fmt: skip
        assert (p["threshold"] or {}).get("passes") == s.passes
        covered += s.covered
    stored = t0_conn.execute("SELECT count(*) FROM serving.predictions").fetchone()
    assert stored == (raw.height,)
    print(
        f"\nT18.15: {raw.height} loans of {MONTH:%Y-%m} through the API, {covered} covered,"
        f" minimum {choice.minimum:+.3f}, "
        f"{sum(1 for s in expected.values() if s.passes)} pass the threshold"
    )
    assert pl.Series([s.pd for s in expected.values() if s.covered]).is_between(0, 1).all()
