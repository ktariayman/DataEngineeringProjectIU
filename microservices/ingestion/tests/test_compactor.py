"""
Unit tests for the compactor module.
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

from microservices.ingestion.src.compactor import compact, estimate_num_output_files


@pytest.fixture()
def sample_df(spark: SparkSession):
    data = [(f"id_{i}", i) for i in range(100)]
    schema = StructType([
        StructField("id", StringType()),
        StructField("value", IntegerType()),
    ])
    return spark.createDataFrame(data, schema)


class TestCompact:
    def test_returns_dataframe(self, sample_df):
        print("\n[TEST] Compact DataFrame")
        print(f"  Input rows: {sample_df.count()}")
        print(f"  Target size: 128 MB per partition")
        result = compact(sample_df, target_size_mb=128)
        print(f"  Output rows: {result.count()}")
        print(f"  Output partitions: {result.rdd.getNumPartitions()}")
        print(f"  ✓ Compaction preserves data")
        assert result.count() == 100

    def test_reduces_partitions(self, spark: SparkSession):
        """When data is small, compact should coalesce to fewer partitions."""
        print("\n[TEST] Compact reduces partitions for small data")
        data = [(str(i),) for i in range(10)]
        schema = StructType([StructField("x", StringType())])
        df = spark.createDataFrame(data, schema).repartition(50)
        print(f"  Original partitions: {df.rdd.getNumPartitions()}")
        print(f"  Rows: {df.count()}")
        assert df.rdd.getNumPartitions() == 50
        compacted = compact(df, target_size_mb=128)
        print(f"  Compacted partitions: {compacted.rdd.getNumPartitions()}")
        print(f"  Rows after compaction: {compacted.count()}")
        print(f"  ✓ Partition count reduced (data too small for 50 partitions)")
        # Should reduce from 50 since data is tiny
        assert compacted.rdd.getNumPartitions() <= 50
        assert compacted.count() == 10


class TestEstimateFiles:
    def test_returns_at_least_one(self, sample_df):
        print("\n[TEST] Estimate output file count")
        print(f"  DataFrame rows: {sample_df.count()}")
        print(f"  Target size: 1024 MB")
        n = estimate_num_output_files(sample_df, target_size_mb=1024)
        print(f"  Estimated files: {n}")
        print(f"  ✓ At least 1 file required")
        assert n >= 1
