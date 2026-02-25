"""Tests for :mod:`microservices.storage.src.lineage`.

Covers governance guarantee:
  - Storage audit trail for zone operations
  - Lineage records persisted as JSON
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_project_root = str(Path(__file__).resolve().parents[3])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from microservices.storage.src.lineage import StorageLineageRecord, save_lineage


class TestStorageLineageRecord:
    """Verify storage lineage record creation."""

    def test_record_creation(self) -> None:
        print("\n[TEST] Create storage lineage record")
        rec = StorageLineageRecord(
            operation_name="zone_init",
            component_version="1.0.0",
        )
        print(f"  operation_name    = '{rec.operation_name}'")
        print(f"  component_version = '{rec.component_version}'")
        print(f"  run_id            = '{rec.run_id}'")
        print(f"  status            = '{rec.status}'")
        assert rec.operation_name == "zone_init"
        assert rec.status == "running"
        assert rec.run_id is not None
        print("  ✓ Record created with running status")

    def test_record_zone(self) -> None:
        print("\n[TEST] Record zone affected")
        rec = StorageLineageRecord("test_op", "1.0.0")
        rec.record_zone("/data/raw")
        rec.record_zone("/data/curated")
        rec.record_zone("/data/raw")  # duplicate
        print(f"  zones_affected = {rec.zones_affected}")
        assert len(rec.zones_affected) == 2
        assert "/data/raw" in rec.zones_affected
        assert "/data/curated" in rec.zones_affected
        print("  ✓ Zones recorded with dedup")

    def test_record_path_created(self) -> None:
        print("\n[TEST] Record paths created")
        rec = StorageLineageRecord("test_op", "1.0.0")
        rec.record_path_created("/data/raw/kt4")
        rec.record_path_created("/data/raw/content/lectures")
        print(f"  paths_created = {rec.paths_created}")
        assert len(rec.paths_created) == 2
        print("  ✓ Created paths recorded")

    def test_record_permission(self) -> None:
        print("\n[TEST] Record permission change")
        rec = StorageLineageRecord("test_op", "1.0.0")
        rec.record_permission("/data/raw", "755", "hdfs", "hadoop")
        print(f"  permissions_applied = {rec.permissions_applied}")
        assert len(rec.permissions_applied) == 1
        perm = rec.permissions_applied[0]
        assert perm["path"] == "/data/raw"
        assert perm["permission"] == "755"
        assert perm["owner"] == "hdfs"
        print("  ✓ Permission change recorded with timestamp")

    def test_record_step(self) -> None:
        print("\n[TEST] Record operation step")
        rec = StorageLineageRecord("test_op", "1.0.0")
        rec.record_step("create_dirs", status="success", details={"count": 8})
        rec.record_step("set_permissions", status="success")
        print(f"  steps = {rec.steps}")
        assert len(rec.steps) == 2
        assert rec.steps[0]["step"] == "create_dirs"
        assert rec.steps[0]["count"] == 8
        print("  ✓ Operation steps recorded with details")

    def test_finish_record(self) -> None:
        print("\n[TEST] Finish record sets status and timestamp")
        rec = StorageLineageRecord("test_op", "1.0.0")
        rec.finish(status="success")
        print(f"  status      = '{rec.status}'")
        print(f"  finished_at = '{rec.finished_at}'")
        assert rec.status == "success"
        assert rec.finished_at is not None
        print("  ✓ Record finished with timestamp")

    def test_to_dict(self) -> None:
        print("\n[TEST] Serialize record to dict")
        rec = StorageLineageRecord("zone_init", "1.0.0")
        rec.record_zone("/data/raw")
        rec.record_step("test_step")
        rec.finish("success")
        d = rec.to_dict()
        print(f"  Dict keys: {sorted(d.keys())}")
        assert d["operation_name"] == "zone_init"
        assert d["status"] == "success"
        assert len(d["zones_affected"]) == 1
        assert len(d["steps"]) == 1
        print("  ✓ Dict contains all fields")


class TestSaveLineage:
    """Verify lineage persistence."""

    def test_save_creates_json_file(self, tmp_path: Path) -> None:
        print("\n[TEST] Save lineage record as JSON file")
        rec = StorageLineageRecord("zone_init", "1.0.0")
        rec.record_zone("/data/raw")
        rec.finish("success")

        output_dir = str(tmp_path / "lineage")
        filepath = save_lineage(rec, output_dir=output_dir)
        print(f"  Saved to: {filepath}")

        saved_path = Path(filepath)
        assert saved_path.exists()
        assert saved_path.suffix == ".json"

        # Verify JSON content
        with open(saved_path, "r") as f:
            data = json.load(f)
        print(f"  JSON keys: {sorted(data.keys())}")
        assert data["operation_name"] == "zone_init"
        assert data["status"] == "success"
        assert "/data/raw" in data["zones_affected"]
        print("  ✓ Lineage record persisted as valid JSON")

    def test_save_creates_directory(self, tmp_path: Path) -> None:
        print("\n[TEST] Save creates output directory if missing")
        rec = StorageLineageRecord("test_save", "1.0.0")
        rec.finish("success")

        new_dir = str(tmp_path / "nested" / "lineage")
        filepath = save_lineage(rec, output_dir=new_dir)
        print(f"  Created dir + file: {filepath}")
        assert Path(filepath).exists()
        print("  ✓ Directory created automatically")
