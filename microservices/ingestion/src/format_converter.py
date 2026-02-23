"""
Format conversion utilities: CSV DataFrame → Parquet.

This module is the implementation behind the ``format_conversion`` pipeline
step shown in the architecture diagram.

Reliability: writes are wrapped with ``@retry`` so transient HDFS failures
(NameNode failover, network hiccups) do not crash the pipeline.
"""

from __future__ import annotations

import logging

from pyspark.sql import DataFrame

from microservices.ingestion.src.retry import retry

logger = logging.getLogger(__name__)


@retry(max_retries=3, backoff_sec=2.0, backoff_factor=2.0)
def convert_to_parquet(
    df: DataFrame,
    output_path: str,
    mode: str = "overwrite",
    partition_by: list[str] | None = None,
) -> None:
    """Write a DataFrame to Parquet format.

    Parameters
    ----------
    df : DataFrame
        Validated DataFrame to persist.
    output_path : str
        Destination path (local or HDFS).
    mode : str
        Spark write mode (``overwrite``, ``append``, …).
    partition_by : list[str] | None
        Optional partition columns.
    """
    writer = df.write.format("parquet").mode(mode)

    if partition_by:
        writer = writer.partitionBy(*partition_by)

    writer.save(output_path)
    logger.info("Parquet written → %s (mode=%s, partitions=%s)", output_path, mode, partition_by)
