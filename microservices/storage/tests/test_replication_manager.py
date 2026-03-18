"""Tests for :mod:`microservices.storage.src.replication_manager`.

Covers reliability guarantees:
  - Replication factor = 3 enforcement
  - Automated failover / no SPOF detection
  - Failure isolation via health assessment
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_project_root = str(Path(__file__).resolve().parents[3])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from microservices.storage.src.replication_manager import (
    ClusterHealth,
    ReplicationStatus,
    assess_cluster_health,
    parse_jmx_replication_metrics,
    validate_replication_factor,
)


class TestReplicationStatus:
    """Verify ReplicationStatus properties."""

    def test_fully_replicated(self) -> None:
        print("\n[TEST] Fully replicated cluster (3 DataNodes, replication=3)")
        status = ReplicationStatus(target_replication=3, live_datanodes=3)
        print(f"  effective_replication = {status.effective_replication}")
        print(f"  is_fully_replicated  = {status.is_fully_replicated}")
        print(f"  replication_ratio    = {status.replication_ratio:.2f}")
        assert status.effective_replication == 3
        assert status.is_fully_replicated is True
        assert status.replication_ratio == 1.0
        print("  ✓ Full replication with 3 nodes")

    def test_degraded_replication(self) -> None:
        print("\n[TEST] Degraded cluster (2 DataNodes, replication=3)")
        status = ReplicationStatus(target_replication=3, live_datanodes=2)
        print(f"  effective_replication = {status.effective_replication}")
        print(f"  is_fully_replicated  = {status.is_fully_replicated}")
        print(f"  replication_ratio    = {status.replication_ratio:.2f}")
        assert status.effective_replication == 2
        assert status.is_fully_replicated is False
        assert abs(status.replication_ratio - 0.6667) < 0.01
        print("  ✓ Degraded: can only replicate 2 of 3")

    def test_zero_datanodes(self) -> None:
        print("\n[TEST] Zero DataNodes")
        status = ReplicationStatus(target_replication=3, live_datanodes=0)
        print(f"  effective_replication = {status.effective_replication}")
        print(f"  replication_ratio    = {status.replication_ratio:.2f}")
        assert status.effective_replication == 0
        assert status.replication_ratio == 0.0
        print("  ✓ Zero nodes → zero effective replication")


class TestAssessClusterHealth:
    """Verify cluster health assessment logic."""

    def test_healthy_cluster(self) -> None:
        print("\n[TEST] Healthy cluster: 3 DataNodes, no issues")
        status = assess_cluster_health(
            live_datanodes=3, target_replication=3,
        )
        print(f"  health = {status.health.value}")
        assert status.health == ClusterHealth.HEALTHY
        print("  ✓ 3/3 DataNodes → HEALTHY")

    def test_degraded_cluster(self) -> None:
        print("\n[TEST] Degraded cluster: 2 of 3 DataNodes")
        status = assess_cluster_health(
            live_datanodes=2, target_replication=3,
        )
        print(f"  health = {status.health.value}")
        assert status.health == ClusterHealth.DEGRADED
        print("  ✓ 2/3 DataNodes → DEGRADED")

    def test_critical_missing_blocks(self) -> None:
        print("\n[TEST] Critical cluster: missing blocks detected")
        status = assess_cluster_health(
            live_datanodes=3, target_replication=3,
            missing_blocks=5,
        )
        print(f"  health         = {status.health.value}")
        print(f"  missing_blocks = {status.missing_blocks}")
        assert status.health == ClusterHealth.CRITICAL
        print("  ✓ Missing blocks → CRITICAL")

    def test_critical_corrupt_blocks(self) -> None:
        print("\n[TEST] Critical cluster: corrupt blocks detected")
        status = assess_cluster_health(
            live_datanodes=3, target_replication=3,
            corrupt_blocks=2,
        )
        print(f"  health         = {status.health.value}")
        print(f"  corrupt_blocks = {status.corrupt_blocks}")
        assert status.health == ClusterHealth.CRITICAL
        print("  ✓ Corrupt blocks → CRITICAL")

    def test_unavailable_cluster(self) -> None:
        print("\n[TEST] Unavailable cluster: 0 DataNodes")
        status = assess_cluster_health(
            live_datanodes=0, target_replication=3,
        )
        print(f"  health = {status.health.value}")
        assert status.health == ClusterHealth.UNAVAILABLE
        print("  ✓ 0 DataNodes → UNAVAILABLE")

    def test_under_replicated_is_degraded(self) -> None:
        print("\n[TEST] Under-replicated blocks → DEGRADED")
        status = assess_cluster_health(
            live_datanodes=3, target_replication=3,
            under_replicated_blocks=10,
        )
        print(f"  health                  = {status.health.value}")
        print(f"  under_replicated_blocks = {status.under_replicated_blocks}")
        assert status.health == ClusterHealth.DEGRADED
        print("  ✓ Under-replicated blocks → DEGRADED")


class TestValidateReplicationFactor:
    """Verify replication factor validation."""

    def test_valid_replication(self) -> None:
        print("\n[TEST] Replication=3 with 3 DataNodes → valid")
        valid, msg = validate_replication_factor(3, 3)
        print(f"  valid = {valid}")
        print(f"  msg   = '{msg}'")
        assert valid is True
        print("  ✓ Replication factor achievable")

    def test_exceeds_live_nodes(self) -> None:
        print("\n[TEST] Replication=3 with 1 DataNode → invalid")
        valid, msg = validate_replication_factor(3, 1)
        print(f"  valid = {valid}")
        print(f"  msg   = '{msg}'")
        assert valid is False
        assert "exceeds" in msg.lower()
        print("  ✓ Cannot replicate to more nodes than available")

    def test_zero_replication_invalid(self) -> None:
        print("\n[TEST] Replication=0 → invalid")
        valid, msg = validate_replication_factor(0, 3)
        print(f"  valid = {valid}")
        assert valid is False
        print("  ✓ Replication factor must be >= 1")


class TestParseJMXMetrics:
    """Verify JMX metrics parsing."""

    def test_parse_full_jmx_response(self) -> None:
        print("\n[TEST] Parse complete JMX replication metrics")
        jmx_data = {
            "beans": [{
                "NumLiveDataNodes": 3,
                "UnderReplicatedBlocks": 5,
                "MissingBlocks": 0,
                "CorruptBlocks": 0,
                "BlocksTotal": 1200,
            }]
        }
        result = parse_jmx_replication_metrics(jmx_data)
        print(f"  live_datanodes          = {result['live_datanodes']}")
        print(f"  under_replicated_blocks = {result['under_replicated_blocks']}")
        print(f"  missing_blocks          = {result['missing_blocks']}")
        print(f"  corrupt_blocks          = {result['corrupt_blocks']}")
        print(f"  total_blocks            = {result['total_blocks']}")
        assert result["live_datanodes"] == 3
        assert result["under_replicated_blocks"] == 5
        assert result["missing_blocks"] == 0
        assert result["total_blocks"] == 1200
        print("  ✓ All JMX replication metrics parsed correctly")

    def test_parse_empty_jmx(self) -> None:
        print("\n[TEST] Parse empty JMX response returns zeros")
        result = parse_jmx_replication_metrics({"beans": []})
        print(f"  All values: {result}")
        assert all(v == 0 for v in result.values())
        print("  ✓ Empty JMX → all zeros (safe default)")
