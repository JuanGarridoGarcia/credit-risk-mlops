"""The smoke test of the published images (D-134), run by ``ci/publish.py`` after pushing
and before moving ``main``; tested itself on every pull request (T22.3, T22.4).

It starts, under a compose project of its own and on free ports, Postgres, the MLflow
server (from ``train``) and the API (from ``serve``) with the images given, applies the
migrations and registers made-up champions as the API tests do. It then asks for:

- the commit and version inside ``train`` (the commit of the run, the version of the code);
- ``/health`` 200: champions loaded and database reachable;
- one ``/predict`` with PD, LGD and expected loss in range, and its ``prediction_id``.

Everything it started is removed at the end, whatever happened.

Usage: ``python -m tests.smoke --serve <image> --train <image> --commit <sha>``. It runs
in a process of its own: MLflow keeps its server address and experiment in globals.
"""

import argparse
import os
import subprocess
import sys
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Final

import httpx
import mlflow
from mlflow import MlflowClient

from credit_risk import __version__, registry
from credit_risk.buy_rule import NAME as RULE
from tests.api_support import ADMIN_KEY, PREDICT_KEY, loan, rule, toy_models
from tests.integration.api_process import free_port
from tests.integration.conftest import dbmate

ROOT: Final = Path(__file__).resolve().parent.parent
#: The services the API needs; compose starts their dependencies (Postgres) too.
SERVICES: Final = ("mlflow", "api")
USER: Final = "smoke"
PASSWORD: Final = "smoke-only-password"


class SmokeError(AssertionError):
    """The images failed the smoke test: the message says where."""


def _compose(project: str, env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", "--project-name", project, "--project-directory", str(ROOT),
         "--file", str(ROOT / "docker-compose.yml"), *args],
        env=env, capture_output=True, text=True, check=False,
    )  # fmt: skip


@contextmanager
def services(serve: str, train: str) -> Iterator[dict[str, str]]:
    """Postgres, MLflow and the API from the given images; yields their ports."""
    project = f"credit-risk-smoke-{uuid.uuid4().hex[:8]}"
    ports = {name: str(free_port()) for name in ("postgres", "mlflow", "api")}
    env = {
        **os.environ,
        "SERVE_IMAGE": serve,
        "TRAIN_IMAGE": train,
        "POSTGRES_DB": USER,
        "POSTGRES_USER": USER,
        "POSTGRES_PASSWORD": PASSWORD,
        "POSTGRES_PORT": str(ports["postgres"]),
        "MLFLOW_PORT": str(ports["mlflow"]),
        "API_PORT": str(ports["api"]),
        "API_KEYS_PREDICT": f"smoke:{PREDICT_KEY}",
        "API_KEYS_ADMIN": f"smoke-admin:{ADMIN_KEY}",
        # Only read by services the smoke test does not start (the worker, the clock and
        # Grafana); compose refuses to read the file without them (E-064).
        "API_PREDICT_KEY": PREDICT_KEY,
        "API_ADMIN_KEY": ADMIN_KEY,
        "GRAFANA_ADMIN_PASSWORD": PASSWORD,
        "GRAFANA_DB_PASSWORD": PASSWORD,
    }
    try:
        # Postgres is not ours and the publish job runs on a fresh machine, which has never
        # pulled it (E-055): pull it, by the digest pinned in compose.
        pulled = _compose(project, env, "pull", "--quiet", "postgres")
        if pulled.returncode != 0:
            raise SmokeError(f"cannot pull Postgres: {pulled.stderr.strip()[-2000:]}")
        # Ours were pulled before, by digest: never build or pull them here.
        up = _compose(project, env, "up", "--detach", "--wait", "--no-build", "--pull", "never",
                      *SERVICES)  # fmt: skip
        if up.returncode != 0:
            raise SmokeError(f"the services did not start: {up.stderr.strip()[-2000:]}")
        yield ports | {"project": project}
    except BaseException:
        logs = _compose(project, env, "logs", "--no-color", "--tail", "40", *SERVICES)
        print(logs.stdout[-6000:], file=sys.stderr)
        raise
    finally:
        _compose(project, env, "down", "--volumes", "--remove-orphans")


