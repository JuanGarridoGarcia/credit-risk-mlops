"""B1: the package imports and its version has a single source of truth."""

import tomllib
from importlib.metadata import version
from pathlib import Path

import credit_risk

PYPROJECT = Path(__file__).parents[2] / "pyproject.toml"


# B1
def test_package_version_matches_pyproject() -> None:
    declared = tomllib.loads(PYPROJECT.read_text())["project"]["version"]

    assert credit_risk.__version__ == declared
    assert version("credit-risk") == declared
