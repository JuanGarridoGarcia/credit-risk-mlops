"""Command line: ``python -m credit_risk.simulator --until 2014-01``."""

import argparse
import logging
from datetime import date
from pathlib import Path

from credit_risk.simulator.publish import load_prepared, publish


def _month(text: str) -> date:
    return date.fromisoformat(f"{text}-01")


def main(argv: list[str] | None = None) -> None:
    """Publish every monthly delivery up to the given month."""
    parser = argparse.ArgumentParser(description="Publish simulated Lending Club deliveries.")
    parser.add_argument("--until", type=_month, required=True, help="last month, YYYY-MM")
    parser.add_argument(
        "--source", type=Path, default=Path("data/raw/accepted_2007_to_2018Q4.csv.gz")
    )
    parser.add_argument("--landing", type=Path, default=Path("data/landing"))
    parser.add_argument("--cache", type=Path, default=Path("data/simulator"))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    prepared = load_prepared(args.source, args.cache)
    publish(prepared, args.landing, args.until)


if __name__ == "__main__":
    main()