def _train_carries(train: str, commit: str) -> None:
    done = subprocess.run(
        ["docker", "run", "--rm", train, "python", "-c",
         "import os, credit_risk; print(os.environ.get('CREDIT_RISK_COMMIT', ''),"
         " credit_risk.__version__)"],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    if done.returncode != 0:
        raise SmokeError(f"the train image does not start: {done.stderr.strip()[-2000:]}")
    inside = done.stdout.split()
    if inside != [commit, __version__]:
        raise SmokeError(
            f"the train image carries commit and version {inside}, not {[commit, __version__]}"
        )


def _register(name: str, model: Any) -> None:
    mlflow.set_experiment(name)
    with mlflow.start_run() as run:
        pass
    registry.log_model(run.info.run_id, model)
    version = registry.register(name, run.info.run_id, f"runs:/{run.info.run_id}/model")
    MlflowClient().set_registered_model_alias(name, registry.CHAMPION, version)


def _champions(mlflow_port: str) -> None:
    mlflow.set_tracking_uri(f"http://127.0.0.1:{mlflow_port}")
    pd_model, lgd_model = toy_models()
    _register("pd", pd_model)
    _register("lgd", lgd_model)
    _register(RULE, rule(0.05, "1", "1"))


def _answers(api_port: str, timeout: float) -> dict[str, Any]:
    """``/health`` 200 within ``timeout`` seconds, then one prediction."""
    with httpx.Client(base_url=f"http://127.0.0.1:{api_port}", trust_env=False, timeout=30) as h:
        h.post("/admin/reload", headers={"X-API-Key": ADMIN_KEY})
        deadline = time.monotonic() + timeout
        while (health := h.get("/health")).status_code != 200:
            if time.monotonic() > deadline:
                raise SmokeError(f"/health answers {health.status_code}: {health.text}")
            time.sleep(1)
        answer = h.post("/predict", json=loan(1), headers={"X-API-Key": PREDICT_KEY})
    if answer.status_code != 200:
        raise SmokeError(f"/predict answers {answer.status_code}: {answer.text}")
    body: dict[str, Any] = answer.json()
    if not (
        isinstance(body.get("prediction_id"), int)
        and 0 < body["pd"] < 1
        and 0 <= body["lgd"] <= 1
        and 0 <= body["expected_loss"] <= body["ead"]
    ):
        raise SmokeError(f"/predict answers something out of range: {body}")
    return body


def smoke(
    serve: str, train: str, commit: str, *, champions: bool = True, timeout: float = 90
) -> dict[str, Any]:
    """Run the smoke test (see the module); returns the prediction, raises ``SmokeError``.

    ``champions=False`` leaves the registry empty: the API then never becomes ready, and
    the test must fail (T22.3).
    """
    _train_carries(train, commit)
    with services(serve, train) as ports:
        url = f"postgres://{USER}:{PASSWORD}@127.0.0.1:{ports['postgres']}/{USER}?sslmode=disable"
        try:
            dbmate(url, "up")
        except subprocess.CalledProcessError as error:
            raise SmokeError(f"the migrations failed: {error.stderr}") from error
        if champions:
            _champions(ports["mlflow"])
        return _answers(ports["api"], timeout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke test of the published images")
    parser.add_argument("--serve", required=True)
    parser.add_argument("--train", required=True)
    parser.add_argument("--commit", required=True)
    # For T22.3 only: an empty registry, and a shorter wait for /health.
    parser.add_argument("--no-champions", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--timeout", type=float, default=90, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        body = smoke(
            args.serve, args.train, args.commit,
            champions=not args.no_champions, timeout=args.timeout,
        )  # fmt: skip
    except Exception as error:  # noqa: BLE001 - any failure fails the smoke test
        print(f"smoke: FAILED: {error!r}", file=sys.stderr)
        return 1
    print(f"smoke: ok, PD {body['pd']:.4f}, LGD {body['lgd']:.4f}, EL {body['expected_loss']:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
