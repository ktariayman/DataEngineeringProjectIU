"""
Unit tests for the format_converter module.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, IntegerType

# Add project root to path for direct execution
_project_root = str(Path(__file__).resolve().parents[3])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from microservices.ingestion.src.format_converter import convert_to_parquet


@pytest.fixture()
def sample_df(spark: SparkSession):
    data = [("a", 1), ("b", 2)]
    schema = StructType([
        StructField("name", StringType()),
        StructField("value", IntegerType()),
    ])
    return spark.createDataFrame(data, schema)


class TestConvertToParquet:
    def test_writes_parquet(self, spark: SparkSession, sample_df, tmp_path: Path):
        print("\n[TEST] Convert CSV to Parquet")
        out = str(tmp_path / "output.parquet")
        print(f"  Input rows: {sample_df.count()}")
        print(f"  Output path: {out}")
        convert_to_parquet(sample_df, out)
        loaded = spark.read.parquet(out)
        print(f"  Loaded rows: {loaded.count()}")
        print(f"  ✓ Parquet written and verified")
        assert loaded.count() == 2

    def test_writes_with_partition(self, spark: SparkSession, sample_df, tmp_path: Path):
        print("\n[TEST] Convert with partitioning")
        out = str(tmp_path / "partitioned.parquet")
        print(f"  Partition by: ['name']")
        convert_to_parquet(sample_df, out, partition_by=["name"])
        loaded = spark.read.parquet(out)
        print(f"  Loaded rows: {loaded.count()}")
        print(f"  Columns: {loaded.columns}")
        print(f"  ✓ Partitioned Parquet created")
        assert loaded.count() == 2
        assert "name" in loaded.columns

    def test_append_mode(self, spark: SparkSession, sample_df, tmp_path: Path):
        print("\n[TEST] Append mode writes")
        out = str(tmp_path / "append.parquet")
        print(f"  Write 1: overwrite mode, {sample_df.count()} rows")
        convert_to_parquet(sample_df, out, mode="overwrite")
        print(f"  Write 2: append mode, {sample_df.count()} rows")
        convert_to_parquet(sample_df, out, mode="append")
        loaded = spark.read.parquet(out)
        print(f"  Total rows: {loaded.count()}")
        print(f"  ✓ Append mode works correctly (2 + 2 = 4)")
        assert loaded.count() == 4  # 2 + 2
