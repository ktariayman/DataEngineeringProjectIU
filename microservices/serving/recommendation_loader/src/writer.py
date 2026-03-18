"""
HDFS-to-PostgreSQL writer.

Reads a Parquet dataset from HDFS and writes it into a PostgreSQL table
using PySpark's JDBC DataFrameWriter (batch mode).
"""

from __future__ import annotations

import logging
from pyspark.sql import DataFrame

logger = logging.getLogger(__name__)


def write_df_to_postgres(
    df: DataFrame,
    jdbc_url: str,
    table: str,
    user: str,
    password: str,
    mode: str = "overwrite",
    batch_size: int = 5000,
) -> None:
    """Write a Spark DataFrame to a PostgreSQL table via JDBC.

    Parameters
    ----------
    df : DataFrame
        Data to write.
    jdbc_url : str
        JDBC connection URL, e.g. ``jdbc:postgresql://host:5432/db``.
    table : str
        Target table name.
    user, password : str
        Database credentials.
    mode : str
        Spark write mode (``overwrite`` | ``append``).
    batch_size : int
        Rows per JDBC batch insert.
    """
    row_count = df.count()
    if row_count == 0:
        logger.warning("[loader] DataFrame for table '%s' is empty – skipping write.", table)
        return

    logger.info("[loader] Writing %d rows to postgres table '%s' (mode=%s).", row_count, table, mode)

    df.write \
        .format("jdbc") \
        .option("url", jdbc_url) \
        .option("dbtable", table) \
        .option("user", user) \
        .option("password", password) \
        .option("driver", "org.postgresql.Driver") \
        .option("batchsize", str(batch_size)) \
        .mode(mode) \
        .save()

    logger.info("[loader] Successfully wrote %d rows to '%s'.", row_count, table)
