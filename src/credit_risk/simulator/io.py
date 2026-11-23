"""File input and output of the simulator: read and verify the source, write deliveries."""

import gzip
import hashlib
import io
from datetime import date
from pathlib import Path
from typing import Final

import polars as pl

from credit_risk.contracts import LISTINGS, OUTCOMES, SOURCE_COLUMNS
from credit_risk.simulator.core import SourceError

#: SHA-256 of ``accepted_2007_to_2018Q4.csv.gz`` recorded at the first download (D-012).
SOURCE_SHA256: Final = "55c16f75120f897683f02e7aabcf080d0e4a20c4832feb1d592cfa941bd62a2d"
_CHUNK: Final = 1 << 20
#: gzip level 6: measured 1.1 s and 8.8 MB for the largest month, against 10 s and 8.4 MB
#: at the default level 9 (E-015).
GZIP_LEVEL: Final = 6


def sha256(path: Path) -> str:
    """SHA-256 of a file, read in chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_source(path: Path, expected_sha256: str = SOURCE_SHA256) -> pl.DataFrame:
    """Read the snapshot as text after checking its hash and its columns (T1.1)."""
    got = sha256(path)
    if got != expected_sha256:
        raise SourceError(
            f"{path.name}: SHA-256 {got} does not match the expected {expected_sha256}"
        )
    frame = pl.read_csv(path, infer_schema=False)
    missing = SOURCE_COLUMNS - set(frame.columns)
    extra = set(frame.columns) - SOURCE_COLUMNS
    if missing or extra:
        raise SourceError(f"unexpected columns: missing {sorted(missing)}, extra {sorted(extra)}")
    return frame


def delivery_path(landing: Path, period: date, stream: str) -> Path:
    """``<landing>/YYYY-MM/<stream>.csv.gz``."""
    if stream not in (LISTINGS, OUTCOMES):
        raise ValueError(f"unknown stream {stream!r}")
    return landing / f"{period:%Y-%m}" / f"{stream}.csv.gz"


def write_delivery(frame: pl.DataFrame, path: Path) -> None:
    """Write a delivery as gzip CSV, byte-for-byte reproducible (T1.8).

    gzip stores a timestamp and the file name in its header by default; both are
    fixed so the same rows always give the same bytes (and the same hash, D-049).
    """
    buffer = io.BytesIO()
    frame.write_csv(buffer)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with (
        tmp.open("wb") as raw,
        gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=GZIP_LEVEL) as gz,
    ):
        gz.write(buffer.getvalue())
    tmp.replace(path)  # atomic: a reader never sees half a file
