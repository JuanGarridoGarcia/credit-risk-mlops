"""T22.1: names and tags of the published images (D-130 to D-133).

The whole publication, against a registry of its own, is rehearsed in
``tests/integration/test_release.py`` (T22.4).
"""

import pytest
from ci.publish import PublishError, publish
from ci.tags import PlanError, plan

from credit_risk import __version__

SHA = "0123456789abcdef0123456789abcdef01234567"
REPOSITORY = "JuanGarridoGarcia/credit-risk-mlops"


class NothingPublished:
    """A registry with no image at all; it records what it is asked to change."""

    def __init__(self) -> None:
        self.changes: list[str] = []

    def image_id(self, ref: str) -> str | None:
        return None

    def remote_digest(self, ref: str) -> str | None:
        return None

    def tag(self, source: str, target: str) -> None:
        self.changes.append(f"tag {target}")

    def push(self, ref: str) -> str:
        self.changes.append(f"push {ref}")
        return "sha256:new"

    def copy(self, source: str, target: str) -> str:
        self.changes.append(f"copy {target}")
        return "sha256:new"

    def pull(self, ref: str) -> None:
        self.changes.append(f"pull {ref}")

    def remove(self, ref: str) -> None:
        self.changes.append(f"remove {ref}")


# T22.1
def test_main_publishes_the_commit_tag_and_then_moves_main() -> None:
    run = plan("refs/heads/main", SHA, __version__, REPOSITORY)
    # GHCR only takes lowercase names: the owner is lowered.
    assert run.repositories == {
        "serve": "ghcr.io/juangarridogarcia/credit-risk-serve",
        "train": "ghcr.io/juangarridogarcia/credit-risk-train",
    }
    assert (run.commit_tag, run.promoted, run.push) == ("sha-0123456", "main", True)


def test_a_release_tag_reuses_the_commit_and_adds_its_version() -> None:
    run = plan(f"refs/tags/v{__version__}", SHA, __version__, REPOSITORY)
    assert (run.commit_tag, run.promoted, run.push) == ("sha-0123456", __version__, False)


@pytest.mark.parametrize(
    ("ref", "sha", "message"),
    [
        ("refs/tags/v9.9.9", SHA, "version"),
        ("refs/tags/v0.2", SHA, "vX.Y.Z"),
        ("refs/tags/release", SHA, "vX.Y.Z"),
        ("refs/tags/v0.2.0-rc1", SHA, "vX.Y.Z"),
        ("refs/heads/feature", SHA, "only main"),
        ("refs/pull/13/merge", SHA, "only main"),
        ("refs/heads/main", "0123456", "full commit"),
        ("refs/heads/main", SHA.upper(), "full commit"),
    ],
    ids=["other version", "short version", "not a version", "pre-release", "other branch",
         "pull request", "short commit", "not a commit"],
)  # fmt: skip
def test_anything_else_publishes_nothing_and_says_why(ref: str, sha: str, message: str) -> None:
    with pytest.raises(PlanError, match=message):
        plan(ref, sha, __version__, REPOSITORY)


def test_a_release_of_a_commit_never_published_from_main_fails() -> None:
    run = plan(f"refs/tags/v{__version__}", SHA, __version__, REPOSITORY)
    registry = NothingPublished()
    with pytest.raises(PublishError, match="no published images"):
        publish(run, SHA, {}, registry, smoke=lambda *_: None)
    assert registry.changes == []
