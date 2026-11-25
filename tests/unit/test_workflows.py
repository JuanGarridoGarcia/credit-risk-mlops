"""T22.2: the rules of continuous delivery, read from the workflows (D-130 to D-136).

What only runs on main cannot run in a pull request; these checks keep its rules from
being lost by an edit of the YAML.
"""

import re
from pathlib import Path
from typing import Any

import yaml
from ci.tags import plan

from credit_risk import __version__

WORKFLOWS = Path(__file__).parents[2] / ".github" / "workflows"
PINNED = re.compile(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}")


def _load(name: str) -> dict[str, Any]:
    loaded: dict[Any, Any] = yaml.safe_load((WORKFLOWS / name).read_text())
    # YAML 1.1 reads the key "on" as True.
    loaded["on"] = loaded.pop(True, loaded.get("on"))
    workflow: dict[str, Any] = loaded
    return workflow


def _steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = job["steps"]
    return steps


def _index(steps: list[dict[str, Any]], text: str) -> int:
    found = [i for i, s in enumerate(steps) if text in str(s.get("name", "")) + s.get("run", "")]
    assert len(found) == 1, f"one step with {text!r}: {found}"
    return found[0]


# T22.2
def test_publish_runs_only_on_main_and_releases_after_the_four_jobs() -> None:
    ci = _load("ci.yml")
    assert ci["on"]["push"] == {"branches": ["main"], "tags": ["v*"]}
    assert "pull_request" in ci["on"]
    publish = ci["jobs"]["publish"]
    assert set(publish["needs"]) == {"quality", "tests", "secrets", "integration"}
    assert set(ci["jobs"]) == {"quality", "tests", "secrets", "integration", "publish"}
    condition = publish["if"]
    assert "github.event_name == 'push'" in condition
    assert "github.ref == 'refs/heads/main'" in condition
    assert "startsWith(github.ref, 'refs/tags/v')" in condition
    # Cancelling is for pull requests only: a publication is never cut halfway.
    assert ci["concurrency"]["cancel-in-progress"] == "${{ github.event_name == 'pull_request' }}"


def test_only_publish_can_write_packages() -> None:
    for name in ("ci.yml", "security.yml"):
        workflow = _load(name)
        assert workflow["permissions"] == {"contents": "read"}, name
        for job_name, job in workflow["jobs"].items():
            permissions = job.get("permissions", {})
            if (name, job_name) == ("ci.yml", "publish"):
                assert permissions == {"contents": "read", "packages": "write"}
            else:
                assert permissions.get("packages") in (None, "read"), (name, job_name)
                assert set(permissions.values()) <= {"read"}, (name, job_name)


def test_publish_builds_nothing_and_goes_scan_push_smoke_promote() -> None:
    jobs = _load("ci.yml")["jobs"]
    integration, publish = _steps(jobs["integration"]), _steps(jobs["publish"])
    # The images travel from the job that tested them (D-133).
    keep = _index(integration, "docker save credit-risk:serve credit-risk:train")
    upload = _index(integration, "Upload the tested images")
    assert keep < upload
    assert integration[upload]["with"]["name"] == "tested-images"
    assert all("build-push-action" not in s.get("uses", "") for s in publish)
    assert all("docker build" not in s.get("run", "") for s in publish)
    download = _index(publish, "Download the images the integration job tested")
    assert publish[download]["with"]["name"] == "tested-images"
    # Trivy blocks on HIGH and CRITICAL (D-135) before anything is pushed.
    trivy = _index(publish, "Trivy")
    assert "--severity HIGH,CRITICAL --exit-code 1" in publish[trivy]["run"]
    assert "--ignorefile /work/.trivyignore.yaml" in publish[trivy]["run"]
    release = _index(publish, "Pull the images the commit published from main")
    push = _index(publish, "python -m ci.publish")
    assert download < trivy
    assert release < trivy < push
    assert push == len(publish) - 1
    # Push, smoke test and promotion are one step, in that order (ci/publish.py, T22.4).
    assert "--fresh-pull" in publish[push]["run"]


def test_every_action_is_pinned_by_its_commit() -> None:
    for path in sorted(WORKFLOWS.glob("*.yml")):
        for job in _load(path.name)["jobs"].values():
            for step in _steps(job):
                if "uses" in step:
                    assert PINNED.fullmatch(step["uses"]), (path.name, step["uses"])


def test_the_weekly_scan_reads_the_published_main_images() -> None:
    image = _load("security.yml")["jobs"]["image"]
    assert image["strategy"]["matrix"]["target"] == ["serve", "train"]
    run = plan("refs/heads/main", "0" * 40, __version__, "JuanGarridoGarcia/credit-risk-mlops")
    expected = run.repositories["serve"].replace("serve", "${{ matrix.target }}") + ":main"
    assert image["env"]["IMAGE"] == expected
    steps = _steps(image)
    assert all("build-push-action" not in s.get("uses", "") for s in steps)
    assert '"$IMAGE"' in steps[_index(steps, "Trivy")]["run"]
