"""The exam of the frozen thresholds (D-150, T33.4): the simulation 2014-01 to 2018-12.

``make exam`` runs it: the clock starts empty on a database of its own (:data:`NAME`),
with landing, training sets and model names of its own, and replays every month with
the real number of trials, the API in a process of its own as in T17.9. It takes hours,
more than any single test may, so it is a command that resumes where it stopped (the
clock knows its month); ``FRESH=1`` starts it again from nothing. The data tests of
``test_calibration_data.py`` then read what it left.

Needs the real source file (``make data``) and the services of docker compose.
"""

import os
import shutil
import signal
import sys
import time
from pathlib import Path

import mlflow
import psycopg
from mlflow.tracking import MlflowClient

from credit_risk.flows import Paths
from credit_risk.settings import Settings
from credit_risk.simulator import clock
from credit_risk.simulator.clock import World
from tests.api_support import ADMIN_KEY, PREDICT_KEY
from tests.integration.api_process import api_process
from tests.integration.conftest import database_url, dbmate

ROOT = Path(__file__).resolve().parents[2]
#: The database, model prefix and folder of the exam.
NAME = "threshold_exam"
PREFIX = "exam-"
FOLDER = ROOT / "data" / "exam"
FIRST, LAST = "2014-01", "2018-12"


def conninfo(settings: Settings) -> str:
    """How to reach the database of the exam."""
    return settings.postgres_conninfo().replace(f"dbname={settings.postgres_db}", f"dbname={NAME}")


def forget() -> None:
    """Remove what an earlier exam left outside its database: the folders the system writes
    and the models and runs of :data:`PREFIX` (E-066). The log of the exam stays."""
    for folder in ("landing", "validation", "training_sets"):
        shutil.rmtree(FOLDER / folder, ignore_errors=True)
    client = MlflowClient()
    for model in client.search_registered_models(f"name LIKE '{PREFIX}%'"):
        for version in client.search_model_versions(f"name='{model.name}'"):
            client.delete_model_version(model.name, version.version)
        client.delete_registered_model(model.name)
    # The experiments stay, emptied: MLflow refuses to log into a deleted one.
    for experiment in client.search_experiments(filter_string=f"name LIKE '{PREFIX}%'"):
        for found in client.search_runs([experiment.experiment_id], max_results=50000):
            client.delete_run(found.info.run_id)


def run(until: str = LAST, *, fresh: bool = False) -> list[str]:
    """Replay up to ``until`` on the exam's database; return the months run now."""
    settings = Settings()
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    with psycopg.connect(settings.postgres_conninfo(), autocommit=True) as admin:
        exists = admin.execute("SELECT 1 FROM pg_database WHERE datname = %s", (NAME,)).fetchone()
        if fresh or not exists:
            admin.execute(f'DROP DATABASE IF EXISTS "{NAME}" WITH (FORCE)')
            forget()
            admin.execute(f'CREATE DATABASE "{NAME}"')
    dbmate(database_url(settings, NAME), "up")
    os.environ["POSTGRES_DB"] = NAME
    os.environ.setdefault("CREDIT_RISK_COMMIT", "e" * 40)
    paths = Paths(
        landing=str(FOLDER / "landing"),
        reports=str(FOLDER / "validation"),
        training_sets=str(FOLDER / "training_sets"),
    )
    world = World(source=str(ROOT / World().source), cache=str(ROOT / World().cache))
    with api_process(NAME, PREFIX, ready=False) as url:
        os.environ.update(API_URL=url, API_ADMIN_KEY=ADMIN_KEY, API_PREDICT_KEY=PREDICT_KEY)
        return clock.replay(until, world, paths, FIRST, PREFIX)


def _stop(signum: int, _frame: object) -> None:
    # SIGTERM would end the process at once and leave the API of the exam running, alone
    # and writing alerts into the exam's database (E-067): unwind instead, so it stops.
    sys.exit(128 + signum)


def main() -> None:
    signal.signal(signal.SIGTERM, _stop)
    until = sys.argv[1] if len(sys.argv) > 1 else LAST
    start = time.perf_counter()
    months = run(until, fresh=os.environ.get("FRESH") == "1")
    done = f"{months[0]} to {months[-1]}" if months else "nothing (already there)"
    print(f"exam: replayed {done} in {time.perf_counter() - start:.0f} s", flush=True)


if __name__ == "__main__":
    main()
