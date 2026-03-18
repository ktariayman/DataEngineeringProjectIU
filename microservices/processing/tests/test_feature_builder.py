"""
Tests for the feature_builder module.
Covers correctness join with questions, time feature extraction,
response-time capping, and non-respond action handling.
"""

from __future__ import annotations

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.feature_builder import cap_response_time, enrich_interactions


class TestEnrichInteractions:
    """Validate the interaction-enrichment pipeline."""

    # ── Correctness join ────────────────────────────────────────────────

    def test_is_correct_for_respond_actions(self, spark, sample_kt4, sample_questions):
        """respond rows should have is_correct=1 when user_answer matches correct_answer."""
        print("\n[TEST] test_is_correct_for_respond_actions")

        enriched = enrich_interactions(
            sample_kt4, sample_questions,
            correctness_join=True,
            time_features=False,
            response_time_cap_ms=300000,
        )
        # u001 answered q001 with 'a', correct_answer for q001 is 'a' → is_correct=1
        rows = enriched.filter(
            (enriched.user_id == "u001")
            & (enriched.item_id == "q001")
            & (enriched.action_type == "respond")
        ).take(2)

        assert len(rows) >= 1
        first = rows[0]
        assert first["is_correct"] == 1
        print("  ✓ u001 q001 is_correct=1 (answer 'a' == correct 'a')")

    def test_is_correct_wrong_answer(self, spark, sample_kt4, sample_questions):
        """respond rows should have is_correct=0 when answers don't match."""
        print("\n[TEST] test_is_correct_wrong_answer")

        enriched = enrich_interactions(
            sample_kt4, sample_questions,
            correctness_join=True,
            time_features=False,
            response_time_cap_ms=300000,
        )
        # u002 answered q001 with 'b', correct answer is 'a' → is_correct=0
        rows = enriched.filter(
            (enriched.user_id == "u002")
            & (enriched.item_id == "q001")
            & (enriched.action_type == "respond")
        ).take(1)

        assert len(rows) == 1
        assert rows[0]["is_correct"] == 0
        print("  ✓ u002 q001 is_correct=0 (answer 'b' != correct 'a')")

    def test_enter_actions_have_null_is_correct(self, spark, sample_kt4, sample_questions):
        """Non-respond actions (enter) should have is_correct=None or 0."""
        print("\n[TEST] test_enter_actions_have_null_is_correct")

        enriched = enrich_interactions(
            sample_kt4, sample_questions,
            correctness_join=True,
            time_features=False,
            response_time_cap_ms=300000,
        )
        enter_rows = enriched.filter(enriched.action_type == "enter").take(5)
        assert len(enter_rows) >= 1
        for row in enter_rows:
            assert row["is_correct"] in (None, 0)
        print("  ✓ enter actions have is_correct in (None, 0)")

    # ── Time features ───────────────────────────────────────────────────

    def test_time_features_extracted(self, spark, sample_kt4, sample_questions):
        """With time_features=True, hour_of_day and day_of_week should be populated."""
        print("\n[TEST] test_time_features_extracted")

        enriched = enrich_interactions(
            sample_kt4, sample_questions,
            correctness_join=False,
            time_features=True,
            response_time_cap_ms=300000,
        )
        assert "hour_of_day" in enriched.columns
        assert "day_of_week" in enriched.columns
        print("  ✓ hour_of_day and day_of_week columns present")

        row = enriched.first()
        assert row["hour_of_day"] is not None
        assert row["day_of_week"] is not None
        print("  ✓ time feature values are non-null")

    def test_hour_of_day_range(self, spark, sample_kt4, sample_questions):
        """hour_of_day should be in 0-23."""
        print("\n[TEST] test_hour_of_day_range")

        enriched = enrich_interactions(
            sample_kt4, sample_questions,
            correctness_join=False,
            time_features=True,
            response_time_cap_ms=300000,
        )
        from pyspark.sql import functions as F
        stats = enriched.agg(
            F.min("hour_of_day").alias("min_h"),
            F.max("hour_of_day").alias("max_h"),
        ).first()

        assert stats["min_h"] >= 0
        assert stats["max_h"] <= 23
        print(f"  ✓ hour_of_day range [{stats['min_h']}, {stats['max_h']}] within [0, 23]")

    # ── Response-time capping ───────────────────────────────────────────

    def test_response_time_capped(self, spark, sample_kt4, sample_questions):
        """response_time_ms should never exceed the configured cap."""
        print("\n[TEST] test_response_time_capped")

        cap = 20000  # 20 seconds - some test rows exceed this
        enriched = enrich_interactions(
            sample_kt4, sample_questions,
            correctness_join=False,
            time_features=False,
            response_time_cap_ms=cap,
        )
        from pyspark.sql import functions as F
        max_rt = enriched.agg(F.max("response_time_ms")).first()[0]
        assert max_rt <= cap
        print(f"  ✓ max response_time_ms={max_rt} <= cap={cap}")

    # ── Row count preservation ──────────────────────────────────────────

    def test_row_count_preserved(self, spark, sample_kt4, sample_questions):
        """Enrichment should not drop or add rows (left join)."""
        print("\n[TEST] test_row_count_preserved")

        original_count = sample_kt4.count()
        enriched = enrich_interactions(
            sample_kt4, sample_questions,
            correctness_join=True,
            time_features=True,
            response_time_cap_ms=300000,
        )
        enriched_count = enriched.count()
        assert enriched_count == original_count
        print(f"  ✓ row count preserved: {enriched_count} == {original_count}")


class TestCapResponseTime:
    """Standalone cap_response_time() tests."""

    def test_cap_limits_value(self, spark):
        """Values above cap should be clamped."""
        print("\n[TEST] test_cap_limits_value")

        from pyspark.sql import functions as F
        df = spark.createDataFrame(
            [(100,), (500000,), (200,)], ["elapsed_time"]
        )
        result = cap_response_time(df, cap_ms=1000)
        rows = result.select("elapsed_time").orderBy("elapsed_time").take(3)
        assert rows[0]["elapsed_time"] == 100
        assert rows[1]["elapsed_time"] == 200
        assert rows[2]["elapsed_time"] == 1000
        print("  ✓ values correctly capped at 1000")
