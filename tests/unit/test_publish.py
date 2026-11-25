"""T22.5: the brakes of ``ci/publish.py`` and its command line (D-132 to D-134).

The rehearsal of T22.4 runs the program against a real registry, where things go well
except in the cases it stages. Here a registry in memory makes each brake fire: the
publication stops, says why, and ``main`` is not moved.
"""

import json
import subprocess
from pathlib import Path

import ci.publish
import pytest
from ci.publish import Cli, PublishError, main, publish
from ci.tags import IMAGES, Plan, PlanError, plan

from credit_risk import __version__

SHA = "0123456789abcdef0123456789abcdef01234567"
REPOSITORY = "Owner/credit-risk-mlops"
TESTED = {"serve": "id-serve", "train": "id-train"}


class Registry:
    """Local images and a registry, in memory; it records what it is asked to do."""

    def __init__(self) -> None:
        self.local: dict[str, str] = {f"credit-risk:{i}": TESTED[i] for i in IMAGES}
        self.remote: dict[str, str] = {}  # "repository:tag" -> digest
        self.content: dict[str, str] = {}  # digest -> image id
        self.pulled_instead: dict[str, str] = {}  # digest -> another image id
        self.copied_as: str | None = None  # a digest the copy gets instead of its own
        self.calls: list[str] = []

    def image_id(self, ref: str) -> str | None:
        if "@" in ref:
            digest = ref.split("@")[1]
            return self.pulled_instead.get(digest, self.content.get(digest))
        if ref in self.remote:
            return self.content[self.remote[ref]]
        return self.local.get(ref)

    def remote_digest(self, ref: str) -> str | None:
        return self.remote.get(ref)

    def tag(self, source: str, target: str) -> None:
        self.local[target] = self.local[source]

    def push(self, ref: str) -> str:
        digest = f"sha256:{self.local[ref]}"
        self.content[digest] = self.local[ref]
        self.remote[ref] = digest
        self.calls.append(f"push {ref}")
        return digest

    def copy(self, source: str, target: str) -> str:
        self.remote[target] = self.copied_as or source.split("@")[1]
        self.calls.append(f"copy {target}")
        return self.remote[target]

    def pull(self, ref: str) -> None:
        self.calls.append(f"pull {ref}")

    def remove(self, ref: str) -> None:
        self.local.pop(ref, None)
        self.calls.append(f"remove {ref}")


def _main_run() -> tuple[Registry, Plan]:
    return Registry(), plan("refs/heads/main", SHA, __version__, REPOSITORY)


def _no_smoke(*_: str) -> None:
    pass


def _moved(registry: Registry) -> list[str]:
    return [c for c in registry.calls if c.startswith("copy")]


# T22.5
def test_an_image_that_was_not_tested_is_never_pushed() -> None:
    registry, run = _main_run()
    registry.local["credit-risk:train"] = "id-other"
    with pytest.raises(PublishError, match="not the image the integration job tested"):
        publish(run, SHA, TESTED, registry, _no_smoke)
    assert registry.calls == ["push ghcr.io/owner/credit-risk-serve:sha-0123456",
                              "pull ghcr.io/owner/credit-risk-serve@sha256:id-serve"]  # fmt: skip
    assert _moved(registry) == []


def test_an_image_pulled_back_that_is_not_the_tested_one_stops_everything() -> None:
    registry, run = _main_run()
    registry.pulled_instead["sha256:id-serve"] = "id-other"
    with pytest.raises(PublishError, match="pulled back is not the image tested"):
        publish(run, SHA, TESTED, registry, _no_smoke)
    assert _moved(registry) == []


def test_a_version_already_on_another_image_is_never_rewritten() -> None:
    registry = Registry()
    for image in IMAGES:
        repository = f"ghcr.io/owner/credit-risk-{image}"
        registry.remote[f"{repository}:sha-0123456"] = f"sha256:{TESTED[image]}"
        registry.content[f"sha256:{TESTED[image]}"] = TESTED[image]
        registry.remote[f"{repository}:{__version__}"] = "sha256:older"
    run = plan(f"refs/tags/v{__version__}", SHA, __version__, REPOSITORY)
    with pytest.raises(PublishError, match="a version is never rewritten"):
        publish(run, SHA, {}, registry, _no_smoke)
    assert registry.remote[f"ghcr.io/owner/credit-risk-serve:{__version__}"] == "sha256:older"
    assert _moved(registry) == []


