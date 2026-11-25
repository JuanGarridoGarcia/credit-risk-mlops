"""Names and tags of the published images (D-130 to D-132).

Every merge to main publishes each image under ``sha-`` and the first 7 characters of its
commit, a tag that never changes, and then moves ``main`` to it. A git tag ``vX.Y.Z``
builds nothing: it puts ``X.Y.Z`` on the image that its commit already published from
main (D-133). Anything else publishes nothing.
"""

import re
from dataclasses import dataclass
from typing import Final

REGISTRY: Final = "ghcr.io"
#: The two application images (D-078, D-131): target of the Dockerfile and local name.
IMAGES: Final = ("serve", "train")
MAIN: Final = "refs/heads/main"
_RELEASE: Final = re.compile(r"refs/tags/v(\d+\.\d+\.\d+)")
_COMMIT: Final = re.compile(r"[0-9a-f]{40}")


class PlanError(ValueError):
    """What was asked cannot be published: the message says why."""


@dataclass(frozen=True)
class Plan:
    """What one run publishes."""

    #: Repository of each image in the registry, by target.
    repositories: dict[str, str]
    #: The tag of the commit, ``sha-abc1234``: pushed on main, looked up on a release.
    commit_tag: str
    #: The tag moved once the smoke test passes: ``main`` or the version.
    promoted: str
    #: True on main (push the tested images); False on a release (reuse what main pushed).
    push: bool


def plan(ref: str, sha: str, version: str, repository: str, *, registry: str = REGISTRY) -> Plan:
    """The plan of a run on ``ref`` (``GITHUB_REF``) for commit ``sha``.

    ``version`` is the package's (``pyproject.toml``) and ``repository`` is
    ``owner/name`` as GitHub gives it; the registry only takes lowercase names.
    ``registry`` is GHCR (D-130) except in the rehearsal of T22.4.
    """
    if not _COMMIT.fullmatch(sha):
        raise PlanError(f"{sha!r} is not a full commit hash")
    owner = repository.split("/")[0].lower()
    if not owner:
        raise PlanError(f"{repository!r} has no owner")
    repositories = {i: f"{registry}/{owner}/credit-risk-{i}" for i in IMAGES}
    commit_tag = f"sha-{sha[:7]}"
    if ref == MAIN:
        return Plan(repositories, commit_tag, "main", push=True)
    if ref.startswith("refs/tags/"):
        release = _RELEASE.fullmatch(ref)
        if release is None:
            raise PlanError(f"{ref}: a release tag is vX.Y.Z, for example v0.2.0")
        if release.group(1) != version:
            raise PlanError(
                f"{ref}: the code of this commit is version {version} (pyproject.toml); "
                f"tag it v{version} or change the version first"
            )
        return Plan(repositories, commit_tag, release.group(1), push=False)
    raise PlanError(f"{ref}: only main and release tags vX.Y.Z are published")
