"""
HDFS-to-PostgreSQL reader.

Reads curated Parquet datasets from HDFS.
"""

from __future__ import annotations

import logging
from pyspark.sql import DataFrame, SparkSession

logger = logging.getLogger(__name__)


def read_parquet_from_hdfs(
    spark: SparkSession,
    path: str,
) -> DataFrame:
    """Read a Parquet dataset from HDFS.

    Parameters
    ----------
    spark : SparkSession
        Active Spark session.
    path : str
        Full HDFS path, e.g. ``hdfs://namenode:9000/data/curated/...``.

    Returns
    -------
    DataFrame
    """
    logger.info("[loader] Reading Parquet from %s", path)
    df = spark.read.parquet(path)
    logger.info("[loader] Read %d rows from %s", df.count(), path)
    return df
