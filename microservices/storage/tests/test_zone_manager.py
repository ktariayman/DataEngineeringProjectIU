"""Tests for :mod:`microservices.storage.src.zone_manager`.

Covers governance guarantees:
  - Raw vs Curated zone separation
  - Immutable raw zone enforcement
  - Structured folder hierarchy
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_project_root = str(Path(__file__).resolve().parents[3])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from microservices.storage.src.zone_manager import (
    DatasetDefinition,
    ImmutableZoneViolationError,
    ZoneDefinition,
    ZoneType,
    generate_init_commands,
    get_all_zone_paths,
    get_default_zones,
    validate_write_mode,
)


class TestZoneTypes:
    """Verify zone type enum values."""

    def test_raw_zone_type(self) -> None:
        print("\n[TEST] ZoneType.RAW has correct value")
        print(f"  ZoneType.RAW = '{ZoneType.RAW.value}'")
        assert ZoneType.RAW.value == "raw"
        print("  ✓ Raw zone type value is 'raw'")

    def test_curated_zone_type(self) -> None:
        print("\n[TEST] ZoneType.CURATED has correct value")
        print(f"  ZoneType.CURATED = '{ZoneType.CURATED.value}'")
        assert ZoneType.CURATED.value == "curated"
        print("  ✓ Curated zone type value is 'curated'")


class TestDefaultZones:
    """Verify the canonical zone layout from the architecture diagram."""

    def test_two_zones_defined(self) -> None:
        print("\n[TEST] Exactly two zones are defined (raw + curated)")
        zones = get_default_zones()
        print(f"  Zone keys: {list(zones.keys())}")
        assert len(zones) == 2
        assert ZoneType.RAW in zones
        assert ZoneType.CURATED in zones
        print("  ✓ Both raw and curated zones present")

    def test_raw_zone_is_immutable(self) -> None:
        print("\n[TEST] Raw zone is marked immutable")
        zones = get_default_zones()
        raw = zones[ZoneType.RAW]
        print(f"  raw.immutable = {raw.immutable}")
        print(f"  raw.base_path = '{raw.base_path}'")
        assert raw.immutable is True
        assert raw.base_path == "/data/raw"
        print("  ✓ Raw zone is immutable at /data/raw")

    def test_curated_zone_is_mutable(self) -> None:
        print("\n[TEST] Curated zone is NOT immutable")
        zones = get_default_zones()
        curated = zones[ZoneType.CURATED]
        print(f"  curated.immutable = {curated.immutable}")
        print(f"  curated.base_path = '{curated.base_path}'")
        assert curated.immutable is False
        assert curated.base_path == "/data/curated"
        print("  ✓ Curated zone allows updates at /data/curated")

    def test_raw_zone_has_kt4_lectures_questions(self) -> None:
        print("\n[TEST] Raw zone contains kt4, lectures, questions datasets")
        zones = get_default_zones()
        raw = zones[ZoneType.RAW]
        ds_names = sorted(raw.datasets.keys())
        print(f"  Raw datasets: {ds_names}")
        assert "kt4" in raw.datasets
        assert "lectures" in raw.datasets
        assert "questions" in raw.datasets
        print("  ✓ All 3 raw datasets registered")

    def test_kt4_partitioned_by_event_date(self) -> None:
        print("\n[TEST] KT4 dataset is partitioned by event_date")
        zones = get_default_zones()
        kt4 = zones[ZoneType.RAW].datasets["kt4"]
        print(f"  kt4.partition_by = {kt4.partition_by}")
        print(f"  kt4.write_mode  = '{kt4.write_mode}'")
        print(f"  kt4.path        = '{kt4.path}'")
        assert kt4.partition_by == ("event_date",)
        assert kt4.write_mode == "append"
        print("  ✓ KT4 partitioned by event_date, mode=append")

    def test_curated_zone_has_three_datasets(self) -> None:
        print("\n[TEST] Curated zone contains 3 datasets")
        zones = get_default_zones()
        curated = zones[ZoneType.CURATED]
        ds_names = sorted(curated.datasets.keys())
        print(f"  Curated datasets: {ds_names}")
        assert "aggregated_student_features" in curated.datasets
        assert "user_vectors" in curated.datasets
        assert "recommendations_batch" in curated.datasets
        print("  ✓ All 3 curated datasets registered")


class TestImmutabilityEnforcement:
    """Verify that zone immutability rules are enforced."""

    def test_append_to_raw_kt4_allowed(self) -> None:
        print("\n[TEST] Append to raw/kt4 is ALLOWED (matches dataset config)")
        zones = get_default_zones()
        raw = zones[ZoneType.RAW]
        validate_write_mode(raw, "kt4", "append")
        print("  ✓ No exception raised for append on kt4")

    def test_overwrite_raw_kt4_blocked(self) -> None:
        print("\n[TEST] Overwrite on raw/kt4 is BLOCKED (kt4 is append-only)")
        zones = get_default_zones()
        raw = zones[ZoneType.RAW]
        with pytest.raises(ImmutableZoneViolationError, match="write_mode='append'"):
            validate_write_mode(raw, "kt4", "overwrite")
        print("  ✓ ImmutableZoneViolationError raised for overwrite on kt4")

    def test_unregistered_dataset_blocked(self) -> None:
        print("\n[TEST] Write to unregistered dataset in raw zone is BLOCKED")
        zones = get_default_zones()
        raw = zones[ZoneType.RAW]
        with pytest.raises(ImmutableZoneViolationError, match="not registered"):
            validate_write_mode(raw, "unknown_table", "append")
        print("  ✓ ImmutableZoneViolationError raised for unregistered dataset")

    def test_curated_zone_allows_any_mode(self) -> None:
        print("\n[TEST] Curated zone allows any write mode")
        zones = get_default_zones()
        curated = zones[ZoneType.CURATED]
        # Curated zone is not immutable, so any mode is accepted
        validate_write_mode(curated, "user_vectors", "overwrite")
        validate_write_mode(curated, "user_vectors", "append")
        print("  ✓ Both append and overwrite allowed in curated zone")


class TestZonePathCollector:
    """Verify all HDFS paths are collected correctly."""

    def test_all_zone_paths_returned(self) -> None:
        print("\n[TEST] All zone paths are collected from default zones")
        paths = get_all_zone_paths()
        print(f"  Total paths: {len(paths)}")
        for p in paths:
            print(f"    {p}")
        # 2 base paths + 3 raw datasets + 3 curated datasets = 8
        assert len(paths) >= 8
        assert "/data/raw" in paths
        assert "/data/curated" in paths
        assert "/data/raw/kt4/partitions_by_event_date" in paths
        assert "/data/curated/user_vectors" in paths
        print("  ✓ All expected zone paths present")

    def test_paths_are_sorted_and_unique(self) -> None:
        print("\n[TEST] Zone paths are sorted and deduplicated")
        paths = get_all_zone_paths()
        assert paths == sorted(set(paths))
        print(f"  {len(paths)} unique sorted paths")
        print("  ✓ Paths are sorted and unique")


class TestInitCommands:
    """Verify HDFS init commands are generated correctly."""

    def test_generates_mkdir_commands(self) -> None:
        print("\n[TEST] Init commands include mkdir for all paths")
        cmds = generate_init_commands()
        mkdir_cmds = [c for c in cmds if "mkdir" in c]
        print(f"  mkdir commands: {len(mkdir_cmds)}")
        for c in mkdir_cmds:
            print(f"    {c}")
        assert len(mkdir_cmds) >= 8
        assert all("-p" in c for c in mkdir_cmds)
        print("  ✓ All mkdir commands use -p (idempotent)")

    def test_generates_chmod_commands(self) -> None:
        print("\n[TEST] Init commands include chmod for RBAC")
        cmds = generate_init_commands()
        chmod_cmds = [c for c in cmds if "chmod" in c]
        print(f"  chmod commands: {len(chmod_cmds)}")
        for c in chmod_cmds:
            print(f"    {c}")
        assert len(chmod_cmds) >= 2
        assert any("755" in c and "/data/raw" in c for c in chmod_cmds)
        assert any("750" in c and "/data/curated" in c for c in chmod_cmds)
        print("  ✓ RBAC permissions: raw=755, curated=750")

    def test_generates_chown_commands(self) -> None:
        print("\n[TEST] Init commands include chown for ownership")
        cmds = generate_init_commands()
        chown_cmds = [c for c in cmds if "chown" in c]
        print(f"  chown commands: {len(chown_cmds)}")
        for c in chown_cmds:
            print(f"    {c}")
        assert len(chown_cmds) >= 2
        assert all("hdfs:hadoop" in c for c in chown_cmds)
        print("  ✓ Ownership set to hdfs:hadoop")
