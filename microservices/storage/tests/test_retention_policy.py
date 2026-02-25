"""Tests for :mod:`microservices.storage.src.retention_policy`.

Covers privacy guarantees:
  - No PII stored / retention policy enforcement
  - Automated identification of expired partitions
  - Configurable retention per zone (raw=365d, curated=180d)
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

_project_root = str(Path(__file__).resolve().parents[3])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from microservices.storage.src.retention_policy import (
    RetentionPolicy,
    extract_partition_date,
    find_expired_partitions,
    generate_deletion_commands,
    get_default_policies,
)


class TestRetentionPolicy:
    """Verify retention policy configuration."""

    def test_default_raw_policy(self) -> None:
        print("\n[TEST] Default raw zone retention = 365 days")
        policies = get_default_policies()
        raw = policies["raw"]
        print(f"  zone_name      = '{raw.zone_name}'")
        print(f"  retention_days = {raw.retention_days}")
        print(f"  enabled        = {raw.enabled}")
        print(f"  cutoff_date    = {raw.cutoff_date}")
        assert raw.retention_days == 365
        assert raw.enabled is True
        print("  ✓ Raw zone: 1-year retention policy")

    def test_default_curated_policy(self) -> None:
        print("\n[TEST] Default curated zone retention = 180 days")
        policies = get_default_policies()
        curated = policies["curated"]
        print(f"  zone_name      = '{curated.zone_name}'")
        print(f"  retention_days = {curated.retention_days}")
        print(f"  cutoff_date    = {curated.cutoff_date}")
        assert curated.retention_days == 180
        assert curated.enabled is True
        print("  ✓ Curated zone: 6-month retention policy")

    def test_cutoff_date_calculation(self) -> None:
        print("\n[TEST] Cutoff date is today minus retention_days")
        policy = RetentionPolicy(zone_name="test", retention_days=30)
        expected = date.today() - timedelta(days=30)
        print(f"  retention_days = {policy.retention_days}")
        print(f"  cutoff_date    = {policy.cutoff_date}")
        print(f"  expected       = {expected}")
        assert policy.cutoff_date == expected
        print("  ✓ Cutoff date computed correctly")


class TestExtractPartitionDate:
    """Verify Hive-style partition date extraction."""

    def test_valid_partition_path(self) -> None:
        print("\n[TEST] Extract date from valid partition path")
        path = "/data/raw/kt4/partitions_by_event_date/event_date=2024-06-15"
        result = extract_partition_date(path)
        print(f"  path   = '{path}'")
        print(f"  result = {result}")
        assert result == date(2024, 6, 15)
        print("  ✓ Date extracted correctly")

    def test_no_date_in_path(self) -> None:
        print("\n[TEST] No date in path returns None")
        path = "/data/raw/content/lectures"
        result = extract_partition_date(path)
        print(f"  path   = '{path}'")
        print(f"  result = {result}")
        assert result is None
        print("  ✓ None returned for non-partitioned path")

    def test_nested_partition_path(self) -> None:
        print("\n[TEST] Extract date from deeply nested path")
        path = "/data/raw/kt4/partitions_by_event_date/event_date=2023-01-01/part-00000.parquet"
        result = extract_partition_date(path)
        print(f"  result = {result}")
        assert result == date(2023, 1, 1)
        print("  ✓ Date extracted from nested path")


class TestFindExpiredPartitions:
    """Verify expired partition detection."""

    def test_find_old_partitions(self) -> None:
        print("\n[TEST] Find partitions older than retention cutoff")
        policy = RetentionPolicy(zone_name="raw", retention_days=30)
        old_date = (date.today() - timedelta(days=60)).isoformat()
        recent_date = (date.today() - timedelta(days=5)).isoformat()
        partitions = [
            f"/data/raw/kt4/partitions_by_event_date/event_date={old_date}",
            f"/data/raw/kt4/partitions_by_event_date/event_date={recent_date}",
        ]
        print(f"  Partitions tested: {len(partitions)}")
        print(f"  Old:    event_date={old_date}")
        print(f"  Recent: event_date={recent_date}")
        expired = find_expired_partitions(partitions, policy)
        print(f"  Expired: {len(expired)}")
        assert len(expired) == 1
        assert old_date in expired[0]
        print("  ✓ Only the old partition is expired")

    def test_no_expired_partitions(self) -> None:
        print("\n[TEST] No expired partitions when all are recent")
        policy = RetentionPolicy(zone_name="raw", retention_days=365)
        recent = (date.today() - timedelta(days=10)).isoformat()
        partitions = [
            f"/data/raw/kt4/partitions_by_event_date/event_date={recent}",
        ]
        expired = find_expired_partitions(partitions, policy)
        print(f"  Expired: {len(expired)}")
        assert len(expired) == 0
        print("  ✓ No partitions expired")

    def test_disabled_policy_returns_empty(self) -> None:
        print("\n[TEST] Disabled policy returns empty list")
        policy = RetentionPolicy(
            zone_name="raw", retention_days=1, enabled=False,
        )
        old_date = (date.today() - timedelta(days=100)).isoformat()
        partitions = [
            f"/data/raw/kt4/partitions_by_event_date/event_date={old_date}",
        ]
        expired = find_expired_partitions(partitions, policy)
        print(f"  policy.enabled = {policy.enabled}")
        print(f"  Expired: {len(expired)}")
        assert len(expired) == 0
        print("  ✓ Disabled policy skips evaluation")

    def test_non_partitioned_paths_skipped(self) -> None:
        print("\n[TEST] Non-partitioned paths are skipped gracefully")
        policy = RetentionPolicy(zone_name="raw", retention_days=1)
        partitions = ["/data/raw/content/lectures", "/data/raw/content/questions"]
        expired = find_expired_partitions(partitions, policy)
        print(f"  Expired: {len(expired)}")
        assert len(expired) == 0
        print("  ✓ Non-date paths silently skipped")


class TestGenerateDeletionCommands:
    """Verify deletion command generation."""

    def test_dry_run_commands(self) -> None:
        print("\n[TEST] Dry run generates commented commands")
        paths = ["/data/raw/kt4/partitions_by_event_date/event_date=2023-01-01"]
        cmds = generate_deletion_commands(paths, dry_run=True)
        print(f"  Commands: {len(cmds)}")
        for c in cmds:
            print(f"    {c}")
        assert len(cmds) == 1
        assert cmds[0].startswith("# DRY RUN:")
        assert "-rm -r -skipTrash" in cmds[0]
        print("  ✓ Dry run → commented command")

    def test_actual_delete_commands(self) -> None:
        print("\n[TEST] Actual delete generates real commands")
        paths = [
            "/data/raw/kt4/partitions_by_event_date/event_date=2023-01-01",
            "/data/raw/kt4/partitions_by_event_date/event_date=2023-01-02",
        ]
        cmds = generate_deletion_commands(paths, dry_run=False)
        print(f"  Commands: {len(cmds)}")
        for c in cmds:
            print(f"    {c}")
        assert len(cmds) == 2
        assert all(not c.startswith("#") for c in cmds)
        assert all("-rm -r -skipTrash" in c for c in cmds)
        print("  ✓ Real commands without dry-run prefix")
