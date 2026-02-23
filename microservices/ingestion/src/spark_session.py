"""
Spark session factory for the ingestion microservice.
"""

from __future__ import annotations

from pyspark.sql import SparkSession


def get_spark_session(
    app_name: str = "ednet-ingestion",
    master: str | None = None,
    extra_config: dict[str, str] | None = None,
) -> SparkSession:
    """Build (or retrieve) a configured SparkSession.

    Parameters
    ----------
    app_name : str
        Spark application name.
    master : str | None
        Spark master URL.  ``None`` lets spark-submit / cluster decide.
    extra_config : dict | None
        Additional Spark configuration key-value pairs.

    Returns
    -------
    SparkSession
    """
    builder = SparkSession.builder.appName(app_name)

    if master:
        builder = builder.master(master)

    for key, value in (extra_config or {}).items():
        builder = builder.config(key, value)

    return builder.getOrCreate()
