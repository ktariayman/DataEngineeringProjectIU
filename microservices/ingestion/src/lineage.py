"""
Data lineage & audit tracker for the ingestion pipeline.

Governance guarantees:
  - Every pipeline run produces a **lineage record** documenting:
    source paths, schemas used, row counts, transformations applied,
    target paths, timestamps, and pipeline version.
  - Records are persisted as JSON to a configurable directory and can
    be forwarded to a metadata catalog (e.g. Apache Atlas, DataHub).

This satisfies the "Data Governance" non-functional requirement from the
architecture diagram.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class LineageRecord:
    """Immutable record of one pipeline execution."""

    def __init__(
        self,
        pipeline_name: str,
        pipeline_version: str,
        run_mode: str,
    ) -> None:
        self.pipeline_name = pipeline_name
        self.pipeline_version = pipeline_version
        self.run_mode = run_mode
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.finished_at: Optional[str] = None
        self.status: str = "running"
        self.sources: dict[str, dict[str, Any]] = {}
        self.targets: dict[str, dict[str, Any]] = {}
        self.steps: list[dict[str, Any]] = []

    # ── recording helpers ──────────────────────────────────────────────

    def record_source(
        self,
        name: str,
        path: str,
        row_count: int,
        columns: list[str],
        schema_version: str = "1.0",
    ) -> None:
        """Log a source that was read."""
        self.sources[name] = {
            "path": path,
            "row_count": row_count,
            "columns": columns,
            "schema_version": schema_version,
        }

    def record_target(
        self,
        name: str,
        path: str,
        row_count: int,
        format: str = "parquet",
        write_mode: str = "append",
    ) -> None:
        """Log a target that was written."""
        self.targets[name] = {
            "path": path,
            "row_count": row_count,
            "format": format,
            "mode": write_mode,
            "write_mode": write_mode,
        }

    def record_step(
        self,
        step_name: str,
        status: str = "success",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Log a pipeline step execution."""
        self.steps.append({
            "step": step_name,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **(details or {}),
        })

    def finish(self, status: str = "success") -> None:
        self.finished_at = datetime.now(timezone.utc).isoformat()
        self.status = status

    # ── serialisation ──────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "pipeline_name": self.pipeline_name,
            "pipeline_version": self.pipeline_version,
            "run_id": self.run_id,
            "run_mode": self.run_mode,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status,
            "sources": self.sources,
            "targets": self.targets,
            "steps": self.steps,
        }


def save_lineage(record: LineageRecord, output_dir: str = "lineage") -> str:
    """Persist a lineage record as JSON.

    Returns
    -------
    str
        Path to the saved JSON file.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    filename = f"{record.pipeline_name}_{record.run_id}.json"
    filepath = out / filename
    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(record.to_dict(), fh, indent=2, ensure_ascii=False)
    logger.info("[lineage] Record saved → %s", filepath)
    return str(filepath)
