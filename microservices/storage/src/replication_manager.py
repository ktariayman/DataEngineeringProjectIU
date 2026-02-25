"""
Replication manager for the storage microservice.

Reliability guarantees:
  - **Replication factor = 3**: every data block is stored on 3 DataNodes.
  - **Automated failover / No SPOF**: the cluster tolerates up to 2
    DataNode failures without data loss.
  - **Failure isolation**: block-level replication ensures that a single
    disk or node failure doesn't affect data availability.

This module provides:
  1. Replication factor validation across datasets.
  2. Cluster health assessment based on live DataNode count.
  3. Under-replicated block monitoring.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── Cluster health status ─────────────────────────────────────────────────

class ClusterHealth(str, Enum):
    """Overall cluster health states."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNAVAILABLE = "unavailable"


# ── Replication status ────────────────────────────────────────────────────

@dataclass
class ReplicationStatus:
    """Current replication state of the HDFS cluster."""
    target_replication: int
    live_datanodes: int
    total_blocks: int = 0
    under_replicated_blocks: int = 0
    missing_blocks: int = 0
    corrupt_blocks: int = 0
    health: ClusterHealth = ClusterHealth.HEALTHY

    @property
    def effective_replication(self) -> int:
        """The actual replication factor achievable with current nodes."""
        return min(self.target_replication, self.live_datanodes)

    @property
    def is_fully_replicated(self) -> bool:
        """Whether the cluster can achieve the target replication factor."""
        return self.live_datanodes >= self.target_replication

    @property
    def replication_ratio(self) -> float:
        """Fraction of target replication achieved (0.0 to 1.0)."""
        if self.target_replication == 0:
            return 0.0
        return min(1.0, self.live_datanodes / self.target_replication)


# ── Health assessment ─────────────────────────────────────────────────────

def assess_cluster_health(
    live_datanodes: int,
    target_replication: int = 3,
    min_datanodes: int = 1,
    under_replicated_blocks: int = 0,
    missing_blocks: int = 0,
    corrupt_blocks: int = 0,
    total_blocks: int = 0,
) -> ReplicationStatus:
    """Assess overall cluster health based on replication metrics.

    Parameters
    ----------
    live_datanodes : int
        Number of currently live DataNodes.
    target_replication : int
        Desired replication factor (default: 3).
    min_datanodes : int
        Minimum DataNodes for the cluster to be considered operational.
    under_replicated_blocks : int
        Number of blocks below target replication.
    missing_blocks : int
        Number of blocks with zero replicas.
    corrupt_blocks : int
        Number of corrupt block replicas.
    total_blocks : int
        Total number of blocks in the filesystem.

    Returns
    -------
    ReplicationStatus
        Complete health assessment.
    """
    # Determine health level
    if live_datanodes == 0:
        health = ClusterHealth.UNAVAILABLE
    elif missing_blocks > 0 or corrupt_blocks > 0:
        health = ClusterHealth.CRITICAL
    elif live_datanodes < min_datanodes:
        health = ClusterHealth.CRITICAL
    elif live_datanodes < target_replication or under_replicated_blocks > 0:
        health = ClusterHealth.DEGRADED
    else:
        health = ClusterHealth.HEALTHY

    status = ReplicationStatus(
        target_replication=target_replication,
        live_datanodes=live_datanodes,
        total_blocks=total_blocks,
        under_replicated_blocks=under_replicated_blocks,
        missing_blocks=missing_blocks,
        corrupt_blocks=corrupt_blocks,
        health=health,
    )

    logger.info(
        "[replication] Cluster health: %s — %d/%d DataNodes live, "
        "effective replication %d/%d, under-replicated: %d, missing: %d",
        health.value,
        live_datanodes, target_replication,
        status.effective_replication, target_replication,
        under_replicated_blocks, missing_blocks,
    )

    return status


def validate_replication_factor(
    requested: int,
    live_datanodes: int,
) -> tuple[bool, str]:
    """Check if a requested replication factor is achievable.

    Parameters
    ----------
    requested : int
        Desired replication factor.
    live_datanodes : int
        Number of currently live DataNodes.

    Returns
    -------
    tuple[bool, str]
        (is_valid, message)
    """
    if requested < 1:
        return False, f"Replication factor must be >= 1, got {requested}."

    if requested > live_datanodes:
        return (
            False,
            f"Replication factor {requested} exceeds live DataNodes "
            f"({live_datanodes}). Data would be under-replicated.",
        )

    return True, f"Replication factor {requested} is achievable with {live_datanodes} DataNodes."


def parse_jmx_replication_metrics(jmx_data: dict[str, Any]) -> dict[str, int]:
    """Parse replication-relevant metrics from NameNode JMX data.

    Parameters
    ----------
    jmx_data : dict
        Raw JMX response from NameNode.

    Returns
    -------
    dict[str, int]
        Parsed metrics: ``live_datanodes``, ``under_replicated_blocks``,
        ``missing_blocks``, ``corrupt_blocks``, ``total_blocks``.
    """
    result: dict[str, int] = {
        "live_datanodes": 0,
        "under_replicated_blocks": 0,
        "missing_blocks": 0,
        "corrupt_blocks": 0,
        "total_blocks": 0,
    }

    beans = jmx_data.get("beans", [])
    for bean in beans:
        if "NumLiveDataNodes" in bean:
            result["live_datanodes"] = int(bean.get("NumLiveDataNodes", 0))
        if "UnderReplicatedBlocks" in bean:
            result["under_replicated_blocks"] = int(bean.get("UnderReplicatedBlocks", 0))
        if "MissingBlocks" in bean:
            result["missing_blocks"] = int(bean.get("MissingBlocks", 0))
        if "CorruptBlocks" in bean:
            result["corrupt_blocks"] = int(bean.get("CorruptBlocks", 0))
        if "BlocksTotal" in bean:
            result["total_blocks"] = int(bean.get("BlocksTotal", 0))

    return result
