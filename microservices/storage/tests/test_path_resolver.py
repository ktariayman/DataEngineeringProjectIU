"""Tests for :mod:`microservices.storage.src.path_resolver`.

Covers maintainability guarantees:
  - Single source of truth for all HDFS paths
  - Structured folder hierarchy
  - Zone boundary validation
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

_project_root = str(Path(__file__).resolve().parents[3])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from microservices.storage.src.path_resolver import (
    get_zone_base_path,
    list_all_dataset_paths,
    resolve_curated_path,
    resolve_partition_path,
    resolve_raw_path,
)


class TestResolveRawPath:
    """Verify raw zone path resolution."""

    def test_kt4_path(self) -> None:
        print("\n[TEST] Resolve raw path for kt4")
        path = resolve_raw_path("kt4")
        print(f"  kt4 path: {path}")
        assert path == "hdfs://namenode:9000/data/raw/kt4/partitions_by_event_date"
        print("  ✓ KT4 path matches architecture diagram")

    def test_lectures_path(self) -> None:
        print("\n[TEST] Resolve raw path for lectures")
        path = resolve_raw_path("lectures")
        print(f"  lectures path: {path}")
        assert path == "hdfs://namenode:9000/data/raw/content/lectures"
        print("  ✓ Lectures path correct")

    def test_questions_path(self) -> None:
        print("\n[TEST] Resolve raw path for questions")
        path = resolve_raw_path("questions")
        print(f"  questions path: {path}")
        assert path == "hdfs://namenode:9000/data/raw/content/questions"
        print("  ✓ Questions path correct")

    def test_unknown_dataset_raises(self) -> None:
        print("\n[TEST] Unknown raw dataset raises ValueError")
        with pytest.raises(ValueError, match="Unknown raw dataset"):
            resolve_raw_path("nonexistent")
        print("  ✓ ValueError raised for unknown dataset")

    def test_custom_default_fs(self) -> None:
        print("\n[TEST] Custom default_fs prefix")
        path = resolve_raw_path("kt4", default_fs="hdfs://custom:8020")
        print(f"  Custom path: {path}")
        assert path.startswith("hdfs://custom:8020")
        print("  ✓ Custom filesystem prefix applied")


class TestResolveCuratedPath:
    """Verify curated zone path resolution."""

    def test_aggregated_student_features(self) -> None:
        print("\n[TEST] Resolve curated path for aggregated_student_features")
        path = resolve_curated_path("aggregated_student_features")
        print(f"  path: {path}")
        assert path == "hdfs://namenode:9000/data/curated/aggregated_student_features"
        print("  ✓ Aggregated features path correct")

    def test_user_vectors(self) -> None:
        print("\n[TEST] Resolve curated path for user_vectors")
        path = resolve_curated_path("user_vectors")
        print(f"  path: {path}")
        assert path == "hdfs://namenode:9000/data/curated/user_vectors"
        print("  ✓ User vectors path correct")

    def test_recommendations_batch(self) -> None:
        print("\n[TEST] Resolve curated path for recommendations_batch")
        path = resolve_curated_path("recommendations_batch")
        print(f"  path: {path}")
        assert path == "hdfs://namenode:9000/data/curated/recommendations_batch"
        print("  ✓ Recommendations batch path correct")

    def test_unknown_curated_raises(self) -> None:
        print("\n[TEST] Unknown curated dataset raises ValueError")
        with pytest.raises(ValueError, match="Unknown curated dataset"):
            resolve_curated_path("nonexistent")
        print("  ✓ ValueError raised for unknown curated dataset")


class TestResolvePartitionPath:
    """Verify date-partitioned path resolution."""

    def test_partition_with_date_object(self) -> None:
        print("\n[TEST] Partition path with date object")
        path = resolve_partition_path("kt4", date(2025, 1, 15))
        print(f"  path: {path}")
        assert path.endswith("event_date=2025-01-15")
        print("  ✓ Date object → event_date=YYYY-MM-DD")

    def test_partition_with_string_date(self) -> None:
        print("\n[TEST] Partition path with string date")
        path = resolve_partition_path("kt4", "2024-12-31")
        print(f"  path: {path}")
        assert path.endswith("event_date=2024-12-31")
        print("  ✓ String date → event_date=YYYY-MM-DD")

    def test_invalid_date_format_raises(self) -> None:
        print("\n[TEST] Invalid date format raises ValueError")
        with pytest.raises(ValueError, match="Invalid date format"):
            resolve_partition_path("kt4", "2025/01/15")
        print("  ✓ ValueError raised for bad date format")


class TestZoneBase:
    """Verify zone base path resolution."""

    def test_raw_base(self) -> None:
        print("\n[TEST] Raw zone base path")
        path = get_zone_base_path("raw")
        print(f"  path: {path}")
        assert path == "hdfs://namenode:9000/data/raw"
        print("  ✓ Raw base path correct")

    def test_curated_base(self) -> None:
        print("\n[TEST] Curated zone base path")
        path = get_zone_base_path("curated")
        print(f"  path: {path}")
        assert path == "hdfs://namenode:9000/data/curated"
        print("  ✓ Curated base path correct")

    def test_unknown_zone_raises(self) -> None:
        print("\n[TEST] Unknown zone raises ValueError")
        with pytest.raises(ValueError, match="Unknown zone"):
            get_zone_base_path("staging")
        print("  ✓ ValueError raised for unknown zone")


class TestListAllDatasets:
    """Verify full dataset path listing."""

    def test_lists_all_six_datasets(self) -> None:
        print("\n[TEST] list_all_dataset_paths returns all 6 datasets")
        all_paths = list_all_dataset_paths()
        print(f"  Datasets: {len(all_paths)}")
        for name, path in sorted(all_paths.items()):
            print(f"    {name}: {path}")
        assert len(all_paths) == 6
        assert "kt4" in all_paths
        assert "lectures" in all_paths
        assert "questions" in all_paths
        assert "aggregated_student_features" in all_paths
        assert "user_vectors" in all_paths
        assert "recommendations_batch" in all_paths
        print("  ✓ All 6 datasets listed")
