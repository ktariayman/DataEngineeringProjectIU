"""
Data retention policy enforcement for the storage microservice.

Privacy guarantees:
  - **No PII stored**: ensured at ingestion; this module enforces
    time-based retention as a defence-in-depth measure.
  - **Retention policy**: automated identification of expired partitions
    based on configurable age thresholds per zone.

Governance guarantees:
  - Data lifecycle is explicitly managed — no unbounded storage growth.
  - Expired data is identified programmatically, deletion is auditable.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


# ── Retention configuration ───────────────────────────────────────────────

@dataclass(frozen=True)
class RetentionPolicy:
    """Retention rules for a storage zone."""
    zone_name: str
    retention_days: int
    enabled: bool = True
    description: str = ""

    @property
    def cutoff_date(self) -> date:
        """Partitions older than this date are eligible for deletion."""
        return date.today() - timedelta(days=self.retention_days)


# ── Default policies (matching storage_config.yaml) ───────────────────────

def get_default_policies() -> dict[str, RetentionPolicy]:
    """Return the default retention policies from the architecture spec."""
    return {
        "raw": RetentionPolicy(
            zone_name="raw",
            retention_days=365,
            enabled=True,
            description="Keep raw data for 1 year",
        ),
        "curated": RetentionPolicy(
            zone_name="curated",
            retention_days=180,
            enabled=True,
            description="Keep curated data for 6 months",
        ),
    }


# ── Partition date extraction ─────────────────────────────────────────────

_PARTITION_DATE_PATTERN = re.compile(r"event_date=(\d{4}-\d{2}-\d{2})")


def extract_partition_date(partition_path: str) -> Optional[date]:
    """Extract the date from a Hive-style partition path.

    Parameters
    ----------
    partition_path : str
        Path like ``/data/raw/kt4/partitions_by_event_date/event_date=2025-01-15``

    Returns
    -------
    date or None
        Parsed date, or ``None`` if the path doesn't contain a parseable date.
    """
    match = _PARTITION_DATE_PATTERN.search(partition_path)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        logger.warning(
            "[retention] Could not parse date from partition: %s",
            partition_path,
        )
        return None


# ── Expired partition detection ───────────────────────────────────────────

def find_expired_partitions(
    partition_paths: list[str],
    policy: RetentionPolicy,
) -> list[str]:
    """Identify partitions that exceed the retention threshold.

    Parameters
    ----------
    partition_paths : list[str]
        HDFS partition paths (Hive-style: ``event_date=YYYY-MM-DD``).
    policy : RetentionPolicy
        Retention rules to apply.

    Returns
    -------
    list[str]
        Paths to partitions that should be deleted.
    """
    if not policy.enabled:
        logger.info(
            "[retention] Policy for zone '%s' is disabled — skipping.",
            policy.zone_name,
        )
        return []

    cutoff = policy.cutoff_date
    expired: list[str] = []

    for path in partition_paths:
        partition_date = extract_partition_date(path)
        if partition_date is None:
            logger.debug(
                "[retention] Skipping non-date partition: %s", path,
            )
            continue
        if partition_date < cutoff:
            expired.append(path)
            logger.info(
                "[retention] EXPIRED: %s (date=%s, cutoff=%s)",
                path, partition_date, cutoff,
            )

    logger.info(
        "[retention] Zone '%s': %d/%d partitions expired (cutoff=%s).",
        policy.zone_name, len(expired), len(partition_paths), cutoff,
    )

    return expired


def generate_deletion_commands(
    expired_paths: list[str],
    dry_run: bool = True,
) -> list[str]:
    """Generate ``hdfs dfs -rm -r`` commands for expired partitions.

    Parameters
    ----------
    expired_paths : list[str]
        Paths to delete.
    dry_run : bool
        If ``True``, prefix commands with ``# DRY RUN:`` for safety.

    Returns
    -------
    list[str]
        Shell commands.
    """
    commands: list[str] = []
    for path in expired_paths:
        cmd = f"hdfs dfs -rm -r -skipTrash {path}"
        if dry_run:
            cmd = f"# DRY RUN: {cmd}"
        commands.append(cmd)
    return commands
