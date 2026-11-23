"""B6: the test catalogue (docs/tests.md) and the test code say the same thing.

A test is marked in the code by a comment ``# <ID>`` just before its first function; the
functions that follow belong to it until the next marker. Each row of the catalogue names
its functions as ``file::function``.
"""

import ast
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOGUE = ROOT / "docs" / "tests.md"
TEST_ID = r"B\d+|T\d+\.\d+"
MARKER = re.compile(rf"^# ({TEST_ID})\b", flags=re.MULTILINE)
ROW = re.compile(rf"^\| ({TEST_ID}) \|(.*)$", flags=re.MULTILINE)
REF = re.compile(r"`(tests/[\w/]+\.py)::(\w+)`")


def _markers() -> dict[str, set[str]]:
    """Test ID -> files of tests/ where its marker is."""
    found: dict[str, set[str]] = defaultdict(set)
    for path in sorted((ROOT / "tests").rglob("test_*.py")):
        for test_id in MARKER.findall(path.read_text()):
            found[test_id].add(path.relative_to(ROOT).as_posix())
    return found


def _rows(doc: str) -> dict[str, set[tuple[str, str]]]:
    """Test ID -> (file, function) named by its row of the catalogue."""
    rows: dict[str, set[tuple[str, str]]] = {}
    for test_id, rest in ROW.findall(doc):
        assert test_id not in rows, f"{test_id} has two rows in docs/tests.md"
        rows[test_id] = set(REF.findall(rest))
    return rows


def _functions(file: str) -> set[str]:
    tree = ast.parse((ROOT / file).read_text())
    return {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}


# B6
def test_markers_and_catalogue_agree() -> None:
    doc = CATALOGUE.read_text()
    markers, rows = _markers(), _rows(doc)
    assert set(markers) == set(rows), "IDs in the code and in docs/tests.md differ"
    for test_id, refs in rows.items():
        assert refs, f"{test_id} names no function"
        assert markers[test_id] == {file for file, _ in refs}, f"{test_id}: marker in another file"
    for file, function in REF.findall(doc):
        assert (ROOT / file).is_file(), f"docs/tests.md names {file}, which does not exist"
        assert function in _functions(file), f"docs/tests.md names {file}::{function}"
