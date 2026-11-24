"""The monthly cycle, orchestrated with Prefect (step 4.1, D-099 to D-104).

The flow only coordinates: every task is one call into the functions of ``src/``, and
between tasks only identifiers travel (a month, a training set version, a registered
version, the covered terms), never data (D-100). Four tasks, each cut where its result is
already stored:

1. ``load``: every delivery that has arrived up to the month is loaded and validated
   (Postgres, D-104);
2. ``version``: the training set at the month (object storage and manifest);
3. ``train-pd``: PD trained, registered and judged for promotion (MLflow);
4. ``train-lgd``: the same for the LGD, on the terms the PD covers (MLflow).

The flow starts from the deliveries in the landing folder, as it would with a real
provider. Publishing them belongs to the simulated world, never to the system (D-043,
D-105): the simulator writes them before the flow runs.

Every task is idempotent, so running the flow again for the same month changes nothing
(D-049, D-061, D-101). Only transient failures are retried (D-102): a lost connection to
Postgres or MLflow. Anything else, a failed validation above all, stops the flow at once.

``python -m credit_risk.flows run 2014-01`` runs the flow in this process;
``serve`` registers it as a deployment of the Prefect server and waits for runs;
``server`` starts the Prefect server of docker compose on the project's Postgres.
"""

import argparse
import logging
import os
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Final
from urllib.parse import quote

import psycopg
from mlflow.exceptions import MlflowException
from prefect import flow, task
from prefect.client.schemas.objects import State, TaskRun
from prefect.tasks import Task
from psycopg import sql
from pydantic import BaseModel, ConfigDict

from credit_risk import pipeline
from credit_risk.ingest import catch_up
from credit_risk.settings import Settings
from credit_risk.snapshot import ROOT, build, git_commit, read_features
from credit_risk.storage import LocalStore
from credit_risk.train import LIGHTGBM_TRIALS

log = logging.getLogger(__name__)

#: Name of the flow and of its deployment on the Prefect server.
FLOW: Final = "monthly"
#: Name of the Prefect metadata database inside the project's Postgres (D-103).
DATABASE: Final = "prefect"
PORT: Final = 4200

# ---------------------------------------------------------------- retries (D-102)

#: Attempts after the first one, and the wait before each.
RETRIES: Final = 3
RETRY_DELAYS: Final = (10, 30, 90)
#: HTTP statuses of MLflow that mean "the server is not able right now".
TRANSIENT_STATUS: Final = frozenset({500, 502, 503, 504})


def is_transient(error: BaseException) -> bool:
    """Whether trying again may succeed: a lost connection, not a wrong input (D-102).

    Transient: the connection to Postgres (``psycopg.OperationalError``) or to MLflow
    (no answer, a timeout, or a 5xx answer). Anything else is permanent, including an
    error we do not know: a needless alert costs less than a blind retry.
    """
    if isinstance(error, psycopg.OperationalError):
        return True
    if isinstance(error, MlflowException):
        # How the MLflow client reports a request that got no answer (after its own
        # retries): "API request to <url> failed with [timeout] exception ...".
        message = str(error)
        if any(f"failed with {kind}exception" in message for kind in ("", "timeout ")):
            return True
        status: int = error.get_http_status_code()  # type: ignore[no-untyped-call]
        return status in TRANSIENT_STATUS
    return False


def retry_transient(_task: Task[Any, Any], _run: TaskRun, state: State[Any]) -> bool:
    """Prefect's ``retry_condition_fn``: retry only what :func:`is_transient` accepts."""
    error = state.data if isinstance(state.data, BaseException) else None
    if error is None:
        try:
            state.result(raise_on_failure=True)
        except BaseException as raised:  # noqa: BLE001 - classified right below
            error = raised
    retry = error is not None and is_transient(error)
    log.info("failure %r: %s", error, "transient, retrying" if retry else "permanent, stopping")
    return retry


RETRY: Final[dict[str, Any]] = {
    "retries": RETRIES,
    "retry_delay_seconds": list(RETRY_DELAYS),
    "retry_condition_fn": retry_transient,
}

# ---------------------------------------------------------------- tasks


def _month(text: str) -> date:
    return date.fromisoformat(f"{text}-01")


def _connect() -> psycopg.Connection[Any]:
    return psycopg.connect(Settings().postgres_conninfo(), autocommit=True)


class Paths(BaseModel):
    """Where the flow reads and writes; relative paths are from the working directory.

    A pydantic model, so that the Prefect server can pass it as a parameter (JSON).
    """

    model_config = ConfigDict(frozen=True)

    landing: str = "data/landing"
    reports: str = "data/validation"
    training_sets: str = str(ROOT)


@task(name="load", **RETRY)
def load_task(period: str, paths: Paths) -> int:
    """Load and validate every delivered month up to ``period`` (D-104); return how many."""
    with _connect() as conn:
        loaded = catch_up(conn, Path(paths.landing), _month(period), reports=Path(paths.reports))
    return len(loaded)


