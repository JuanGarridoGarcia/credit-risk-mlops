"""Every training run is logged to MLflow with a fixed list of required fields (D-079).

A run must be enough to find out, months later, what was trained and to train it again
(T8.4): the code (commit), the data (snapshot version, a content hash, D-059), the
environment (library versions) and the randomness (seed), plus every metric with its
bootstrap interval (D-075). :func:`log_run` is the only way runs are written and refuses
a record that lacks any of them (T8.3).

The tracking server itself runs in docker compose from the ``train`` image (D-091):
``python -m credit_risk.tracking server`` creates the ``mlflow`` database in the
project's Postgres if missing and starts ``mlflow server`` on it.
"""

import argparse
import logging
import math
import os
import platform
import shutil
from collections.abc import Mapping
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path
from typing import Final
from urllib.parse import quote

import mlflow
import psycopg
from psycopg import sql

from credit_risk.settings import Settings

log = logging.getLogger(__name__)

#: Name of the MLflow metadata database inside the project's Postgres (D-079).
DATABASE: Final = "mlflow"
#: Where the server keeps artefacts inside its container (a volume; S3 in AWS).
ARTIFACTS: Final = "/mlflow/artifacts"
PORT: Final = 5000

#: Libraries whose versions every run records: they decide what a model predicts.
LIBRARIES: Final = ("polars", "numpy", "scipy", "scikit-learn", "lightgbm", "mlflow-skinny")


class MissingFieldError(ValueError):
    """A run record lacks a required field (D-079); the message names it."""


@dataclass(frozen=True)
class Interval:
    """A metric with its 95% bootstrap interval (D-075)."""

    value: float
    low: float
    high: float


@dataclass(frozen=True)
class RunRecord:
    """Everything a training run logs. Required: commit, snapshot, seed, versions, metrics."""

    experiment: str
    name: str
    commit: str
    snapshot: str
    seed: int | None
    versions: Mapping[str, str]
    metrics: Mapping[str, Interval]
    params: Mapping[str, object] = field(default_factory=dict)
    tags: Mapping[str, str] = field(default_factory=dict)
    files: Mapping[str, Path] = field(default_factory=dict)


def library_versions() -> dict[str, str]:
    """The installed versions of :data:`LIBRARIES` and of Python."""
    return {
        "python": platform.python_version(),
        **{name: metadata.version(name) for name in LIBRARIES},
    }


def check(record: RunRecord) -> None:
    """Raise :class:`MissingFieldError` naming the first required field that is missing."""
    if not record.commit:
        raise MissingFieldError("commit")
    if not record.snapshot:
        raise MissingFieldError("snapshot")
    if record.seed is None:
        raise MissingFieldError("seed")
    missing = [name for name in ("python", *LIBRARIES) if not record.versions.get(name)]
    if missing:
        raise MissingFieldError(f"versions ({', '.join(missing)})")
    if not record.metrics:
        raise MissingFieldError("metrics")
    for name, metric in record.metrics.items():
        bounds = (metric.value, metric.low, metric.high)
        if not all(math.isfinite(x) for x in bounds) or not metric.low <= metric.high:
            raise MissingFieldError(f"interval of metric {name}")


def log_run(record: RunRecord) -> str:
    """Check ``record`` and log it as one MLflow run; return the run id."""
    check(record)
    mlflow.set_experiment(record.experiment)
    with mlflow.start_run(run_name=record.name) as run:
        mlflow.set_tags(
            {
                "commit": record.commit,
                "snapshot": record.snapshot,
                **{f"version.{lib}": v for lib, v in record.versions.items()},
                **record.tags,
            }
        )
        mlflow.log_params({"seed": record.seed, **record.params})
        for name, metric in record.metrics.items():
            mlflow.log_metrics(
                {name: metric.value, f"{name}.low": metric.low, f"{name}.high": metric.high}
            )
        for folder, path in record.files.items():
            mlflow.log_artifact(str(path), artifact_path=folder)
        return str(run.info.run_id)


# ---------------------------------------------------------------- tracking server


def backend_uri(settings: Settings) -> str:
    """SQLAlchemy address of the metadata database. Holds the password: never log it."""
    password = quote(settings.postgres_password.get_secret_value(), safe="")
    user = quote(settings.postgres_user, safe="")
    return (
        f"postgresql+psycopg://{user}:{password}@{settings.postgres_host}:"
        f"{settings.postgres_port}/{DATABASE}"
    )


def create_database(settings: Settings) -> bool:
    """Create the ``mlflow`` database if missing; return whether it was created."""
    with psycopg.connect(settings.postgres_conninfo(), autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DATABASE,))
        if exists.fetchone():
            return False
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DATABASE)))
        return True


def server() -> None:  # pragma: no cover - replaces the process; covered by T8.1 and T8.2
    """Create the metadata database if needed and become ``mlflow server``."""
    settings = Settings()
    if create_database(settings):
        log.info("created database %s", DATABASE)
    executable = shutil.which("mlflow")
    if executable is None:
        raise RuntimeError("mlflow is not installed (it is in the train image)")
    # The address goes through the environment, so the password never shows in `ps`.
    env = {**os.environ, "MLFLOW_BACKEND_STORE_URI": backend_uri(settings)}
    args = [
        executable, "server", "--host", "0.0.0.0", "--port", str(PORT),  # noqa: S104
        "--serve-artifacts", "--artifacts-destination", ARTIFACTS,
    ]  # fmt: skip
    os.execve(executable, args, env)  # noqa: S606


def main(argv: list[str] | None = None) -> None:  # pragma: no cover - see server()
    """``python -m credit_risk.tracking server``."""
    parser = argparse.ArgumentParser(description="MLflow tracking server (D-079).")
    parser.add_argument("action", choices=["server"])
    parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    server()


if __name__ == "__main__":
    main()
