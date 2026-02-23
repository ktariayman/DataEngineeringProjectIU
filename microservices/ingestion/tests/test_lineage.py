"""Tests for :mod:`microservices.ingestion.src.lineage`."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Add project root to path for direct execution
_project_root = str(Path(__file__).resolve().parents[3])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from microservices.ingestion.src.lineage import LineageRecord, save_lineage


class TestLineageRecord:
    def _make_record(self) -> LineageRecord:
        return LineageRecord(
            pipeline_name="test-pipeline",
            pipeline_version="1.0.0",
            run_mode="initial",
        )

    def test_initial_state(self) -> None:
        print("\n[TEST] Lineage record initial state")
        rec = self._make_record()
        print(f"  Pipeline: {rec.pipeline_name}")
        print(f"  Status: {rec.status}")
        print(f"  Sources: {len(rec.sources)}")
        print(f"  Targets: {len(rec.targets)}")
        print(f"  Steps: {len(rec.steps)}")
        print(f"  ✓ Record initialized correctly")
        assert rec.status == "running"
        assert rec.pipeline_name == "test-pipeline"
        assert rec.sources == {}
        assert rec.targets == {}
        assert rec.steps == []

    def test_record_source(self) -> None:
        print("\n[TEST] Record data source")
        rec = self._make_record()
        rec.record_source("kt4", "/data/kt4", 1000, ["ts", "action"], "1.0.0")
        print(f"  Source name: kt4")
        print(f"  Path: /data/kt4")
        print(f"  Row count: {rec.sources['kt4']['row_count']}")
        print(f"  Columns: {rec.sources['kt4']['columns']}")
        print(f"  Schema version: {rec.sources['kt4']['schema_version']}")
        print(f"  ✓ Source recorded successfully")
        assert "kt4" in rec.sources
        assert rec.sources["kt4"]["row_count"] == 1000
        assert rec.sources["kt4"]["schema_version"] == "1.0.0"

    def test_record_target(self) -> None:
        print("\n[TEST] Record data target")
        rec = self._make_record()
        rec.record_target("kt4", "hdfs://nn:9000/raw/kt4", 950, "parquet", "append")
        print(f"  Target name: kt4")
        print(f"  Path: {rec.targets['kt4']['path']}")
        print(f"  Row count: {rec.targets['kt4']['row_count']}")
        print(f"  Format: {rec.targets['kt4']['format']}")
        print(f"  Write mode: {rec.targets['kt4']['write_mode']}")        
        print(f"  ✓ Target recorded successfully")
        assert "kt4" in rec.targets
        assert rec.targets["kt4"]["format"] == "parquet"

    def test_record_step(self) -> None:
        print("\n[TEST] Record pipeline step")
        rec = self._make_record()
        rec.record_step("file_intake", "success", {"rows_read": 42})
        print(f"  Step: {rec.steps[0]['step']}")
        print(f"  Status: {rec.steps[0]['status']}")
        print(f"  Metadata: rows_read={rec.steps[0]['rows_read']}")
        print(f"  ✓ Step recorded successfully")
        assert len(rec.steps) == 1
        assert rec.steps[0]["step"] == "file_intake"
        assert rec.steps[0]["rows_read"] == 42

    def test_finish(self) -> None:
        print("\n[TEST] Finish lineage record")
        rec = self._make_record()
        print(f"  Initial status: {rec.status}")
        rec.finish("success")
        print(f"  Final status: {rec.status}")
        print(f"  Finished at: {rec.finished_at}")
        print(f"  ✓ Record finalized successfully")
        assert rec.status == "success"
        assert rec.finished_at is not None

    def test_to_dict_structure(self) -> None:
        print("\n[TEST] Lineage record to_dict structure")
        rec = self._make_record()
        rec.record_source("kt4", "/data/kt4", 100, ["ts"], "1.0.0")
        rec.record_step("validation")
        rec.finish("success")

        d = rec.to_dict()
        print(f"  Dictionary keys: {list(d.keys())}")
        print(f"  Pipeline: {d['pipeline_name']} v{d['pipeline_version']}")
        print(f"  Run mode: {d['run_mode']}")
        print(f"  Status: {d['status']}")
        print(f"  Sources: {list(d['sources'].keys())}")
        print(f"  Steps: {len(d['steps'])}")
        print(f"  ✓ Dictionary structure validated")
        assert d["pipeline_name"] == "test-pipeline"
        assert d["pipeline_version"] == "1.0.0"
        assert d["run_mode"] == "initial"
        assert d["status"] == "success"
        assert "kt4" in d["sources"]
        assert len(d["steps"]) == 1


class TestSaveLineage:
    def test_creates_json_file(self, tmp_path: Path) -> None:
        print("\n[TEST] Save lineage to JSON file")
        rec = LineageRecord("pipe", "1.0.0", "daily")
        rec.record_source("lectures", "/lectures.csv", 50, ["id"], "1.0.0")
        rec.finish("success")
        print(f"  Pipeline: {rec.pipeline_name} v{rec.pipeline_version}")
        print(f"  Run mode: {rec.run_mode}")

        path = save_lineage(rec, output_dir=str(tmp_path))
        print(f"  Saved to: {path}")
        assert Path(path).exists()

        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        print(f"  JSON contains {len(data)} fields")
        print(f"  Status: {data['status']}")
        print(f"  Sources: {list(data['sources'].keys())}")
        print(f"  ✓ Lineage saved and validated")
        assert data["pipeline_name"] == "pipe"
        assert data["status"] == "success"
        assert "lectures" in data["sources"]

    def test_creates_output_dir_if_missing(self, tmp_path: Path) -> None:
        print("\n[TEST] Create output directory if missing")
        nested = tmp_path / "sub" / "dir"
        print(f"  Target directory: {nested}")
        print(f"  Exists before: {nested.exists()}")
        rec = LineageRecord("p", "0.1.0", "initial")
        rec.finish("success")

        path = save_lineage(rec, output_dir=str(nested))
        print(f"  Exists after: {nested.exists()}")
        print(f"  Lineage saved to: {path}")
        print(f"  ✓ Output directory created automatically")
        assert nested.exists()
        assert Path(path).exists()
