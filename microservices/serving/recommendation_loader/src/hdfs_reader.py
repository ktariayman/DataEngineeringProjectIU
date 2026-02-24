"""
HDFS Parquet reader for the Recommendation Loader.

Reads precomputed recommendation Parquet files from the HDFS curated zone
and yields rows as plain Python dicts.

Architecture:
  - Reading is separated from writing (Single Responsibility)
  - No DB logic here
  - Reads at most `max_rows` rows to prevent OOM on unexpected data growth
"""

from __future__ import annotations

import logging
import os
from datetime import date
from typing import Iterator, Optional

import pyarrow as pa
import pyarrow.fs as pafs

logger = logging.getLogger(__name__)

_DEFAULT_HDFS_PATH = "hdfs://namenode:9000/data/curated/recommendations_batch"


def _get_hdfs_path() -> str:
    base = os.environ.get("HDFS_URL", "hdfs://namenode:9000").rstrip("/")
    return f"{base}/data/curated/recommendations_batch"


def read_recommendations(
    generation_date: Optional[date] = None,
    max_rows: int = 10_000_000,
) -> Iterator[dict]:
    """
    Read recommendation rows from HDFS curated zone.

    Parameters
    ----------
    generation_date : date | None
        If provided, reads only the partition for that date.
        If None, reads the full latest partition.
    max_rows : int
        Safety cap — raises if row count exceeds this.

    Yields
    ------
    dict with keys: user_id, recommended_user_id, similarity_score, generation_date
    """
    hdfs_path = _get_hdfs_path()

    if generation_date is not None:
        # Partition path convention: generation_date=YYYY-MM-DD/
        partition_path = f"{hdfs_path}/generation_date={generation_date.isoformat()}"
    else:
        partition_path = hdfs_path

    logger.info("Reading Parquet from HDFS path: %s", partition_path)

    # Parse scheme and host from path (hdfs://namenode:9000/...)
    # pyarrow.fs.HadoopFileSystem needs host + port separately
    scheme, rest = partition_path.split("://", 1)
    host_port, path = rest.split("/", 1)
    if ":" in host_port:
        host, port_str = host_port.split(":", 1)
        port = int(port_str)
    else:
        host = host_port
        port = 9000

    hdfs = pafs.HadoopFileSystem(host=host, port=port)
    dataset = pa.dataset.dataset(f"/{path}", filesystem=hdfs, format="parquet")

    total = 0
    for batch in dataset.to_batches(batch_size=10_000):
        df = batch.to_pydict()
        rows_in_batch = len(df["user_id"])
        total += rows_in_batch
        if total > max_rows:
            raise RuntimeError(
                f"Row count {total} exceeded max_rows={max_rows}. "
                "Possible data explosion — aborting."
            )
        for i in range(rows_in_batch):
            yield {
                "user_id": df["user_id"][i],
                "recommended_user_id": df["recommended_user_id"][i],
                "similarity_score": float(df["similarity_score"][i]),
                "generation_date": df["generation_date"][i],
            }

    logger.info("Read %d rows from HDFS.", total)
