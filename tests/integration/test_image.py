"""B5: the application image runs unprivileged, carries no secrets and stays small."""

import json

import pytest

import credit_risk
from tests.integration.conftest import docker

pytestmark = pytest.mark.integration

# Measured at 211 MB on 2026-11-22 (F1) and 456 MB on 2026-11-23 after polars entered
# (its binary alone is 170 MB, D-052). A jump above this means something that should not
# be there (data, Jupyter, compilers) entered the image.
MAX_IMAGE_SIZE_MB = 500

SECRET_MARKERS = ("PASSWORD", "SECRET", "TOKEN", "KAGGLE", "AWS_")


def _looks_secret(text: str) -> bool:
    return any(marker in text.upper() for marker in SECRET_MARKERS)


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
    size_mb = int(docker("image", "inspect", image, "--format", "{{.Size}}")) / 1e6

    assert size_mb <= MAX_IMAGE_SIZE_MB, f"image is {size_mb:.0f} MB"
