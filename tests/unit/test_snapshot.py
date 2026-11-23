"""Tests T5 of training set versions that need no database, approved by Juan on 2026-11-23."""

from datetime import date
from pathlib import Path

import polars as pl

from credit_risk.ingest import file_sha256
from credit_risk.snapshot import content_hash


def _frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "id": [3, 1, 2, 4],
            "loan_amnt": [10_000.0, 0.1, None, -0.0],
            "term": pl.Series([36, 60, 36, None], dtype=pl.Int16),
            "issue_d": [date(2015, 3, 1), None, date(2007, 6, 1), date(2018, 12, 1)],
            "desc": ['a,"b"', "\\N", None, ""],
            "hardship_flag": [True, False, None, True],
        }
    )


def _bytes(frame: pl.DataFrame, path: Path, compression: str) -> tuple[str, pl.DataFrame]:
    frame.write_parquet(path, compression=compression)  # type: ignore[arg-type]
    return file_sha256(path), pl.read_parquet(path)


def _set(frame: pl.DataFrame, id_: int, column: str, value: object) -> pl.DataFrame:
    new = pl.when(pl.col("id") == id_).then(pl.lit(value)).otherwise(pl.col(column))
    return frame.with_columns(new.alias(column))


# T5.8
def test_content_hash_follows_the_data_not_the_file(tmp_path: Path) -> None:
    frame = _frame()
    shuffled = frame.reverse()
    zstd_sha, from_zstd = _bytes(frame, tmp_path / "a.parquet", "zstd")
    snappy_sha, from_snappy = _bytes(shuffled, tmp_path / "b.parquet", "snappy")
    assert zstd_sha != snappy_sha
    hashes = {content_hash({"f": f}) for f in (frame, shuffled, from_zstd, from_snappy)}
    assert len(hashes) == 1


def test_one_changed_value_changes_the_content_hash() -> None:
    frame = _frame()
    reference = content_hash({"f": frame})
    changed = [
        _set(frame, 2, "loan_amnt", 0.0),  # a missing value becomes 0
        _set(frame, 4, "loan_amnt", 0.0),  # -0.0 becomes 0.0
        _set(frame, 1, "desc", None),  # the text "\\N" becomes missing
        frame.with_columns(pl.col("term").cast(pl.Int64)),
        frame.rename({"desc": "title"}),
    ]
    hashes = [content_hash({"f": f}) for f in changed]
    assert reference not in hashes
    assert len(set(hashes)) == len(hashes)
    assert content_hash({"f": frame, "g": frame}) != content_hash({"f": frame})
