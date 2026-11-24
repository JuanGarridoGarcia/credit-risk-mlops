"""B5, B7 and B8: the two application images (D-078).

B5: they run unprivileged, carry no secrets and stay small. B7: ``serve`` carries nothing
of training. B8: a model trained in ``train`` predicts the same once loaded in ``serve``.
"""

import json
import os
import uuid

import pytest
from mlflow import MlflowClient

import credit_risk
from tests.integration.conftest import IMAGES, REPO_ROOT, docker

pytestmark = pytest.mark.integration

# Budgets of D-078, on the unpacked size: the sum of the image's layers. It is the same on
# every machine, unlike `docker image inspect`, whose Size also counts the compressed
# layers under the containerd image store (E-028). Measured on 2026-11-24: serve 752 MB,
# train 1,229 MB. A jump above a budget means something that should not be there (data,
# Jupyter, compilers, training libraries in serve) entered the image.
MAX_IMAGE_SIZE_MB = {IMAGES["serve"]: 800, IMAGES["train"]: 1_500}

SECRET_MARKERS = ("PASSWORD", "SECRET", "TOKEN", "KAGGLE", "AWS_")


def _looks_secret(text: str) -> bool:
    return any(marker in text.upper() for marker in SECRET_MARKERS)


# B5
def test_image_runs_as_non_root(image: str) -> None:
    uid = docker("run", "--rm", "--entrypoint", "id", image, "-u")

    assert uid != "0"


def test_image_has_no_env_file(image: str) -> None:
    # Inspected as root so that no directory is skipped for lack of permissions.
    found = docker(
        "run", "--rm", "--user", "0", "--entrypoint", "find", image,
        "/", "-xdev", "-name", ".env*",
    )  # fmt: skip

    assert found == ""


def test_image_has_no_secrets_in_config(image: str) -> None:
    config = json.loads(docker("image", "inspect", image, "--format", "{{json .Config.Env}}"))
    history = docker("history", "--no-trunc", "--format", "{{.CreatedBy}}", image)

    env_names = [entry.split("=", 1)[0].upper() for entry in config]
    suspicious_env = [name for name in env_names if _looks_secret(name)]
    suspicious_steps = [step for step in history.splitlines() if _looks_secret(step)]

    assert suspicious_env == []
    assert suspicious_steps == []


def test_image_default_command_works(image: str) -> None:
    output = docker("run", "--rm", image)

    assert output == f"credit-risk {credit_risk.__version__}"


def test_image_size_within_budget(image: str) -> None:
    layers = docker("history", "--human=false", "--format", "{{.Size}}", image)
    size_mb = sum(int(size) for size in layers.split()) / 1e6

    assert size_mb <= MAX_IMAGE_SIZE_MB[image], f"{image} is {size_mb:.0f} MB"


# B7
@pytest.mark.parametrize("module", ["optuna", "shap", "mlflow.server"])
def test_serve_carries_nothing_of_training(module: str) -> None:
    # mlflow-skinny ships the module mlflow.server but not its dependencies, so the test
    # imports the module instead of only looking for it.
    command = f"""
try:
    import {module}
    print("imported")
except ImportError:
    print("missing")
"""
    found = docker("run", "--rm", "--entrypoint", "python", IMAGES["serve"], "-c", command)

    assert found == "missing"
    # The same import works in train, so the check above can tell them apart.
    found = docker("run", "--rm", "--entrypoint", "python", IMAGES["train"], "-c", command)
    assert found == "imported"


# B8: the scripts run inside the images. Both build the same made-up validation set; the
# training one registers its model in the MLflow server of compose, the serving one loads it.
_DATA = """
import json, sys
import polars as pl
sys.path.insert(0, "/work")
from synthetic import CUTOFF, training_set
from credit_risk import registry
from credit_risk.features import build_features
from credit_risk.snapshot import SPLIT
listings = training_set(seed=4)
validation = build_features(listings.filter(pl.col(SPLIT) == "validation"))
name = sys.argv[1]
"""

_TRAIN = (
    _DATA
    + """
import mlflow
from credit_risk.train import prepare_frame, train_pd
model = train_pd(prepare_frame(listings), CUTOFF, trials=2).chosen
mlflow.set_experiment(name)
with mlflow.start_run() as run:
    pass
version = registry.register(name, run.info.run_id, registry.log_model(run.info.run_id, model))
print(json.dumps({"version": version, "pd": model.predict_pd(validation).to_list()}))
"""
)

_SERVE = (
    _DATA
    + """
model = registry.load(name, sys.argv[2])
print(json.dumps({"pd": model.predict_pd(validation).to_list()}))
"""
)


def _run(image: str, script: str, *args: str) -> dict[str, object]:
    uri = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")
    output = docker(
        "run", "--rm", "--network", "host", "-e", f"MLFLOW_TRACKING_URI={uri}",
        "-e", "MLFLOW_DISABLE_AGENT_HINT=1",
        "-v", f"{REPO_ROOT / 'tests' / 'synthetic.py'}:/work/synthetic.py:ro",
        "--entrypoint", "python", image, "-c", script, *args,
    )  # fmt: skip
    answer: dict[str, object] = json.loads(output.splitlines()[-1])
    return answer


def test_a_model_trained_in_train_predicts_the_same_in_serve() -> None:
    name = f"test-images-{uuid.uuid4().hex[:8]}"
    try:
        trained = _run(IMAGES["train"], _TRAIN, name)
        served = _run(IMAGES["serve"], _SERVE, name, str(trained["version"]))
        assert trained["pd"], "no prediction"
        assert served["pd"] == trained["pd"]
    finally:
        client = MlflowClient(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
        for version in client.search_model_versions(f"name='{name}'"):
            client.delete_model_version(name, version.version)
        if client.search_registered_models(f"name='{name}'"):
            client.delete_registered_model(name)
        for experiment in client.search_experiments(filter_string=f"name = '{name}'"):
            client.delete_experiment(experiment.experiment_id)
