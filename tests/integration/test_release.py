"""T22.4: the publication of main and of a release, rehearsed against a registry of its
own (D-132 to D-134).

The publish job runs only on main; here ``ci/publish.py`` runs on every pull request, with
the images this pull request built and the real smoke test, against a throwaway registry
in a container. Nothing reaches GHCR.
"""

import json
import urllib.request
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Final

import pytest
from ci.publish import Cli, Published, PublishError, publish
from ci.tags import IMAGES as TARGETS
from ci.tags import plan

from credit_risk import __version__

from .api_process import free_port
from .conftest import IMAGES, docker
from .test_smoke import commit_of

pytestmark = pytest.mark.integration

#: The official registry, pinned by version and digest.
REGISTRY_IMAGE: Final = (
    "registry:3.0.0@sha256:6c5666b861f3505b116bb9aa9b25175e71210414bd010d92035ff64018f9457e"
)
REPOSITORY: Final = "Rehearsal/credit-risk-mlops"
OTHER: Final = "d" * 40


@dataclass
class Story:
    registry: str
    commit: str
    tested: dict[str, str]
    first: Published | None = None
    main_after_first: dict[str, str] = field(default_factory=dict)
    failed_smoke: str = ""
    main_after_failed_smoke: dict[str, str] = field(default_factory=dict)
    rewrite: str = ""
    after_rewrite: dict[str, dict[str, str]] = field(default_factory=dict)
    release: Published | None = None


def _digests(registry: str, tag: str) -> dict[str, str]:
    cli = Cli()
    run = plan("refs/heads/main", "0" * 40, __version__, REPOSITORY, registry=registry)
    found = {i: cli.remote_digest(f"{run.repositories[i]}:{tag}") for i in TARGETS}
    return {i: d for i, d in found.items() if d is not None}


def _tags(registry: str, image: str) -> set[str]:
    url = f"http://{registry}/v2/rehearsal/credit-risk-{image}/tags/list"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=10) as answer:
        return set(json.loads(answer.read())["tags"])


def _other_images() -> dict[str, str]:
    """Images that are not the tested ones: the same with one more label (no build)."""
    other = {}
    for image in TARGETS:
        name = f"rehearsal-{image}:{uuid.uuid4().hex[:8]}"
        container = docker("create", IMAGES[image])
        try:
            docker("commit", "--change", f"LABEL rehearsal={name}", container, name)
        finally:
            docker("rm", container)
        other[image] = name
    return other


@pytest.fixture(scope="module")
def story() -> Iterator[Story]:
    port = free_port()
    name = f"rehearsal-registry-{uuid.uuid4().hex[:8]}"
    docker("run", "--detach", "--rm", "--name", name, "--publish", f"127.0.0.1:{port}:5000",
           REGISTRY_IMAGE)  # fmt: skip
    registry = f"localhost:{port}"
    commit = commit_of(IMAGES["train"])
    tested = {i: docker("image", "inspect", "--format", "{{.Id}}", IMAGES[i]) for i in TARGETS}
    s = Story(registry, commit, tested)
    other: dict[str, str] = {}
    try:
        main = plan("refs/heads/main", commit, __version__, REPOSITORY, registry=registry)
        s.first = publish(main, commit, tested, Cli(), local=IMAGES)
        s.main_after_first = _digests(registry, "main")

        # Other images under another commit whose train does not carry it: the smoke
        # test fails after the push.
        other = _other_images()
        ids = {i: docker("image", "inspect", "--format", "{{.Id}}", other[i]) for i in TARGETS}
        broken = plan("refs/heads/main", OTHER, __version__, REPOSITORY, registry=registry)
        with pytest.raises(PublishError) as failed:
            publish(broken, OTHER, ids, Cli(), local=other)
        s.failed_smoke = str(failed.value)
        s.main_after_failed_smoke = _digests(registry, "main")

        # The same commit again, with images that are not the ones it published.
        with pytest.raises(PublishError) as refused:
            publish(main, commit, ids, Cli(), local=other)
        s.rewrite = str(refused.value)
        s.after_rewrite = {
            "commit": _digests(registry, main.commit_tag),
            "main": _digests(registry, "main"),
        }

        release = plan(f"refs/tags/v{__version__}", commit, __version__, REPOSITORY,
                       registry=registry)  # fmt: skip
        s.release = publish(release, commit, {}, Cli())
        yield s
    finally:
        docker("rm", "--force", name)
        for ref in docker("image", "ls", "--format", "{{.Repository}}:{{.Tag}}").split():
            if ref.startswith((f"{registry}/", "rehearsal-")):
                docker("image", "rm", ref)
        for ref in docker("image", "ls", "--digests", "--format",
                          "{{.Repository}}@{{.Digest}}").split():  # fmt: skip
            if ref.startswith(f"{registry}/"):
                docker("image", "rm", ref)


# T22.4
def test_the_published_images_are_the_tested_ones_and_main_points_to_them(story: Story) -> None:
    assert story.first is not None
    assert story.first.digests == story.main_after_first
    assert story.first.digests == _digests(story.registry, f"sha-{story.commit[:7]}")
    for image in TARGETS:
        pinned = f"{story.first.plan.repositories[image]}@{story.first.digests[image]}"
        assert docker("image", "inspect", "--format", "{{.Id}}", pinned) == story.tested[image]


def test_a_failed_smoke_test_leaves_main_where_it_was(story: Story) -> None:
    assert "smoke test failed" in story.failed_smoke
    assert story.main_after_failed_smoke == story.main_after_first
    # What failed stays in the registry under its commit, to be looked at.
    assert set(_digests(story.registry, f"sha-{OTHER[:7]}")) == set(TARGETS)
    assert _digests(story.registry, f"sha-{OTHER[:7]}") != story.main_after_first


def test_the_tag_of_a_commit_is_never_rewritten(story: Story) -> None:
    assert story.first is not None
    assert "never rewritten" in story.rewrite
    assert story.after_rewrite == {
        "commit": story.first.digests,
        "main": story.main_after_first,
    }


def test_a_release_tags_the_published_images_without_pushing(story: Story) -> None:
    assert story.release is not None
    assert story.release.digests == story.main_after_first
    assert _digests(story.registry, __version__) == story.main_after_first
    assert story.release.pushed == [
        f"{story.release.plan.repositories[i]}:{__version__}" for i in TARGETS
    ]
    for image in TARGETS:
        assert _tags(story.registry, image) == {
            f"sha-{story.commit[:7]}",
            "main",
            f"sha-{OTHER[:7]}",
            __version__,
        }