def test_a_moved_tag_that_lands_on_another_digest_is_reported() -> None:
    registry, run = _main_run()
    registry.copied_as = "sha256:wrapped"  # what E-051 did
    with pytest.raises(PublishError, match="does not point to sha256:id-serve"):
        publish(run, SHA, TESTED, registry, _no_smoke)


def test_a_repeated_run_of_the_same_commit_finishes_without_pushing_again() -> None:
    registry, run = _main_run()
    publish(run, SHA, TESTED, registry, _no_smoke)
    registry.calls.clear()
    again = publish(run, SHA, TESTED, registry, _no_smoke)
    assert again.digests == {i: f"sha256:{TESTED[i]}" for i in IMAGES}
    assert [c for c in registry.calls if c.startswith("push")] == []
    assert _moved(registry) == [f"copy ghcr.io/owner/credit-risk-{i}:main" for i in IMAGES]


def test_a_fresh_pull_drops_the_local_copies_before_pulling() -> None:
    registry, run = _main_run()
    publish(run, SHA, TESTED, registry, _no_smoke, fresh_pull=True)
    serve = [c for c in registry.calls if "serve" in c]
    assert serve == [
        "push ghcr.io/owner/credit-risk-serve:sha-0123456",
        "remove credit-risk:serve",
        "remove ghcr.io/owner/credit-risk-serve:sha-0123456",
        "pull ghcr.io/owner/credit-risk-serve@sha256:id-serve",
        "copy ghcr.io/owner/credit-risk-serve:main",
    ]


def test_answers_of_docker_become_clear_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    answers: list[subprocess.CompletedProcess[str]] = []

    def docker(*args: str) -> subprocess.CompletedProcess[str]:
        return answers.pop(0)

    def answer(code: int, out: str = "", err: str = "") -> None:
        answers.append(subprocess.CompletedProcess([], code, out, err))

    monkeypatch.setattr(ci.publish, "_docker", docker)
    cli = Cli()
    answer(1, err="ERROR: ghcr.io/owner/x:sha-1: not found")
    assert cli.remote_digest("ghcr.io/owner/x:sha-1") is None
    answer(1, err="denied: permission_denied")
    with pytest.raises(PublishError, match=r"cannot ask the registry.*denied"):
        cli.remote_digest("ghcr.io/owner/x:sha-1")
    answer(1, err="unauthorized")
    with pytest.raises(PublishError, match=r"cannot push ghcr\.io/owner/x:sha-1: unauthorized"):
        cli.push("ghcr.io/owner/x:sha-1")
    answer(0)
    answer(1, err="manifest unknown")
    with pytest.raises(PublishError, match="pushed but the registry does not show it"):
        cli.push("ghcr.io/owner/x:sha-1")
    answer(0)
    answer(1, err="not found")
    with pytest.raises(PublishError, match="tagged but the registry does not show it"):
        cli.copy("ghcr.io/owner/x@sha256:a", "ghcr.io/owner/x:main")
    answer(1, err="No such image")
    cli.remove("credit-risk:serve")  # nothing to drop is fine
    assert answers == []


def test_the_command_line_says_why_it_stops_and_summarises_what_it_published(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    common = ["--sha", SHA, "--repository", REPOSITORY]
    assert main(["--ref", "refs/heads/feature", *common], Registry(), _no_smoke) == 1
    assert "only main and release tags" in capsys.readouterr().err
    assert main(["--ref", "refs/heads/main", *common], Registry(), _no_smoke) == 1
    assert "--tested must give the id of serve, train" in capsys.readouterr().err
    with pytest.raises(PlanError, match="has no owner"):
        plan("refs/heads/main", SHA, __version__, "/credit-risk-mlops")

    tested = tmp_path / "tested.json"
    tested.write_text(json.dumps(TESTED))
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    argv = ["--ref", "refs/heads/main", *common, "--tested", str(tested)]
    assert main(argv, Registry(), _no_smoke) == 0
    written = summary.read_text()
    assert written.startswith("### Published images")
    assert "| `ghcr.io/owner/credit-risk-serve` | `sha-0123456`, `main` | `sha256:id-serve` |" in (
        written
    )
