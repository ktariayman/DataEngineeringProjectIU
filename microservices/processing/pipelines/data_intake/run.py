"""
Pipeline step 1 – Data Intake: read Parquet from the HDFS raw zone.

Reads the ingestion-produced Parquet datasets (KT4 interactions, lectures
metadata, questions metadata) into Spark DataFrames for downstream
processing.

Architecture diagram: "Data Intake → Read from raw zone (Parquet)"
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from pyspark.sql import DataFrame
from pyspark.sql.functions import col

_project_root = str(Path(__file__).resolve().parents[4])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from microservices.processing.src.retry import retry
from microservices.processing.src.spark_session import get_spark_session

logger = logging.getLogger(__name__)


@retry(max_retries=3, backoff_sec=2.0, backoff_factor=2.0)
def _read_parquet(spark, path: str) -> DataFrame:
    """Read a Parquet dataset with retry on transient HDFS failures."""
    return spark.read.parquet(path)


def read_raw_sources(
    cfg: dict,
    window_days: Optional[int] = None,
) -> dict[str, DataFrame]:
    """Read all raw-zone sources defined in *cfg['sources']*.

    Parameters
    ----------
    cfg : dict
        Full processing config dict (must contain ``spark`` and ``sources``).
    window_days : int | None
        If set, filter KT4 data to the last *window_days* days (incremental mode).

    Returns
    -------
    dict[str, DataFrame]
        Mapping of source name → raw DataFrame.
    """
    spark = get_spark_session(
        app_name=cfg["spark"]["app_name"],
        master=cfg["spark"].get("master"),
        extra_config=cfg["spark"].get("config"),
    )

    sources = cfg["sources"]
    dataframes: dict[str, DataFrame] = {}

    # ── KT4 interactions ─────────────────────────────────────────────
    try:
        kt4_path = sources["kt4"]["path"]
        kt4_df = _read_parquet(spark, kt4_path)

        # Incremental windowing
        if window_days is not None and "event_date" in kt4_df.columns:
            cutoff = (
                datetime.now(timezone.utc) - timedelta(days=window_days)
            ).strftime("%Y-%m-%d")
            kt4_df = kt4_df.filter(col("event_date") >= cutoff)
            logger.info(
                "[data_intake] KT4 filtered to last %d days (>= %s).",
                window_days, cutoff,
            )

        dataframes["kt4"] = kt4_df
        logger.info("[data_intake] Read 'kt4' from %s", kt4_path)
    except Exception as exc:
        logger.error("[data_intake] FAILED to read 'kt4': %s", exc)

    # ── Lectures metadata ────────────────────────────────────────────
    try:
        lectures_path = sources["lectures"]["path"]
        dataframes["lectures"] = _read_parquet(spark, lectures_path)
        logger.info("[data_intake] Read 'lectures' from %s", lectures_path)
    except Exception as exc:
        logger.error("[data_intake] FAILED to read 'lectures': %s", exc)

    # ── Questions metadata ───────────────────────────────────────────
    try:
        questions_path = sources["questions"]["path"]
        dataframes["questions"] = _read_parquet(spark, questions_path)
        logger.info("[data_intake] Read 'questions' from %s", questions_path)
    except Exception as exc:
        logger.error("[data_intake] FAILED to read 'questions': %s", exc)

    if not dataframes:
        raise RuntimeError("All sources failed during data intake. Aborting pipeline.")

    return dataframes
