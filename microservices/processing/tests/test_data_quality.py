"""
Tests for the DataQualityValidator.
Covers required-column checks, row-count thresholds, null-ratio limits,
and duplicate detection.
"""

from __future__ import annotations

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import pytest

from src.data_quality import DataQualityError, DataQualityValidator


class TestDataQualityValidator:
    """Validate quality gate logic using Spark DataFrames."""

    # ── Helper ──────────────────────────────────────────────────────────

    def _build_df(self, spark, rows, columns):
        if not rows:
            from pyspark.sql.types import StringType, StructField, StructType
            schema = StructType([StructField(c, StringType(), True) for c in columns])
            return spark.createDataFrame([], schema)
        return spark.createDataFrame(rows, columns)

    # ── Required columns ────────────────────────────────────────────────

    def test_required_columns_pass(self, spark):
        """Validation passes when all required columns are present."""
        print("\n[TEST] test_required_columns_pass")

        df = self._build_df(spark, [("u1", 10)], ["user_id", "total_interactions"])
        validator = DataQualityValidator(
            required_columns={"test": ["user_id", "total_interactions"]},
            max_null_ratio=1.0,
        )
        # Should not raise
        validator.validate(df, dataset_name="test")
        print("  ✓ validation passed with all required columns present")

    def test_required_columns_missing_raises(self, spark):
        """Validation fails when a required column is absent."""
        print("\n[TEST] test_required_columns_missing_raises")

        df = self._build_df(spark, [("u1",)], ["user_id"])
        validator = DataQualityValidator(
            required_columns={"test": ["user_id", "total_interactions"]},
            max_null_ratio=1.0,
        )
        with pytest.raises(DataQualityError, match="total_interactions"):
            validator.validate(df, dataset_name="test")
        print("  ✓ DataQualityError raised for missing column")

    # ── Row count ───────────────────────────────────────────────────────

    def test_row_count_pass(self, spark):
        """Validation passes when row count >= min."""
        print("\n[TEST] test_row_count_pass")

        df = self._build_df(spark, [("u1",), ("u2",)], ["user_id"])
        validator = DataQualityValidator(
            max_null_ratio=1.0,
            min_row_count=2,
        )
        validator.validate(df, dataset_name="test")
        print("  ✓ validation passed with sufficient rows")

    def test_row_count_too_low_raises(self, spark):
        """Validation fails when dataset is empty or below threshold."""
        print("\n[TEST] test_row_count_too_low_raises")

        df = self._build_df(spark, [], ["user_id"])
        validator = DataQualityValidator(
            max_null_ratio=1.0,
            min_row_count=1,
        )
        with pytest.raises(DataQualityError, match="[Rr]ow"):
            validator.validate(df, dataset_name="test")
        print("  ✓ DataQualityError raised for 0 rows")

    # ── Null ratio ──────────────────────────────────────────────────────

    def test_null_ratio_within_limit(self, spark):
        """Validation passes when null ratio is under the threshold."""
        print("\n[TEST] test_null_ratio_within_limit")

        data = [("u1", 10), ("u2", 20), ("u3", None)]
        df = self._build_df(spark, data, ["user_id", "score"])
        validator = DataQualityValidator(
            required_columns={"test": ["user_id", "score"]},
            max_null_ratio=0.40,  # 1/3 ≈ 0.33 < 0.40
        )
        validator.validate(df, dataset_name="test")
        print("  ✓ validation passed with null ratio 0.33 < 0.40")

    def test_null_ratio_exceeded_raises(self, spark):
        """Validation fails when null ratio exceeds the threshold."""
        print("\n[TEST] test_null_ratio_exceeded_raises")

        from pyspark.sql.types import LongType, StringType, StructField, StructType

        schema = StructType([
            StructField("user_id", StringType(), True),
            StructField("score", LongType(), True),
        ])
        data = [("u1", None), ("u2", None), ("u3", 10)]
        df = spark.createDataFrame(data, schema=schema)
        validator = DataQualityValidator(
            required_columns={"test": ["user_id", "score"]},
            max_null_ratio=0.50,  # 2/3 ≈ 0.67 > 0.50
        )
        with pytest.raises(DataQualityError, match="[Nn]ull"):
            validator.validate(df, dataset_name="test")
        print("  ✓ DataQualityError raised for null ratio 0.67 > 0.50")

    # ── Duplicates ──────────────────────────────────────────────────────

    def test_duplicate_detection(self, spark):
        """Validator should detect duplicate primary key values."""
        print("\n[TEST] test_duplicate_detection")

        data = [("u1", 10), ("u1", 20), ("u2", 30)]
        df = self._build_df(spark, data, ["user_id", "score"])
        validator = DataQualityValidator(
            max_null_ratio=1.0,
        )
        with pytest.raises(DataQualityError, match="[Dd]uplic"):
            validator.validate(df, dataset_name="test", primary_key="user_id")
        print("  ✓ DataQualityError raised for duplicate primary key")

    def test_no_duplicates_passes(self, spark):
        """When there are no duplicates, validation should succeed."""
        print("\n[TEST] test_no_duplicates_passes")

        data = [("u1", 10), ("u2", 20)]
        df = self._build_df(spark, data, ["user_id", "score"])
        validator = DataQualityValidator(
            max_null_ratio=1.0,
        )
        validator.validate(df, dataset_name="test", primary_key="user_id")
        print("  ✓ validation passed with no duplicate primary keys")
