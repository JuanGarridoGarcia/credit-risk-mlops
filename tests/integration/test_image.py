"""B5: the application images run unprivileged, carry no secrets and stay small."""

import json

import pytest

import credit_risk
from tests.integration.conftest import IMAGES, docker

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
