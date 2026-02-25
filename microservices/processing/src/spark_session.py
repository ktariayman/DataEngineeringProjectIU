"""
Spark session factory for the processing microservice.

Scalability: configures AQE, dynamic allocation, and Kryo serialisation
via the processing_config.yaml ``spark`` section.
"""

from __future__ import annotations

from pyspark.sql import SparkSession


def get_spark_session(
    app_name: str = "ednet-processing",
    master: str | None = None,
    extra_config: dict[str, str] | None = None,
) -> SparkSession:
    """Build (or retrieve) a configured SparkSession.

    Parameters
    ----------
    app_name : str
        Application name shown in the Spark UI.
    master : str | None
        Spark master URL.  ``None`` → use SPARK_MASTER_URL env or defaults.
    extra_config : dict[str, str] | None
        Arbitrary Spark configuration key-value pairs.
    """
    builder = SparkSession.builder.appName(app_name)

    if master:
        builder = builder.master(master)

    for key, value in (extra_config or {}).items():
        builder = builder.config(key, value)

    return builder.getOrCreate()
