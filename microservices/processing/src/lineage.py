"""
Data lineage & audit tracker for the processing microservice.

Governance guarantees:
  - Every processing pipeline run produces a **lineage record** documenting
    input sources consumed, transformations applied, output datasets produced,
    row counts, schema versions, and execution timestamps.
  - Records are persisted as JSON for audit trail and regulatory compliance.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ProcessingLineageRecord:
    """Audit record of a processing pipeline execution."""

    def __init__(
        self,
        pipeline_name: str,
        pipeline_version: str,
        run_mode: str = "initial",
    ) -> None:
        self.pipeline_name = pipeline_name
        self.pipeline_version = pipeline_version
        self.run_mode = run_mode
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.finished_at: Optional[str] = None
        self.status: str = "running"
        self.sources: list[dict[str, Any]] = []
        self.targets: list[dict[str, Any]] = []
        self.transformations: list[dict[str, Any]] = []
        self.steps: list[dict[str, Any]] = []
        self.metrics: dict[str, Any] = {}

    # ── Source / target tracking ──────────────────────────────────────

    def record_source(
        self,
        name: str,
        path: str,
        row_count: int,
        columns: list[str],
        format: str = "parquet",
        schema_version: str = "unknown",
    ) -> None:
        """Log an input dataset consumed by this pipeline run."""
        self.sources.append({
            "name": name,
            "path": path,
            "row_count": row_count,
            "columns": columns,
            "format": format,
            "schema_version": schema_version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def record_target(
        self,
        name: str,
        path: str,
        row_count: int,
        format: str = "parquet",
        write_mode: str = "overwrite",
    ) -> None:
        """Log an output dataset produced by this pipeline run."""
        self.targets.append({
            "name": name,
            "path": path,
            "row_count": row_count,
            "format": format,
            "write_mode": write_mode,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # ── Transformation tracking ──────────────────────────────────────

    def record_transformation(
        self,
        name: str,
        input_rows: int,
        output_rows: int,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Log a transformation step with input/output row counts."""
        self.transformations.append({
            "name": name,
            "input_rows": input_rows,
            "output_rows": output_rows,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **(details or {}),
        })

    # ── Step tracking ────────────────────────────────────────────────

    def record_step(
        self,
        step_name: str,
        status: str = "success",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Log a logical pipeline step."""
        self.steps.append({
            "step": step_name,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **(details or {}),
        })

    # ── Metrics ──────────────────────────────────────────────────────

    def record_metric(self, key: str, value: Any) -> None:
        """Store an arbitrary metric (e.g. users_processed, avg_accuracy)."""
        self.metrics[key] = value

    # ── Finalisation ─────────────────────────────────────────────────

    def finish(self, status: str = "success") -> None:
        self.finished_at = datetime.now(timezone.utc).isoformat()
        self.status = status

    def to_dict(self) -> dict[str, Any]:
        return {
            "pipeline_name": self.pipeline_name,
            "pipeline_version": self.pipeline_version,
            "run_mode": self.run_mode,
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status,
            "sources": self.sources,
            "targets": self.targets,
            "transformations": self.transformations,
            "steps": self.steps,
            "metrics": self.metrics,
        }


def save_lineage(record: ProcessingLineageRecord, output_dir: str = "lineage") -> str:
    """Persist a processing lineage record as JSON.

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
    logger.info("[lineage] Processing record saved → %s", filepath)
    return str(filepath)