@task(name="version", **RETRY)
def version_task(period: str, paths: Paths) -> str:
    """Build (or find) the training set at ``period``; return its version."""
    with _connect() as conn:
        manifest = build(
            conn, _month(period), LocalStore(Path(paths.training_sets)), commit=git_commit()
        )
    return manifest.version


@dataclass(frozen=True)
class Trained:
    """What a training task hands on: identifiers and small facts, never data."""

    version: str
    covered_terms: tuple[int, ...]
    promoted: bool
    reasons: tuple[str, ...]
    reused: bool


def _summary(outcome: pipeline.Outcome) -> Trained:
    verdict = outcome.verdict
    return Trained(
        outcome.version,
        outcome.covered_terms,
        verdict.passed,
        tuple(verdict.reasons),
        outcome.reused,
    )


def _features(version: str, paths: Paths) -> Any:
    with _connect() as conn:
        return read_features(conn, LocalStore(Path(paths.training_sets)), version)


@task(name="train-pd", **RETRY)
def train_pd_task(period: str, version: str, paths: Paths, prefix: str, trials: int) -> Trained:
    """PD of the training set ``version``: trained, registered and judged (D-100, D-101)."""
    outcome = pipeline.retrain_pd(
        _features(version, paths), _month(period), version, prefix=prefix, trials=trials
    )
    return _summary(outcome)


@task(name="train-lgd", **RETRY)
def train_lgd_task(
    period: str,
    version: str,
    covered_terms: tuple[int, ...],
    paths: Paths,
    prefix: str,
    trials: int,
) -> Trained:
    """LGD of the training set ``version``, on the terms the PD covers (D-100, D-101)."""
    outcome = pipeline.retrain_lgd(
        _features(version, paths),
        _month(period),
        version,
        tuple(covered_terms),
        prefix=prefix,
        trials=trials,
    )
    return _summary(outcome)


# ---------------------------------------------------------------- the flow


@flow(name=FLOW, log_prints=True)
def monthly(
    period: str,
    paths: Paths | None = None,
    prefix: str = "",
    trials: int = LIGHTGBM_TRIALS,
) -> dict[str, Any]:
    """The monthly cycle up to ``period`` (YYYY-MM). ``prefix`` keeps test models apart."""
    paths = paths or Paths()
    _month(period)  # a malformed month fails here, before any task runs
    months = load_task(period, paths)
    version = version_task(period, paths)
    pd_ = train_pd_task(period, version, paths, prefix, trials)
    lgd = train_lgd_task(period, version, pd_.covered_terms, paths, prefix, trials)
    summary = {
        "period": period,
        "months_loaded": months,
        "training_set": version,
        "pd": pd_,
        "lgd": lgd,
    }
    log.info("monthly %s: %s", period, summary)
    return summary


# ---------------------------------------------------------------- server and deployment


def database_uri(settings: Settings) -> str:
    """SQLAlchemy address of the Prefect metadata database. Holds the password: never log it."""
    password = quote(settings.postgres_password.get_secret_value(), safe="")
    user = quote(settings.postgres_user, safe="")
    return (
        f"postgresql+asyncpg://{user}:{password}@{settings.postgres_host}:"
        f"{settings.postgres_port}/{DATABASE}"
    )


def create_database(settings: Settings) -> bool:
    """Create the ``prefect`` database if missing; return whether it was created."""
    with psycopg.connect(settings.postgres_conninfo(), autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DATABASE,))
        if exists.fetchone():
            return False
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DATABASE)))
        return True


def server() -> None:  # pragma: no cover - replaces the process; covered by T16.10
    """Create the metadata database if needed and become ``prefect server start``."""
    settings = Settings()
    if create_database(settings):
        log.info("created database %s", DATABASE)
    executable = shutil.which("prefect")
    if executable is None:
        raise RuntimeError("prefect is not installed (it is in the train image)")
    # The address goes through the environment, so the password never shows in `ps`.
    env = {**os.environ, "PREFECT_API_DATABASE_CONNECTION_URL": database_uri(settings)}
    args = [executable, "server", "start", "--host", "0.0.0.0", "--port", str(PORT)]  # noqa: S104
    os.execve(executable, args, env)  # noqa: S606


def serve() -> None:  # pragma: no cover - runs until stopped; covered by T16.10
    """Register the deployment ``monthly/monthly`` and run what the server sends it."""
    monthly.serve(name=FLOW)


def main(argv: list[str] | None = None) -> None:  # pragma: no cover - thin command line
    """``python -m credit_risk.flows run 2014-01`` (or ``serve``, ``server``)."""
    parser = argparse.ArgumentParser(description="The monthly cycle (step 4.1).")
    parser.add_argument("action", choices=["run", "serve", "server"])
    parser.add_argument("period", nargs="?", help="YYYY-MM (run)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if args.action == "server":
        server()
    elif args.action == "serve":
        serve()
    else:
        if args.period is None:
            parser.error("run needs a month, YYYY-MM")
        monthly(args.period)


if __name__ == "__main__":
    main()
