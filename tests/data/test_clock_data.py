"""T17.9: a real year, 2014, lived by the simulated clock (D-106 to D-108), approved by
Juan on 2026-11-24.

Needs the real source file (``make data``) and the services of docker compose (``make
up``). The clock starts empty on a database of its own, with landing, training sets and
model names of its own, and replays 2014-01 to 2014-12 with the real number of trials:
twelve months loaded, four retrainings (January, April, July and October), every
verdict in MLflow and in ``ops.alerts``.
"""

import os
import time
import uuid
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import mlflow
import psycopg
import pytest
from mlflow import MlflowClient
from psycopg.rows import dict_row

from credit_risk import registry
from credit_risk.flows import Paths
from credit_risk.settings import Settings
from credit_risk.simulator import clock
from credit_risk.simulator.clock import World
from tests.integration.conftest import database_url, dbmate
from tests.integration.test_flows import _remove_models

pytestmark = pytest.mark.data

ROOT = Path(__file__).resolve().parents[2]
YEAR = [f"2014-{m:02d}" for m in range(1, 13)]


@pytest.fixture(scope="module")
def year(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, Any]]:
    """Replay 2014 from an empty clock; return what it left."""
    settings = Settings()
    folder = tmp_path_factory.mktemp("year")
    name = "test_clock_year"
    prefix = f"test-year-{uuid.uuid4().hex[:8]}-"
    with psycopg.connect(settings.postgres_conninfo(), autocommit=True) as admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        admin.execute(f'CREATE DATABASE "{name}"')
    previous = {k: os.environ.get(k) for k in ("POSTGRES_DB", "CREDIT_RISK_COMMIT")}
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    try:
        dbmate(database_url(settings, name), "up")
        os.environ["POSTGRES_DB"] = name
        os.environ["CREDIT_RISK_COMMIT"] = "d" * 40
        paths = Paths(
            landing=str(folder / "landing"),
            reports=str(folder / "validation"),
            training_sets=str(folder / "training_sets"),
        )
        world = World(source=str(ROOT / World().source), cache=str(ROOT / World().cache))
        start = time.perf_counter()
        months = clock.replay(YEAR[-1], world, paths, YEAR[0], prefix)
        print(f"\nreplay of 2014: {time.perf_counter() - start:.0f} s")
        conninfo = settings.postgres_conninfo().replace(
            f"dbname={settings.postgres_db}", f"dbname={name}"
        )
        with psycopg.connect(conninfo, row_factory=dict_row) as conn:
            alerts = conn.execute("SELECT * FROM ops.alerts ORDER BY alert_id").fetchall()
            sets = conn.execute("SELECT * FROM ops.training_sets").fetchall()
        yield {
            "months": months,
            "now": clock.now(),
            "alerts": alerts,
            "training_sets": sets,
            "prefix": prefix,
        }
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        _remove_models(prefix)
        with psycopg.connect(settings.postgres_conninfo(), autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


# T17.9
def test_a_real_year_runs_twelve_months_and_retrains_four_times(year: dict[str, Any]) -> None:
    assert year["months"] == YEAR
    assert year["now"] == date(2014, 12, 1)
    assert len(year["training_sets"]) == 4
    assert not [a for a in year["alerts"] if a["kind"] == "flow_failed"]

    client = MlflowClient()
    print("\nverdicts of 2014:")
    for target in ("pd", "lgd"):
        name = f"{year['prefix']}{target}"
        challengers = [
            v for v in client.search_model_versions(f"name='{name}'")
            if v.tags.get(registry.ROLE) == "challenger"
        ]  # fmt: skip
        assert len(challengers) == 4, f"{name}: one challenger per quarter"
        assert len({v.tags[registry.TRAINING_SET] for v in challengers}) == 4
        for version in sorted(challengers, key=lambda v: int(v.version)):
            tags = client.get_run(str(version.run_id)).data.tags
            decision = tags[registry.DECISION]
            assert tags[registry.OUTCOME] == decision, "every verdict carried out"
            rejected = [
                a for a in year["alerts"]
                if a["kind"] == "rejected" and a["model"] == name
                and a["version"] == version.version
            ]  # fmt: skip
            assert len(rejected) == (1 if decision == "rejected" else 0)
            print(f"  {target} v{version.version}: {decision} ({tags['promotion.reasons']})")
        promoted = [a for a in year["alerts"] if a["kind"] == "promoted" and a["model"] == name]
        assert promoted, f"{name} got its first champion"
        assert promoted[-1]["version"] == registry.champion(name)
        print(f"  {target} champion: v{registry.champion(name)}")
