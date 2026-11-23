"""Fixtures of the simulator tests; the hand-made rows live in ``rows.py``."""

from collections.abc import Callable
from pathlib import Path

import polars as pl
import pytest

from .rows import BASIC, Row, frame, write_source


@pytest.fixture
def basic_rows() -> list[Row]:
    return [dict(r) for r in BASIC]


@pytest.fixture
def make_frame() -> Callable[[list[Row]], pl.DataFrame]:
    return frame


@pytest.fixture
def make_source(tmp_path: Path) -> Callable[[list[Row]], Path]:
    def _make(rows: list[Row]) -> Path:
        return write_source(rows, tmp_path / "source.csv.gz")

    return _make
