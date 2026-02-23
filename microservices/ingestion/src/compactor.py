"""
Compaction utilities – merge small Parquet files into larger ones.

Architecture diagram spec:
  - Merge small files
  - Target file size: ~128–512 MB
  - Runs per event_date partition (daily incremental files)
"""

from __future__ import annotations

import logging
import math

from pyspark.sql import DataFrame, SparkSession

logger = logging.getLogger(__name__)

# Default Spark Parquet block size used for estimation (128 MB)
_DEFAULT_TARGET_SIZE_MB = 128


def estimate_num_output_files(
    df: DataFrame,
    target_size_mb: int = _DEFAULT_TARGET_SIZE_MB,
) -> int:
    """Heuristically estimate how many output files we need so each file is
    approximately *target_size_mb*.

    The estimation relies on ``SizeEstimator`` being unavailable from Python,
    so we use the logical plan's size-in-bytes hint when available, falling
    back to a partition-count-based heuristic.
    """
    try:
        # Spark's Catalyst sometimes exposes a size estimate
        size_bytes = df.queryExecution().optimizedPlan().stats().sizeInBytes()
        size_mb = size_bytes / (1024 * 1024)
        n_files = max(1, math.ceil(size_mb / target_size_mb))
        logger.info(
            "Estimated data size: %.1f MB → %d output file(s) (target %d MB)",
            size_mb, n_files, target_size_mb,
        )
        return n_files
    except Exception:
        # Fallback: keep current partition count but cap at a sane minimum
        n_partitions = df.rdd.getNumPartitions()
        n_files = max(1, n_partitions)
        logger.info(
            "Size estimation unavailable; using partition count %d as file count.",
            n_files,
        )
        return n_files


def compact(
    df: DataFrame,
    target_size_mb: int = _DEFAULT_TARGET_SIZE_MB,
) -> DataFrame:
    """Repartition a DataFrame so the resulting Parquet write produces files
    of approximately *target_size_mb* each.

    Parameters
    ----------
    df : DataFrame
        Input DataFrame (typically already partitioned by ``event_date``).
    target_size_mb : int
        Desired output file size in megabytes.

    Returns
    -------
    DataFrame
        Coalesced / repartitioned DataFrame ready for writing.
    """
    n_files = estimate_num_output_files(df, target_size_mb)
    current_partitions = df.rdd.getNumPartitions()

    if n_files < current_partitions:
        # coalesce avoids a full shuffle when reducing partitions
        logger.info("Coalescing from %d → %d partitions.", current_partitions, n_files)
        return df.coalesce(n_files)
    elif n_files > current_partitions:
        logger.info("Repartitioning from %d → %d partitions.", current_partitions, n_files)
        return df.repartition(n_files)
    else:
        logger.info("Partition count already optimal (%d).", current_partitions)
        return df


def compact_parquet_path(
    spark: SparkSession,
    path: str,
    target_size_mb: int = _DEFAULT_TARGET_SIZE_MB,
    partition_by: list[str] | None = None,
) -> None:
    """Read existing Parquet at *path*, compact, and overwrite in-place.

    Useful for a scheduled compaction job that runs after incremental appends.
    """
    logger.info("Compacting Parquet at: %s", path)
    df = spark.read.parquet(path)
    df = compact(df, target_size_mb)

    writer = df.write.format("parquet").mode("overwrite")
    if partition_by:
        writer = writer.partitionBy(*partition_by)
    writer.save(path)
    logger.info("Compaction complete for: %s", path)
