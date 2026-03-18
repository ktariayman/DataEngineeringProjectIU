"""
Tests for the processing lineage tracking module.
Covers record creation, source/target/transformation/step/metric tracking,
finish, serialisation, and persistence.
"""

from __future__ import annotations

import json
import os
import time

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.lineage import ProcessingLineageRecord, save_lineage


class TestProcessingLineageRecord:
    """Validate all operations on a ProcessingLineageRecord."""

    def _make_record(self) -> ProcessingLineageRecord:
        return ProcessingLineageRecord(
            pipeline_name="test-pipeline",
            pipeline_version="1.0.0-test",
            run_mode="initial",
        )

    # ── Creation ────────────────────────────────────────────────────────

    def test_record_creation(self):
        """A new lineage record should carry identifying fields."""
        print("\n[TEST] test_record_creation")

        rec = self._make_record()
        assert rec.pipeline_name == "test-pipeline"
        print("  ✓ pipeline_name stored")
        assert rec.run_id is not None
        print("  ✓ run_id auto-generated")
        assert rec.pipeline_version == "1.0.0-test"
        print("  ✓ pipeline_version stored")
        assert rec.started_at is not None
        print("  ✓ started_at populated")

    # ── record_source / record_target ───────────────────────────────────

    def test_record_source_and_target(self):
        """Sources and targets should accumulate in the record."""
        print("\n[TEST] test_record_source_and_target")

        rec = self._make_record()
        rec.record_source("kt4", "/data/raw/kt4", row_count=100, columns=["user_id", "timestamp"])
        rec.record_source("questions", "/data/raw/content/questions", row_count=50, columns=["question_id"])
        rec.record_target("aggregated_student_features", "/data/curated/agg", row_count=80)

        d = rec.to_dict()
        assert len(d["sources"]) == 2
        print("  ✓ 2 sources recorded")
        assert len(d["targets"]) == 1
        print("  ✓ 1 target recorded")
        assert d["sources"][0]["name"] == "kt4"
        print("  ✓ source name preserved")

    # ── record_transformation ───────────────────────────────────────────

    def test_record_transformation(self):
        """Transformations should capture name, input rows, output rows."""
        print("\n[TEST] test_record_transformation")

        rec = self._make_record()
        rec.record_transformation("enrich_interactions", input_rows=100, output_rows=95)

        d = rec.to_dict()
        assert len(d["transformations"]) == 1
        t = d["transformations"][0]
        assert t["name"] == "enrich_interactions"
        print("  ✓ transformation name captured")
        assert t["input_rows"] == 100
        assert t["output_rows"] == 95
        print("  ✓ input/output row counts captured")

    # ── record_step ─────────────────────────────────────────────────────

    def test_record_step(self):
        """Steps should track name, status, and optional details."""
        print("\n[TEST] test_record_step")

        rec = self._make_record()
        rec.record_step("data_intake", "success", details={"info": "read 100 rows"})
        rec.record_step("feature_engineering", "success")

        d = rec.to_dict()
        assert len(d["steps"]) == 2
        print("  ✓ 2 steps recorded")
        assert d["steps"][0]["info"] == "read 100 rows"
        print("  ✓ step detail preserved")

    # ── record_metric ───────────────────────────────────────────────────

    def test_record_metric(self):
        """Arbitrary metrics should accumulate in the metrics dict."""
        print("\n[TEST] test_record_metric")

        rec = self._make_record()
        rec.record_metric("null_ratio", 0.02)
        rec.record_metric("duplicate_count", 5)

        d = rec.to_dict()
        assert len(d["metrics"]) == 2
        print("  ✓ 2 metrics recorded")
        assert d["metrics"]["null_ratio"] == 0.02
        assert d["metrics"]["duplicate_count"] == 5
        print("  ✓ metric keys and values correct")

    # ── finish ──────────────────────────────────────────────────────────

    def test_finish_sets_end_ts_and_status(self):
        """finish() should record end time and final status."""
        print("\n[TEST] test_finish_sets_end_ts_and_status")

        rec = self._make_record()
        rec.finish(status="success")

        d = rec.to_dict()
        assert d["status"] == "success"
        print("  ✓ status set to success")
        assert d["finished_at"] is not None
        print("  ✓ finished_at populated")

    # ── to_dict ─────────────────────────────────────────────────────────

    def test_to_dict_is_json_serializable(self):
        """to_dict() output must be JSON-safe."""
        print("\n[TEST] test_to_dict_is_json_serializable")

        rec = self._make_record()
        rec.record_source("kt4", "/raw/kt4", row_count=50, columns=["user_id"])
        rec.record_target("agg", "/curated/agg", row_count=48)
        rec.record_transformation("enrich", input_rows=50, output_rows=48)
        rec.record_step("intake", "success")
        rec.record_metric("rows", 48)
        rec.finish(status="success")

        text = json.dumps(rec.to_dict())
        assert isinstance(text, str)
        print("  ✓ to_dict() is JSON-serializable")

    # ── save_lineage ────────────────────────────────────────────────────

    def test_save_lineage(self, tmp_path):
        """save_lineage() should write a JSON file to the specified dir."""
        print("\n[TEST] test_save_lineage")

        rec = self._make_record()
        rec.record_source("kt4", "/raw/kt4", row_count=50, columns=["user_id"])
        rec.finish(status="success")

        output_dir = str(tmp_path / "lineage_out")
        save_lineage(rec, output_dir)

        files = os.listdir(output_dir)
        assert len(files) == 1
        print("  ✓ one lineage file written")

        with open(os.path.join(output_dir, files[0]), "r", encoding="utf-8") as fh:
            data = json.load(fh)

        assert data["pipeline_name"] == "test-pipeline"
        print("  ✓ lineage content is valid JSON with correct pipeline_name")
