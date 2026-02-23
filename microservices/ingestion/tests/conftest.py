"""
Shared PySpark test fixtures for the ingestion microservice.
"""

from __future__ import annotations

import os
import sys

# CRITICAL: Set Python executable paths BEFORE importing pyspark
# This fixes "Python worker failed to connect back" on Windows/Anaconda
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

import pytest
from pyspark.sql import SparkSession


@pytest.fixture(scope="session")
def spark() -> SparkSession:
    """Create a lightweight local SparkSession for testing."""
    session = (
        SparkSession.builder
        .master("local[1]")
        .appName("ingestion-tests")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "1")
        .config("spark.default.parallelism", "1")
        .config("spark.python.worker.reuse", "false")  # Create fresh worker for each task
        .config("spark.executor.heartbeatInterval", "60s")  # Longer heartbeat for slow machines
        .config("spark.network.timeout", "300s")  # Prevent worker timeout
        .config("spark.sql.execution.pyspark.udf.faulthandler.enabled", "true")  # Better crash traces
        .config("spark.python.worker.faulthandler.enabled", "true")  # Better crash traces
        .getOrCreate()
    )
    yield session
    session.stop()
