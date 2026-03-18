"""
Shared pytest fixtures for the processing microservice test suite.

Provides a lightweight local SparkSession and reusable test DataFrames
that mirror the EdNet raw-zone schemas.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# CRITICAL: Set Python executable paths BEFORE importing pyspark.
# This fixes "Python worker failed to connect back" on Windows/Anaconda.
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable
os.environ["PYARROW_IGNORE_TIMEZONE"] = "1"

import pandas as pd
import pytest
from pyspark.sql import SparkSession
from pyspark.sql.types import (
    DoubleType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
)

try:
    import pyarrow  # noqa: F401
    HAS_PYARROW = True
except Exception:  # pragma: no cover - environment dependent
    HAS_PYARROW = False

def _looks_like_recycle_bin_path(path: Path) -> bool:
    norm = str(path).lower().replace("\\", "/")
    return any(
        marker in norm for marker in (
            "/.local/share/trash/files/",  # Linux
            "/.trash/",                    # macOS
            "/$recycle.bin/",              # Windows
        )
    )


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if _looks_like_recycle_bin_path(PROJECT_ROOT):
    raise RuntimeError(
        "Tests are running from a Trash/Recycle Bin copy of the project. "
        "Use the real workspace path under "
        "'.../Documents/DataEngineeringProject/DataEngineeringProjectIU/"
        "microservices/processing'."
    )

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ══════════════════════════════════════════════════════════════════════════
# Spark session (shared across all tests in the session)
# ══════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def spark() -> SparkSession:
    """Create a lightweight local SparkSession for testing.

    Uses Apache Arrow for Python ↔ JVM data transfer and monkey-patches
    ``createDataFrame`` so that plain Python lists are routed through
    pandas + Arrow instead of a PythonRDD.  This avoids spawning a
    Python worker subprocess, which crashes on Windows / Anaconda with
    ``Python worker exited unexpectedly (crashed)``.
    """
    session = (
        SparkSession.builder
        .master("local[1]")
        .appName("processing-tests")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "1")
        .config("spark.default.parallelism", "1")
        .config("spark.pyspark.python", sys.executable)
        .config("spark.pyspark.driver.python", sys.executable)
        .config("spark.python.worker.reuse", "true")
        .config("spark.python.worker.timeout", "120")
        .config("spark.executor.heartbeatInterval", "60s")
        .config("spark.network.timeout", "300s")
        # ── Arrow serialisation (bypasses PythonRDD worker) ──────────
        .config(
            "spark.sql.execution.arrow.pyspark.enabled",
            "true" if HAS_PYARROW else "false",
        )
        .config("spark.sql.execution.arrow.pyspark.fallback.enabled", "true")
        .getOrCreate()
    )

    # ── Monkey-patch createDataFrame ─────────────────────────────────
    # spark.createDataFrame(python_list, schema) internally builds a
    # PythonRDD whose deserialisation requires a Python worker sub-
    # process.  On Windows/Anaconda that subprocess crashes (EOFException).
    # By converting the Python list to a pandas DataFrame first and then
    # calling the original method, PySpark takes the Arrow fast-path
    # which creates a JVM-side LocalRelation — no worker needed.
    _orig_create = session.createDataFrame

    def _create_via_arrow(data, schema=None, samplingRatio=None, verifySchema=True):
        # Without pyarrow, pandas conversion can coerce nullable integer
        # values to float NaN and break explicit integral schemas.
        if not HAS_PYARROW:
            return _orig_create(
                data, schema=schema,
                samplingRatio=samplingRatio, verifySchema=verifySchema,
            )

        if isinstance(data, (list, tuple)):
            # Determine column names from schema
            if isinstance(schema, StructType):
                col_names = [f.name for f in schema.fields]
            elif isinstance(schema, (list, tuple)):
                col_names = list(schema)
            else:
                return _orig_create(
                    data, schema=schema,
                    samplingRatio=samplingRatio, verifySchema=verifySchema,
                )

            # Build a pandas DataFrame (Arrow-friendly)
            if data:
                pdf = pd.DataFrame(list(data), columns=col_names)
            else:
                # Empty DF — bypass Arrow/pandas entirely.
                # Use emptyRDD() which is purely JVM-side (0 partitions,
                # no Python worker needed).
                if isinstance(schema, StructType):
                    return _orig_create(
                        session.sparkContext.emptyRDD(),
                        schema=schema,
                    )
                pdf = pd.DataFrame(columns=col_names)

            if isinstance(schema, StructType):
                return _orig_create(
                    pdf, schema=schema,
                    samplingRatio=samplingRatio, verifySchema=verifySchema,
                )
            return _orig_create(
                pdf, samplingRatio=samplingRatio, verifySchema=verifySchema,
            )

        # pandas / RDD / other — pass through unchanged
        return _orig_create(
            data, schema=schema,
            samplingRatio=samplingRatio, verifySchema=verifySchema,
        )

    session.createDataFrame = _create_via_arrow

    yield session
    session.stop()


# ══════════════════════════════════════════════════════════════════════════
# Test data fixtures
# ══════════════════════════════════════════════════════════════════════════

@pytest.fixture()
def sample_kt4(spark):
    """KT4 interactions for 3 students (u001, u002, u003)."""
    data = [
        # user_id, timestamp, action_type, item_id, source, user_answer, platform, elapsed_time, event_date
        ("u001", 1609459200000, "respond", "q001", "diagnosis", "a", "mobile", 15000, "2021-01-01"),
        ("u001", 1609459260000, "respond", "q002", "diagnosis", "b", "mobile", 20000, "2021-01-01"),
        ("u001", 1609459320000, "respond", "q003", "diagnosis", "c", "mobile", 25000, "2021-01-01"),
        ("u001", 1609545600000, "enter",   "l001", "recommend", None, "mobile", 60000, "2021-01-02"),
        ("u001", 1609545660000, "respond", "q004", "after_lecture", "a", "mobile", 18000, "2021-01-02"),
        ("u001", 1609632000000, "respond", "q001", "review", "a", "web", 12000, "2021-01-03"),
        ("u002", 1609459200000, "respond", "q001", "diagnosis", "b", "web", 30000, "2021-01-01"),
        ("u002", 1609459260000, "respond", "q002", "diagnosis", "a", "web", 40000, "2021-01-01"),
        ("u002", 1609545600000, "enter",   "l001", "recommend", None, "web", 90000, "2021-01-02"),
        ("u002", 1609545660000, "enter",   "l002", "recommend", None, "web", 45000, "2021-01-02"),
        ("u002", 1609632000000, "respond", "q003", "review", "a", "web", 22000, "2021-01-03"),
        ("u003", 1609459200000, "respond", "q001", "diagnosis", "a", "mobile", 10000, "2021-01-01"),
        ("u003", 1609459260000, "respond", "q002", "diagnosis", "a", "mobile", 8000,  "2021-01-01"),
        ("u003", 1609459320000, "respond", "q003", "diagnosis", "b", "mobile", 12000, "2021-01-01"),
        ("u003", 1609459380000, "respond", "q004", "diagnosis", "b", "mobile", 9000,  "2021-01-01"),
        ("u003", 1609545600000, "enter",   "l001", "recommend", None, "mobile", 30000, "2021-01-02"),
        ("u003", 1609545660000, "respond", "q001", "review", "a", "mobile", 7000,  "2021-01-02"),
    ]
    schema = StructType([
        StructField("user_id", StringType(), False),
        StructField("timestamp", LongType(), False),
        StructField("action_type", StringType(), False),
        StructField("item_id", StringType(), False),
        StructField("source", StringType(), True),
        StructField("user_answer", StringType(), True),
        StructField("platform", StringType(), True),
        StructField("elapsed_time", LongType(), True),
        StructField("event_date", StringType(), True),
    ])
    return spark.createDataFrame(data, schema)


@pytest.fixture()
def sample_questions(spark):
    """Questions metadata for q001–q004."""
    data = [
        ("q001", "b001", "e001", "a", 1, "tag1"),
        ("q002", "b001", "e002", "a", 2, "tag2"),
        ("q003", "b002", "e003", "b", 3, "tag1;tag3"),
        ("q004", "b002", "e004", "b", 4, "tag2;tag4"),
    ]
    schema = StructType([
        StructField("question_id", StringType(), False),
        StructField("bundle_id", StringType(), True),
        StructField("explanation_id", StringType(), True),
        StructField("correct_answer", StringType(), True),
        StructField("part", IntegerType(), True),
        StructField("tags", StringType(), True),
    ])
    return spark.createDataFrame(data, schema)


@pytest.fixture()
def sample_lectures(spark):
    """Lectures metadata for l001–l002."""
    data = [
        ("l001", "tag1;tag2", 1),
        ("l002", "tag3", 2),
    ]
    schema = StructType([
        StructField("lecture_id", StringType(), False),
        StructField("tags", StringType(), True),
        StructField("part", IntegerType(), True),
    ])
    return spark.createDataFrame(data, schema)


@pytest.fixture()
def sample_config(tmp_path):
    """Return the path to a minimal processing config YAML."""
    import yaml

    cfg = {
        "spark": {
            "app_name": "processing-test",
            "config": {},
        },
        "sources": {
            "kt4": {"path": "/tmp/test/raw/kt4", "format": "parquet"},
            "lectures": {"path": "/tmp/test/raw/lectures", "format": "parquet"},
            "questions": {"path": "/tmp/test/raw/questions", "format": "parquet"},
        },
        "targets": {
            "aggregated_student_features": {
                "path": "/tmp/test/curated/agg",
                "format": "parquet",
                "mode": "overwrite",
            },
            "user_vectors": {
                "path": "/tmp/test/curated/vectors",
                "format": "parquet",
                "mode": "overwrite",
            },
            "recommendations_batch": {
                "path": "/tmp/test/curated/recs",
                "format": "parquet",
                "mode": "overwrite",
            },
        },
        "feature_engineering": {
            "correctness_join": True,
            "time_features": True,
            "response_time_cap_ms": 300000,
        },
        "feature_aggregation": {
            "min_interactions": 3,
        },
        "similarity": {
            "method": "cosine",
            "top_k": 2,
            "feature_columns": [
                "accuracy_rate",
                "avg_response_time_ms",
                "total_interactions",
                "unique_questions_attempted",
                "unique_lectures_viewed",
                "active_days",
            ],
        },
        "processing_window": {"window_days": 7},
        "data_quality": {
            "max_null_ratio": 0.10,
            "min_row_count": 1,
            "required_output_columns": {
                "aggregated_student_features": ["user_id", "total_interactions"],
                "user_vectors": ["user_id"],
                "recommendations_batch": ["user_id", "recommended_user_id"],
            },
        },
        "privacy": {
            "pii_scan_strict": True,
            "enforce_allowlist": False,
            "allowed_output_columns": {},
        },
        "lineage": {
            "enabled": True,
            "pipeline_version": "1.0.0-test",
            "output_dir": str(tmp_path / "lineage"),
        },
        "compaction": {"target_file_size_mb": 128},
    }

    config_file = tmp_path / "processing_config.yaml"
    with open(config_file, "w", encoding="utf-8") as fh:
        yaml.dump(cfg, fh, default_flow_style=False)

    return str(config_file)
