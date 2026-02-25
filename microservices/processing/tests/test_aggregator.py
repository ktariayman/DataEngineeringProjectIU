"""
Tests for the aggregator module.
Covers per-student feature aggregation and minimum-interaction filtering.
"""

from __future__ import annotations

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.aggregator import aggregate_student_features, filter_min_interactions
from src.feature_builder import enrich_interactions


class TestAggregateStudentFeatures:
    """Validate the per-student aggregation logic."""

    # ── Helper ──────────────────────────────────────────────────────────

    def _enriched(self, spark, sample_kt4, sample_questions):
        """Return an enriched DataFrame for aggregation tests."""
        return enrich_interactions(
            sample_kt4, sample_questions,
            correctness_join=True,
            time_features=True,
            response_time_cap_ms=300000,
        )

    # ── Core aggregation ────────────────────────────────────────────────

    def test_produces_one_row_per_user(self, spark, sample_kt4, sample_questions):
        """Aggregation should yield exactly one row per user_id."""
        print("\n[TEST] test_produces_one_row_per_user")

        enriched = self._enriched(spark, sample_kt4, sample_questions)
        agg = aggregate_student_features(enriched)

        user_count = agg.select("user_id").distinct().count()
        total_rows = agg.count()
        assert total_rows == user_count
        print(f"  ✓ {total_rows} rows == {user_count} distinct users")

    def test_expected_users_present(self, spark, sample_kt4, sample_questions):
        """u001, u002, u003 should all appear in aggregation output."""
        print("\n[TEST] test_expected_users_present")

        enriched = self._enriched(spark, sample_kt4, sample_questions)
        agg = aggregate_student_features(enriched)

        users = {row["user_id"] for row in agg.select("user_id").take(10)}
        for uid in ("u001", "u002", "u003"):
            assert uid in users
            print(f"  ✓ '{uid}' present in aggregated output")

    def test_total_interactions_count(self, spark, sample_kt4, sample_questions):
        """total_interactions should match the raw row count per user."""
        print("\n[TEST] test_total_interactions_count")

        enriched = self._enriched(spark, sample_kt4, sample_questions)
        agg = aggregate_student_features(enriched)

        # u001 has 6 rows in sample_kt4
        u001 = agg.filter(agg.user_id == "u001").first()
        assert u001 is not None
        assert u001["total_interactions"] == 6
        print("  ✓ u001 total_interactions=6")

        # u003 has 6 rows
        u003 = agg.filter(agg.user_id == "u003").first()
        assert u003["total_interactions"] == 6
        print("  ✓ u003 total_interactions=6")

    def test_accuracy_rate_range(self, spark, sample_kt4, sample_questions):
        """accuracy_rate should be in [0.0, 1.0]."""
        print("\n[TEST] test_accuracy_rate_range")

        enriched = self._enriched(spark, sample_kt4, sample_questions)
        agg = aggregate_student_features(enriched)

        from pyspark.sql import functions as F
        stats = agg.agg(
            F.min("accuracy_rate").alias("min_acc"),
            F.max("accuracy_rate").alias("max_acc"),
        ).first()

        assert stats["min_acc"] >= 0.0
        assert stats["max_acc"] <= 1.0
        print(f"  ✓ accuracy_rate range [{stats['min_acc']:.2f}, {stats['max_acc']:.2f}] ⊆ [0, 1]")

    def test_unique_questions_attempted(self, spark, sample_kt4, sample_questions):
        """unique_questions_attempted should count distinct question item_ids."""
        print("\n[TEST] test_unique_questions_attempted")

        enriched = self._enriched(spark, sample_kt4, sample_questions)
        agg = aggregate_student_features(enriched)

        # u001 answered q001, q002, q003, q004 (4 unique questions among respond actions)
        u001 = agg.filter(agg.user_id == "u001").first()
        assert u001["unique_questions_attempted"] >= 3
        print(f"  ✓ u001 unique_questions_attempted={u001['unique_questions_attempted']} >= 3")

    def test_unique_lectures_viewed(self, spark, sample_kt4, sample_questions):
        """unique_lectures_viewed should count enter actions for lecture items."""
        print("\n[TEST] test_unique_lectures_viewed")

        enriched = self._enriched(spark, sample_kt4, sample_questions)
        agg = aggregate_student_features(enriched)

        # u002 entered l001 and l002 (2 lectures)
        u002 = agg.filter(agg.user_id == "u002").first()
        assert u002["unique_lectures_viewed"] >= 1
        print(f"  ✓ u002 unique_lectures_viewed={u002['unique_lectures_viewed']} >= 1")

    def test_active_days_count(self, spark, sample_kt4, sample_questions):
        """active_days should count distinct event_date values per user."""
        print("\n[TEST] test_active_days_count")

        enriched = self._enriched(spark, sample_kt4, sample_questions)
        agg = aggregate_student_features(enriched)

        # u001 has events on 2021-01-01, 2021-01-02, 2021-01-03 → 3 days
        u001 = agg.filter(agg.user_id == "u001").first()
        assert u001["active_days"] == 3
        print("  ✓ u001 active_days=3")

    def test_output_has_expected_columns(self, spark, sample_kt4, sample_questions):
        """Output should include all key aggregation columns."""
        print("\n[TEST] test_output_has_expected_columns")

        enriched = self._enriched(spark, sample_kt4, sample_questions)
        agg = aggregate_student_features(enriched)

        expected = {
            "user_id", "total_interactions", "correct_count",
            "incorrect_count", "accuracy_rate", "avg_response_time_ms",
            "unique_questions_attempted", "unique_lectures_viewed", "active_days",
        }
        actual = set(agg.columns)
        missing = expected - actual
        assert not missing, f"Missing columns: {missing}"
        print(f"  ✓ all {len(expected)} expected columns present")


class TestFilterMinInteractions:
    """Validate minimum-interaction filtering."""

    def test_filters_low_activity_students(self, spark, sample_kt4, sample_questions):
        """Students below the threshold should be removed."""
        print("\n[TEST] test_filters_low_activity_students")

        enriched = self._enriched(spark, sample_kt4, sample_questions)
        agg = aggregate_student_features(enriched)

        # All three users have >= 5 interactions, so threshold of 100 should remove all
        filtered = filter_min_interactions(agg, min_interactions=100)
        assert filtered.count() == 0
        print("  ✓ all students filtered out with threshold=100")

    def test_keeps_active_students(self, spark, sample_kt4, sample_questions):
        """Students above the threshold should be retained."""
        print("\n[TEST] test_keeps_active_students")

        enriched = self._enriched(spark, sample_kt4, sample_questions)
        agg = aggregate_student_features(enriched)

        # All 3 users have >= 5 interactions
        filtered = filter_min_interactions(agg, min_interactions=5)
        assert filtered.count() == 3
        print("  ✓ all 3 students retained with threshold=5")

    # -- helper shared by both test classes --

    def _enriched(self, spark, sample_kt4, sample_questions):
        return enrich_interactions(
            sample_kt4, sample_questions,
            correctness_join=True,
            time_features=True,
            response_time_cap_ms=300000,
        )
