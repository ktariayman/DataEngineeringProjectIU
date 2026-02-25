"""
Data lineage & audit tracker for the storage microservice.

Governance guarantees:
  - Every storage operation produces a **lineage record** documenting
    zone paths affected, permissions applied, replication status,
    timestamps, and component version.
  - Records are persisted as JSON for audit trail.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class StorageLineageRecord:
    """Audit record of a storage management operation."""

    def __init__(
        self,
        operation_name: str,
        component_version: str,
    ) -> None:
        self.operation_name = operation_name
        self.component_version = component_version
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.finished_at: Optional[str] = None
        self.status: str = "running"
        self.zones_affected: list[str] = []
        self.paths_created: list[str] = []
        self.permissions_applied: list[dict[str, str]] = []
        self.steps: list[dict[str, Any]] = []

    def record_zone(self, zone_path: str) -> None:
        """Log a zone that was touched by this operation."""
        if zone_path not in self.zones_affected:
            self.zones_affected.append(zone_path)

    def record_path_created(self, path: str) -> None:
        """Log a path that was created."""
        self.paths_created.append(path)

    def record_permission(self, path: str, permission: str, owner: str, group: str) -> None:
        """Log a permission change."""
        self.permissions_applied.append({
            "path": path,
            "permission": permission,
            "owner": owner,
            "group": group,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def record_step(
        self,
        step_name: str,
        status: str = "success",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Log a step in the operation."""
        self.steps.append({
            "step": step_name,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **(details or {}),
        })

    def finish(self, status: str = "success") -> None:
        self.finished_at = datetime.now(timezone.utc).isoformat()
        self.status = status

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_name": self.operation_name,
            "component_version": self.component_version,
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status,
            "zones_affected": self.zones_affected,
            "paths_created": self.paths_created,
            "permissions_applied": self.permissions_applied,
            "steps": self.steps,
        }


def save_lineage(record: StorageLineageRecord, output_dir: str = "lineage") -> str:
    """Persist a storage lineage record as JSON.

    Returns
    -------
    str
        Path to the saved JSON file.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    filename = f"{record.operation_name}_{record.run_id}.json"
    filepath = out / filename
    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(record.to_dict(), fh, indent=2, ensure_ascii=False)
    logger.info("[lineage] Storage record saved → %s", filepath)
    return str(filepath)
