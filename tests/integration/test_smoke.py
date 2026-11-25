"""T22.3: the smoke test (D-134) on the images this pull request built.

The same program runs after every publication on main (``ci/publish.py``); here it is
shown to pass on good images and to fail, saying where, on images that are not.
"""

import json

import pytest

from tests.smoke import SmokeError, smoke

from .conftest import IMAGES, docker

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


# T22.3
def test_the_smoke_test_passes_on_good_images_and_leaves_nothing() -> None:
    body = smoke(IMAGES["serve"], IMAGES["train"], commit_of(IMAGES["train"]))
    assert isinstance(body["prediction_id"], int)
    assert 0 < body["pd"] < 1
    assert 0 <= body["lgd"] <= 1
    assert _left() == []


def test_the_smoke_test_fails_when_the_api_never_gets_ready() -> None:
    # No champion in the registry: the API runs but is never ready.
    with pytest.raises(SmokeError, match="/health answers 503"):
        smoke(IMAGES["serve"], IMAGES["train"], commit_of(IMAGES["train"]),
              champions=False, timeout=5)  # fmt: skip
    assert _left() == []


def test_the_smoke_test_fails_when_train_carries_another_commit() -> None:
    with pytest.raises(SmokeError, match="carries commit"):
        smoke(IMAGES["serve"], IMAGES["train"], "f" * 40)
    assert _left() == []
