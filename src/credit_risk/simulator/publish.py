"""Publish the deliveries of every month up to a simulated date."""

import json
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import polars as pl

from credit_risk.contracts import LISTINGS, OUTCOMES, delivery_path
from credit_risk.simulator import core
from credit_risk.simulator.io import SOURCE_SHA256, read_source, write_delivery

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Prepared:
    """The snapshot with listing and resolution months, ready to slice into deliveries.

    ``loans`` is lazy: slicing a month reads only that month, so publishing does not
    hold the whole snapshot in memory more than once.
    """

    loans: pl.LazyFrame
    snapshot: date
    summary_rows_dropped: int


def prepare(source: pl.DataFrame) -> Prepared:
    """Drop summary rows and add the delivery months of every loan."""
    loans, dropped = core.drop_summary_rows(source)
    snapshot = core.snapshot_month(loans)
    return Prepared(core.add_periods(loans, snapshot).lazy(), snapshot, dropped)


def load_prepared(
    source_path: Path, cache_dir: Path, expected_sha256: str = SOURCE_SHA256
) -> Prepared:
    """Prepare the snapshot once and keep it in a cache keyed by the source hash.

    Reading and parsing 2.26 million rows takes most of a run; the cache lets the
    replay publish one month at a time without reading the source again.
    """
    cache = cache_dir / f"prepared_{expected_sha256[:16]}.parquet"
    meta = cache.with_suffix(".json")
    if not (cache.exists() and meta.exists()):
        prepared = prepare(read_source(source_path, expected_sha256))
        cache_dir.mkdir(parents=True, exist_ok=True)
        prepared.loans.sink_parquet(cache)
        meta.write_text(
            json.dumps(
                {
                    "snapshot": prepared.snapshot.isoformat(),
                    "summary_rows": prepared.summary_rows_dropped,
                }
            )
        )
    info = json.loads(meta.read_text())
    return Prepared(
        pl.scan_parquet(cache), date.fromisoformat(info["snapshot"]), info["summary_rows"]
    )


def publish(prepared: Prepared, landing: Path, until: date) -> list[Path]:
    """Write the deliveries of every month up to ``until`` (inclusive).

    Months after ``until`` are never written: the landing folder only holds what has
    "arrived" by the simulated date. Rewriting a month gives identical bytes.
    """
    written = []
    for period in core.all_periods(prepared.loans):
        if period > until:
            break
        for stream, frame in (
            (LISTINGS, core.listings_for(prepared.loans, period)),
            (OUTCOMES, core.outcomes_for(prepared.loans, period)),
        ):
            path = delivery_path(landing, period, stream)
            write_delivery(frame, path)
            written.append(path)
    log.info("published %d files up to %s", len(written), until)
    return written
