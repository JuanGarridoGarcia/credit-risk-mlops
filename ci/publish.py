"""Publish the tested images to the registry (D-130 to D-136).

On main, the CI job ``publish`` runs this once the four jobs pass, with the images the
job ``integration`` built and tested (D-133), after Trivy found nothing serious (D-135):

1. pushes each image under its commit tag ``sha-abc1234``, which is never rewritten: if
   the tag already holds another image, nothing is published;
2. pulls each image back from the registry by its digest and checks that it is the one
   tested;
3. runs the smoke test on the pulled images (D-134, ``tests/smoke.py``);
4. only then moves ``main`` to them.

On a release tag ``vX.Y.Z`` nothing is built or pushed: the images that the commit
published from main are pulled, smoke tested and tagged ``X.Y.Z`` (a version tag is never
rewritten either). A failure at any step leaves ``main`` and every version where they were.

Usage (from the root of the repository)::

    python -m ci.publish --ref refs/heads/main --sha <commit> --repository owner/name \\
        --tested tested.json [--registry ghcr.io] [--fresh-pull]
"""

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Protocol

from ci.tags import IMAGES, REGISTRY, Plan, PlanError, plan
from credit_risk import __version__

ROOT: Final = Path(__file__).resolve().parent.parent
#: Answers of a registry that mean "this tag does not exist" (not "I could not ask").
_ABSENT: Final = ("not found", "manifest unknown", "name unknown")


class PublishError(RuntimeError):
    """Nothing more is published: the message says why and what stays as it was."""


class Docker(Protocol):
    """What publishing needs of Docker; the real one runs the ``docker`` command."""

    def image_id(self, ref: str) -> str | None: ...
    def remote_digest(self, ref: str) -> str | None: ...
    def tag(self, source: str, target: str) -> None: ...
    def push(self, ref: str) -> str: ...
    def copy(self, source: str, target: str) -> str: ...
    def pull(self, ref: str) -> None: ...
    def remove(self, ref: str) -> None: ...


def _docker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=False)  # noqa: S603, S607


class Cli:
    """:class:`Docker` through the ``docker`` command."""

    def image_id(self, ref: str) -> str | None:
        done = _docker("image", "inspect", "--format", "{{.Id}}", ref)
        return done.stdout.strip() if done.returncode == 0 else None

    def remote_digest(self, ref: str) -> str | None:
        done = _docker("buildx", "imagetools", "inspect", "--format", "{{json .Manifest}}", ref)
        if done.returncode == 0:
            digest: str = json.loads(done.stdout)["digest"]
            return digest
        if any(a in done.stderr.lower() for a in _ABSENT):
            return None
        raise PublishError(f"cannot ask the registry about {ref}: {done.stderr.strip()}")

    def tag(self, source: str, target: str) -> None:
        self._ok(_docker("tag", source, target), f"tag {source} as {target}")

    def push(self, ref: str) -> str:
        self._ok(_docker("push", "--quiet", ref), f"push {ref}")
        digest = self.remote_digest(ref)
        if digest is None:
            raise PublishError(f"{ref} was pushed but the registry does not show it")
        return digest

    def copy(self, source: str, target: str) -> str:
        """Put tag ``target`` on the manifest of ``source`` in the registry, as it is."""
        self._ok(
            _docker("buildx", "imagetools", "create", "--tag", target, source),
            f"tag {source} as {target} in the registry",
        )
        digest = self.remote_digest(target)
        if digest is None:
            raise PublishError(f"{target} was tagged but the registry does not show it")
        return digest

    def pull(self, ref: str) -> None:
        self._ok(_docker("pull", "--quiet", ref), f"pull {ref}")

    def remove(self, ref: str) -> None:
        _docker("image", "rm", ref)

    @staticmethod
    def _ok(done: subprocess.CompletedProcess[str], what: str) -> None:
        if done.returncode != 0:
            raise PublishError(f"cannot {what}: {(done.stderr or done.stdout).strip()}")


#: The smoke test: (serve image, train image, commit) -> raises if the images fail it.
Smoke = Callable[[str, str, str], None]


def smoke_process(serve: str, train: str, commit: str) -> None:
    """Run ``tests/smoke.py`` in a process of its own (it starts its own services)."""
    done = subprocess.run(  # noqa: S603 - our own interpreter and module
        [sys.executable, "-m", "tests.smoke", "--serve", serve, "--train", train,
         "--commit", commit],
        cwd=ROOT, check=False,
    )  # fmt: skip
    if done.returncode != 0:
        raise PublishError("the smoke test failed (its output is above)")


