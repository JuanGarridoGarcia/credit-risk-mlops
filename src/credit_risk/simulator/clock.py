"""The simulated clock: the system lives through 2014 to 2018 one month at a time (D-107).

The clock belongs to the simulated world, like the rest of the simulator (D-043): in
production the calendar is real and nobody publishes deliveries, they arrive. Its state,
the last month the system completed, is one row of ``sim.clock``, a schema the system
never reads (T17.3).

``advance`` moves one month: it publishes the next month's deliveries, lets the simulated
investor send its listings to the API and buy (``replayer``, D-123), runs the system's
monthly flow for it (which retrains or not by its cadence, D-106), and only then writes the
month as done. If anything fails, the clock stays where it was and the next ``advance``
tries the same month again: a month is never skipped nor done twice. ``replay`` calls
``advance`` until a given month. Both are deployments of the Prefect server; ``advance``
has an interval schedule, paused by default.

``python -m credit_risk.simulator.clock serve`` serves both (the ``clock`` service).
"""

import argparse
import logging
from datetime import date
from pathlib import Path
from typing import Any, Final, cast

import psycopg
from prefect import flow, task
from pydantic import BaseModel, ConfigDict

from credit_risk import flows
from credit_risk.settings import Settings
from credit_risk.simulator.io import SOURCE_SHA256
from credit_risk.simulator.publish import load_prepared, publish
from credit_risk.simulator.replayer import invest_task
from credit_risk.train import LIGHTGBM_TRIALS

log = logging.getLogger(__name__)

#: First month of the replay (D-041).
T0: Final = "2014-01"
#: Real time between two simulated months when the schedule is switched on.
INTERVAL_SECONDS: Final = 600


class World(BaseModel):
    """Where the simulated world reads its source and writes its deliveries."""

    model_config = ConfigDict(frozen=True)

    source: str = "data/raw/accepted_2007_to_2018Q4.csv.gz"
    source_sha256: str = SOURCE_SHA256
    cache: str = "data/simulator"


def _month(text: str) -> date:
    return date.fromisoformat(f"{text}-01")


def _next(month: date) -> date:
    return date(month.year + month.month // 12, month.month % 12 + 1, 1)


def _connect() -> psycopg.Connection[Any]:
    return psycopg.connect(Settings().postgres_conninfo(), autocommit=True)


def now() -> date | None:
    """The last month the system completed, or None before the first one."""
    with _connect() as conn:
        row = conn.execute("SELECT month FROM sim.clock").fetchone()
    return None if row is None else row[0]


def _done(month: date) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO sim.clock (one, month) VALUES (true, %(month)s)
            ON CONFLICT (one) DO UPDATE SET month = %(month)s, updated_at = now()
            """,
            {"month": month},
        )


@task(name="publish", **flows.RETRY)
def publish_task(period: str, world: World, landing: str, history: bool) -> int:
    """The provider delivers ``period`` (D-043), and every month before it on the first
    run (``history``, D-041); return how many files."""
    prepared = load_prepared(Path(world.source), Path(world.cache), world.source_sha256)
    month = _month(period)
    since = None if history else month
    return len(publish(prepared, Path(landing), month, since=since))


@flow(name="advance", log_prints=True)
def advance(
    world: World | None = None,
    paths: flows.Paths | None = None,
    start: str = T0,
    prefix: str = "",
    trials: int = LIGHTGBM_TRIALS,
    cadence: str = flows.CADENCE,
) -> dict[str, Any]:
    """Move the system one month forward; ``start`` is the first month of an empty clock."""
    world, paths = world or World(), paths or flows.Paths()
    last = now()
    month = _month(start) if last is None else _next(last)
    period = f"{month:%Y-%m}"
    log.info("clock: %s -> %s", f"{last:%Y-%m}" if last else "empty", period)
    publish_task(period, world, paths.landing, history=last is None)
    # The investor decides with the champions of the month before, then the system's month
    # runs (D-123). A subflow: if it fails, so does this, and the clock does not move.
    investor = invest_task(period, paths.landing, start)
    summary = flows.monthly(period, paths, prefix, trials, cadence)
    _done(month)
    return {**summary, "investor": investor}


@flow(name="replay", log_prints=True)
def replay(
    until: str,
    world: World | None = None,
    paths: flows.Paths | None = None,
    start: str = T0,
    prefix: str = "",
    trials: int = LIGHTGBM_TRIALS,
    cadence: str = flows.CADENCE,
) -> list[str]:
    """Advance month after month until the clock reaches ``until``; return the months run."""
    end = _month(until)
    months = []
    while (last := now()) is None or last < end:
        summary = advance(world, paths, start, prefix, trials, cadence)
        months.append(summary["period"])
    log.info("replay: clock at %s", f"{last:%Y-%m}")
    return months


def serve() -> None:  # pragma: no cover - runs until stopped; covered by T17.8
    """Serve ``advance/advance`` (schedule paused) and ``replay/replay``."""
    from prefect import serve as serve_all
    from prefect.deployments.runner import RunnerDeployment

    deployments = [
        advance.to_deployment(name="advance", interval=INTERVAL_SECONDS, paused=True),
        replay.to_deployment(name="replay"),
    ]
    serve_all(*(cast(RunnerDeployment, d) for d in deployments))


def main(argv: list[str] | None = None) -> None:  # pragma: no cover - thin command line
    """``python -m credit_risk.simulator.clock serve`` (or ``now``)."""
    parser = argparse.ArgumentParser(description="The simulated clock (D-107).")
    parser.add_argument("action", choices=["serve", "now"])
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if args.action == "serve":
        serve()
    else:
        month = now()
        print(f"{month:%Y-%m}" if month else "empty")


if __name__ == "__main__":
    main()
