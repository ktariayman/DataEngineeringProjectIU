"""
Recommendation Loader — main pipeline entry point.

Flow:
  HDFS curated zone (Parquet)
      → hdfs_reader.read_recommendations()
      → postgres_writer.write_recommendations()
      → PostgreSQL recommendations table

Triggered by the scheduler after the processing job completes:
  docker compose run --rm -e MODE=initial recommendation_loader
  docker compose run --rm -e MODE=daily -e GENERATION_DATE=2026-02-23 recommendation_loader

Exit codes:
  0 → success
  1 → failure (schema error, DB error, HDFS read error)
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from typing import Optional

from microservices.serving.recommendation_loader.src.hdfs_reader import read_recommendations
from microservices.serving.recommendation_loader.src.postgres_writer import write_recommendations

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger(__name__)


def _parse_date(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format '{s}'. Expected YYYY-MM-DD.")


def main(mode: str, generation_date: Optional[date] = None) -> None:
    logger.info("=== Recommendation Loader [%s mode] ===", mode)

    if mode == "daily" and generation_date is None:
        raise ValueError("--generation-date is required in daily mode.")

    try:
        rows = read_recommendations(generation_date=generation_date)
        total = write_recommendations(rows=rows, mode=mode)
        logger.info("=== Loader completed. %d rows loaded. ===", total)
    except Exception as exc:
        logger.exception("Loader failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Recommendation Loader — HDFS to PostgreSQL.")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["initial", "daily"],
        required=True,
        help="'initial': TRUNCATE + load all. 'daily': idempotent upsert for one day.",
    )
    parser.add_argument(
        "--generation-date",
        type=_parse_date,
        default=None,
        help="Date of the batch to load (YYYY-MM-DD). Required for daily mode.",
    )
    args = parser.parse_args()
    main(mode=args.mode, generation_date=args.generation_date)
