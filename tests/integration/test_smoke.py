"""T22.3: the smoke test (D-134) on the images this pull request built.

The same program runs after every publication on main (``ci/publish.py``); here it is
shown to pass on good images and to fail, saying where, on images that are not.
"""

import json
import subprocess
import sys

import pytest

from .conftest import IMAGES, REPO_ROOT, docker

pytestmark = pytest.mark.integration


def commit_of(train: str) -> str:
    """The commit the train image was built from (``CREDIT_RISK_COMMIT``, D-079)."""
    env: list[str] = json.loads(
        docker("image", "inspect", train, "--format", "{{json .Config.Env}}")
    )
    [commit] = [e.split("=", 1)[1] for e in env if e.startswith("CREDIT_RISK_COMMIT=")]
    return commit


def _left() -> list[str]:
    """Compose projects of the smoke test still there."""
    projects = json.loads(docker("compose", "ls", "--all", "--format", "json"))
    return [p["Name"] for p in projects if p["Name"].startswith("credit-risk-smoke-")]


def _smoke(commit: str, *extra: str) -> subprocess.CompletedProcess[str]:
    """The smoke test as ``ci/publish.py`` runs it: a process of its own."""
    return subprocess.run(
        [sys.executable, "-m", "tests.smoke", "--serve", IMAGES["serve"],
         "--train", IMAGES["train"], "--commit", commit, *extra],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )  # fmt: skip


# T22.3
def test_the_smoke_test_passes_on_good_images_and_leaves_nothing() -> None:
    done = _smoke(commit_of(IMAGES["train"]))
    assert done.returncode == 0, done.stderr[-3000:]
    # MLflow prints its own lines first; the verdict is the last one.
    assert done.stdout.splitlines()[-1].startswith("smoke: ok, PD 0."), done.stdout[-2000:]
    assert _left() == []


def test_the_smoke_test_fails_when_the_api_never_gets_ready() -> None:
    # No champion in the registry: the API runs but is never ready.
    done = _smoke(commit_of(IMAGES["train"]), "--no-champions", "--timeout", "5")
    assert done.returncode == 1
    assert "smoke: FAILED" in done.stderr
    assert "/health answers 503" in done.stderr
    assert _left() == []


def test_the_smoke_test_fails_when_train_carries_another_commit() -> None:
    done = _smoke("f" * 40)
    assert done.returncode == 1
    assert "carries commit" in done.stderr
    assert _left() == []
