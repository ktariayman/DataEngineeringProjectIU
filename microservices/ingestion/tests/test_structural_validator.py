"""
Unit tests for StructuralValidator.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, LongType

# Add project root to path for direct execution
_project_root = str(Path(__file__).resolve().parents[3])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from microservices.ingestion.src.structural_validator import (
    StructuralValidator,
    ValidationError,
)


@pytest.fixture()
def sample_df(spark: SparkSession):
    """A small DataFrame mimicking KT4 data."""
    data = [
        (1566780382000, "enter", "q100", "main", None, "ios", 0),
        (1566780392000, "respond", "q100", "main", "a", "ios", 10000),
        (1566780400000, "enter", "q200", "recommend", None, "android", 0),
    ]
    schema = StructType([
        StructField("timestamp", LongType()),
        StructField("action_type", StringType()),
        StructField("item_id", StringType()),
        StructField("source", StringType()),
        StructField("user_answer", StringType()),
        StructField("platform", StringType()),
        StructField("elapsed_time", LongType()),
    ])
    return spark.createDataFrame(data, schema)


@pytest.fixture()
def validator():
    return StructuralValidator(
        max_null_ratio=0.05,
        min_row_count=1,
        required_columns={
            "kt4": ["timestamp", "action_type", "item_id"],
        },
    )


class TestRequiredColumns:
    def test_passes_when_columns_present(self, sample_df, validator):
        print("\n[TEST] Structural validation - required columns present")
        print(f"  DataFrame columns: {sample_df.columns}")
        print(f"  Required for kt4: ['timestamp', 'action_type', 'item_id']")
        result = validator.validate(sample_df, "kt4")
        print(f"  Validation passed: {result.count()} rows")
        print(f"  ✓ All required columns present")
        assert result.count() == 3

    def test_fails_when_column_missing(self, spark: SparkSession, validator):
        print("\n[TEST] Structural validation - missing required columns")
        df = spark.createDataFrame(
            [(1,)], schema=StructType([StructField("timestamp", LongType())])
        )
        print(f"  DataFrame columns: {df.columns}")
        print(f"  Required for kt4: ['timestamp', 'action_type', 'item_id']")
        print(f"  Missing: action_type, item_id")
        with pytest.raises(ValidationError, match="Missing required columns"):
            validator.validate(df, "kt4")
        print(f"  ✓ ValidationError raised as expected")


class TestRowCount:
    def test_fails_on_empty(self, spark: SparkSession):
        print("\n[TEST] Structural validation - empty DataFrame")
        v = StructuralValidator(min_row_count=1, required_columns={})
        schema = StructType([StructField("x", StringType())])
        df = spark.createDataFrame([], schema)
        print(f"  Row count: {df.count()}")
        print(f"  Min required: 1")
        with pytest.raises(ValidationError, match="Row count"):
            v.validate(df, "test")
        print(f"  ✓ ValidationError raised for empty DataFrame")


class TestNullRatio:
    def test_fails_on_high_null_ratio(self, spark: SparkSession):
        print("\n[TEST] Structural validation - high null ratio")
        v = StructuralValidator(
            max_null_ratio=0.01,
            min_row_count=1,
            required_columns={"test": ["val"]},
        )
        data = [(None,), ("x",), (None,)]
        schema = StructType([StructField("val", StringType())])
        df = spark.createDataFrame(data, schema)
        print(f"  Data: {data}")
        print(f"  Null ratio: 2/3 = 66.7%")
        print(f"  Max allowed: 1%")
        with pytest.raises(ValidationError, match="null ratio"):
            v.validate(df, "test")
        print(f"  ✓ ValidationError raised for high null ratio")


class TestNormalisation:
    def test_trims_whitespace(self, spark: SparkSession):
        print("\n[TEST] Structural validation - whitespace normalization")
        v = StructuralValidator(required_columns={})
        data = [("  hello  ",), ("  ",), ("world",)]
        schema = StructType([StructField("val", StringType())])
        df = spark.createDataFrame(data, schema)
        print(f"  Original data: {data}")
        result = v.validate(df, "test")
        trimmed = [row['val'] for row in result.collect()]
        print(f"  After normalization: {trimmed}")
        print(f"  ✓ Whitespace trimmed correctly")
        rows = [r["val"] for r in result.collect()]
        assert "hello" in rows
        assert "world" in rows
        # Empty-after-trim should become null
        assert None in rows

    def test_empty_string_becomes_null(self, spark: SparkSession):
        v = StructuralValidator(required_columns={})
        data = [("",)]
        schema = StructType([StructField("val", StringType())])
        df = spark.createDataFrame(data, schema)
        result = v.validate(df, "test")
        assert result.first()["val"] is None
