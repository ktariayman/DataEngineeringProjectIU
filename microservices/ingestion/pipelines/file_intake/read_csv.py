"""
Pipeline step 1 - File Intake: Read CSV files.

Reads raw EdNet CSV/TSV sources into Spark DataFrames and persists them
as temporary Parquet in a staging area so downstream steps can pick them up.

Architecture diagram: "File Intake → Read CSV files"
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml
from pyspark.sql import DataFrame
from pyspark.sql.functions import col, from_unixtime, to_date

_project_root = str(Path(__file__).resolve().parents[4])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from microservices.ingestion.src.csv_reader import EdNetCSVReader
from microservices.ingestion.src.spark_session import get_spark_session

logger = logging.getLogger(__name__)


def _load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _add_event_date(df: DataFrame) -> DataFrame:
    """Derive ``event_date`` (DATE) from the ``timestamp`` column (epoch ms)."""
    return df.withColumn(
        "event_date",
        to_date(from_unixtime(col("timestamp") / 1000)),
    )


def read_all_sources(config_path: str) -> dict[str, DataFrame]:
    """Read all CSV sources defined in the config.

    Returns
    -------
    dict[str, DataFrame]
        Mapping of source name → raw DataFrame.
    """
    cfg = _load_config(config_path)

    spark = get_spark_session(
        app_name=cfg["spark"]["app_name"],
        master=cfg["spark"].get("master"),
        extra_config=cfg["spark"].get("config"),
    )
    reader = EdNetCSVReader(spark)

    dataframes: dict[str, DataFrame] = {}

    # ── KT4 ────────────────────────────────────────────────────────────
    try:
        src_kt4 = cfg["sources"]["kt4"]
        kt4_df = reader.read_kt4(
            path=src_kt4["path"],
            glob_pattern=src_kt4.get("glob_pattern", "*.csv"),
            delimiter=src_kt4.get("delimiter", "\t"),
        )
        kt4_df = _add_event_date(kt4_df)
        dataframes["kt4"] = kt4_df
    except Exception as exc:
        logger.error("[file_intake] FAILED to read 'kt4': %s", exc)

    # ── Lectures ───────────────────────────────────────────────────────
    try:
        src_lectures = cfg["sources"]["lectures"]
        dataframes["lectures"] = reader.read_lectures(path=src_lectures["path"])
    except Exception as exc:
        logger.error("[file_intake] FAILED to read 'lectures': %s", exc)

    # ── Questions ──────────────────────────────────────────────────────
    try:
        src_questions = cfg["sources"]["questions"]
        dataframes["questions"] = reader.read_questions(path=src_questions["path"])
    except Exception as exc:
        logger.error("[file_intake] FAILED to read 'questions': %s", exc)

    for name, df in dataframes.items():
        logger.info("[file_intake] Read '%s': %d rows, %d columns", name, df.count(), len(df.columns))

    if not dataframes:
        raise RuntimeError("All sources failed during file intake. Aborting pipeline.")

    return dataframes


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 1 - File Intake: Read EdNet CSVs.")
    parser.add_argument("--config", type=str, default="microservices/ingestion/config/ingestion_config.yaml")
    args = parser.parse_args()

    dfs = read_all_sources(args.config)
    for name, df in dfs.items():
        df.printSchema()
        df.show(5, truncate=False)
