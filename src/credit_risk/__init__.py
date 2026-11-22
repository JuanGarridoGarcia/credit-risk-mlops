"""Credit risk MLOps system: PD, LGD and expected loss for Lending Club loans."""

from importlib.metadata import version

# Single source of truth for the version is pyproject.toml (test B1).
__version__: str = version("credit-risk")

__all__ = ["__version__"]