@dataclass
class Published:
    """What a run published: the digest of each image and the tags that point to it."""

    plan: Plan
    digests: dict[str, str] = field(default_factory=dict)
    pushed: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = ["### Published images", "", "| Image | Tags | Digest |", "|---|---|---|"]
        for image, digest in self.digests.items():
            tags = f"`{self.plan.commit_tag}`, `{self.plan.promoted}`"
            lines.append(f"| `{self.plan.repositories[image]}` | {tags} | `{digest}` |")
        return "\n".join(lines) + "\n"


def publish(
    run: Plan,
    sha: str,
    tested: Mapping[str, str],
    docker: Docker,
    smoke: Smoke = smoke_process,
    *,
    local: Mapping[str, str] | None = None,
    fresh_pull: bool = False,
) -> Published:
    """Carry out ``run`` (see the module); ``tested`` is the image id of each tested image
    and ``local`` its local name (``credit-risk:serve``, ``credit-risk:train``)."""
    local = local or {i: f"credit-risk:{i}" for i in IMAGES}
    done = Published(run)
    for image in IMAGES:
        repository = run.repositories[image]
        commit_ref = f"{repository}:{run.commit_tag}"
        existing = docker.remote_digest(commit_ref)
        if run.push:
            expected = tested[image]
            if docker.image_id(local[image]) != expected:
                raise PublishError(f"{local[image]} is not the image the integration job tested")
            if existing is None:
                docker.tag(local[image], commit_ref)
                done.digests[image] = docker.push(commit_ref)
                done.pushed.append(commit_ref)
            else:
                # An earlier attempt of this commit may have pushed it: the same image is
                # fine, another one is never written over the tag of a commit.
                docker.pull(commit_ref)
                if docker.image_id(commit_ref) != expected:
                    raise PublishError(
                        f"{commit_ref} already holds another image; the tag of a commit is "
                        "never rewritten. Nothing was published"
                    )
                done.digests[image] = existing
            if fresh_pull:
                docker.remove(local[image])
                docker.remove(commit_ref)
        else:
            if existing is None:
                raise PublishError(
                    f"{commit_ref} does not exist: commit {sha[:7]} has no published images. "
                    "A release reuses what main published; merge it to main first"
                )
            done.digests[image] = existing
            expected = ""  # the release takes the published image as it is
        pinned = f"{repository}@{done.digests[image]}"
        docker.pull(pinned)
        pulled = docker.image_id(pinned)
        if expected and pulled != expected:
            raise PublishError(f"{pinned} pulled back is not the image tested ({expected})")
        # A version tag is never rewritten; main always moves forward.
        if run.promoted != "main":
            current = docker.remote_digest(f"{repository}:{run.promoted}")
            if current is not None and current != done.digests[image]:
                raise PublishError(
                    f"{repository}:{run.promoted} already holds another image; a version is "
                    "never rewritten. Change the version in pyproject.toml"
                )

    serve, train = (f"{run.repositories[i]}@{done.digests[i]}" for i in IMAGES)
    smoke(serve, train, sha)

    for image in IMAGES:
        repository = run.repositories[image]
        promoted = f"{repository}:{run.promoted}"
        # In the registry, without pulling or pushing: the very manifest smoke tested.
        if docker.copy(f"{repository}@{done.digests[image]}", promoted) != done.digests[image]:
            raise PublishError(f"{promoted} does not point to {done.digests[image]}")
        done.pushed.append(promoted)
    return done


def main(argv: list[str] | None = None, docker: Docker | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--ref", required=True, help="GITHUB_REF of the run")
    parser.add_argument("--sha", required=True, help="the commit of the run")
    parser.add_argument("--repository", required=True, help="owner/name on GitHub")
    parser.add_argument("--tested", type=Path, help="JSON: image id of each tested image")
    parser.add_argument("--registry", default=REGISTRY)
    parser.add_argument("--fresh-pull", action="store_true", help="drop local copies first")
    args = parser.parse_args(argv)
    try:
        run = plan(args.ref, args.sha, __version__, args.repository, registry=args.registry)
        tested = json.loads(args.tested.read_text()) if run.push and args.tested else {}
        if run.push and set(tested) != set(IMAGES):
            raise PublishError(f"--tested must give the id of {', '.join(IMAGES)}")
        done = publish(run, args.sha, tested, docker or Cli(), fresh_pull=args.fresh_pull)
    except (PlanError, PublishError) as error:
        print(f"publish: {error}", file=sys.stderr)
        return 1
    summary = done.summary()
    print(summary)
    if path := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(path).open("a") as out:
            out.write(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
