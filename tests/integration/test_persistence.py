"""B4 and T8.2: data survive destroying and recreating the Postgres and MLflow containers.

`docker compose restart` would keep the same container (and its writable layer),
so it would pass even with a wrong volume. `down` + `up` creates a new container:
if the row is still there, it can only come from the volume. `down -v` (which
deletes the volume) is never used here.
"""

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import mlflow
import psycopg
import pytest
from mlflow import MlflowClient
from psycopg import sql

from credit_risk.settings import Settings
from tests.integration.conftest import compose

pytestmark = [pytest.mark.integration, pytest.mark.destructive]


@pytest.fixture
def table_name(settings: Settings) -> Iterator[str]:
    """A table name never used before; the table is dropped afterwards, pass or fail."""
    name = f"test_persistence_{uuid.uuid4().hex}"
    yield name
    with psycopg.connect(settings.postgres_conninfo(), autocommit=True) as conn:
        conn.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(name)))


# B4
def test_postgres_data_survives_container_recreation(settings: Settings, table_name: str) -> None:
    value = uuid.uuid4().hex
    table = sql.Identifier(table_name)
    with psycopg.connect(settings.postgres_conninfo(), autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE TABLE {} (value text NOT NULL)").format(table))
        conn.execute(sql.SQL("INSERT INTO {} (value) VALUES (%s)").format(table), (value,))
        old_container = compose("ps", "-q", "postgres").stdout.strip()

    compose("down")
    compose("up", "-d", "--wait", "postgres")

    new_container = compose("ps", "-q", "postgres").stdout.strip()
    assert new_container != old_container, "the container was not recreated"
    with psycopg.connect(settings.postgres_conninfo(), autocommit=True) as conn:
        rows = conn.execute(sql.SQL("SELECT value FROM {}").format(table)).fetchall()
    assert rows == [(value,)]


# T8.2
def test_mlflow_runs_and_artefacts_survive_container_recreation(tmp_path: Path) -> None:
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    compose("up", "-d", "--wait", "mlflow")
    value = uuid.uuid4().hex
    note = tmp_path / "note.txt"
    note.write_text(value)
    mlflow.set_experiment(f"test-persistence-{value[:8]}")
    with mlflow.start_run() as run:
        mlflow.log_artifact(str(note), artifact_path="files")
    old_container = compose("ps", "-q", "mlflow").stdout.strip()

    compose("up", "-d", "--force-recreate", "--wait", "mlflow")

    new_container = compose("ps", "-q", "mlflow").stdout.strip()
    assert new_container != old_container, "the container was not recreated"
    client = MlflowClient()
    assert client.get_run(run.info.run_id).info.status == "FINISHED"
    folder = mlflow.artifacts.download_artifacts(
        run_id=run.info.run_id, artifact_path="files", dst_path=str(tmp_path / "back")
    )
    assert (Path(folder) / "note.txt").read_text() == value
    client.delete_experiment(run.info.experiment_id)
