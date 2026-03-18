"""
Tests for the processing schema definitions.
Covers field names, versions, registries, and allowed-column lists.
"""

from __future__ import annotations

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.schemas import (
    AGGREGATED_STUDENT_FEATURES_SCHEMA,
    ALLOWED_OUTPUT_COLUMNS,
    INPUT_SCHEMA_REGISTRY,
    KT4_INPUT_SCHEMA,
    LECTURES_INPUT_SCHEMA,
    OUTPUT_SCHEMA_REGISTRY,
    QUESTIONS_INPUT_SCHEMA,
    RECOMMENDATIONS_SCHEMA,
    SCHEMA_VERSIONS,
    USER_VECTORS_SCHEMA,
    ENRICHED_INTERACTION_SCHEMA,
)


class TestSchemas:
    """Validate schema contracts for the processing microservice."""

    # ── Schema versions ─────────────────────────────────────────────────

    def test_schema_versions_are_present(self):
        """All expected schema version keys must exist."""
        print("\n[TEST] test_schema_versions_are_present")

        for key in ("processing", "aggregated_student_features", "user_vectors", "recommendations_batch"):
            assert key in SCHEMA_VERSIONS, f"Missing version key: {key}"
            print(f"  ✓ SCHEMA_VERSIONS contains '{key}'")

    def test_schema_versions_are_semver_strings(self):
        """Versions should look like semver (N.N.N)."""
        print("\n[TEST] test_schema_versions_are_semver_strings")

        import re
        pattern = re.compile(r"^\d+\.\d+\.\d+$")
        for key, ver in SCHEMA_VERSIONS.items():
            assert pattern.match(ver), f"Bad semver: {key}={ver}"
            print(f"  ✓ '{key}' version '{ver}' is valid semver")

    # ── Input schemas ───────────────────────────────────────────────────

    def test_kt4_input_schema_fields(self):
        """KT4 input schema should contain the expected columns."""
        print("\n[TEST] test_kt4_input_schema_fields")

        expected = {"user_id", "timestamp", "action_type", "item_id", "source",
                    "user_answer", "platform", "elapsed_time", "event_date"}
        actual = {f.name for f in KT4_INPUT_SCHEMA.fields}
        assert expected.issubset(actual), f"Missing: {expected - actual}"
        print(f"  ✓ KT4 schema has all {len(expected)} expected fields")

    def test_lectures_input_schema_fields(self):
        """Lectures schema should at least have lecture_id."""
        print("\n[TEST] test_lectures_input_schema_fields")

        field_names = {f.name for f in LECTURES_INPUT_SCHEMA.fields}
        assert "lecture_id" in field_names
        print("  ✓ 'lecture_id' present in lectures schema")

    def test_questions_input_schema_fields(self):
        """Questions schema should include question_id and correct_answer."""
        print("\n[TEST] test_questions_input_schema_fields")

        field_names = {f.name for f in QUESTIONS_INPUT_SCHEMA.fields}
        for col in ("question_id", "correct_answer"):
            assert col in field_names
            print(f"  ✓ '{col}' present in questions schema")

    # ── Intermediate schema ─────────────────────────────────────────────

    def test_enriched_interaction_schema(self):
        """Enriched schema should add is_correct, response_time_ms, hour_of_day, day_of_week."""
        print("\n[TEST] test_enriched_interaction_schema")

        field_names = {f.name for f in ENRICHED_INTERACTION_SCHEMA.fields}
        for col in ("is_correct", "response_time_ms", "hour_of_day", "day_of_week"):
            assert col in field_names
            print(f"  ✓ '{col}' present in enriched schema")

    # ── Output schemas ──────────────────────────────────────────────────

    def test_aggregated_features_schema_has_user_id(self):
        """Aggregated-features output must have user_id."""
        print("\n[TEST] test_aggregated_features_schema_has_user_id")

        field_names = {f.name for f in AGGREGATED_STUDENT_FEATURES_SCHEMA.fields}
        assert "user_id" in field_names
        print("  ✓ 'user_id' in aggregated features schema")

    def test_user_vectors_schema_fields(self):
        """User vectors schema should have user_id and normalised columns."""
        print("\n[TEST] test_user_vectors_schema_fields")

        field_names = {f.name for f in USER_VECTORS_SCHEMA.fields}
        assert "user_id" in field_names
        print("  ✓ 'user_id' in user vectors schema")
        assert len(field_names) >= 2, "User vectors schema should have >= 2 fields"
        print(f"  ✓ user vectors schema has {len(field_names)} fields")

    def test_recommendations_schema_fields(self):
        """Recommendations schema should have user_id and recommended_user_id."""
        print("\n[TEST] test_recommendations_schema_fields")

        field_names = {f.name for f in RECOMMENDATIONS_SCHEMA.fields}
        for col in ("user_id", "recommended_user_id", "similarity_score"):
            assert col in field_names
            print(f"  ✓ '{col}' in recommendations schema")

    # ── Registries ──────────────────────────────────────────────────────

    def test_input_schema_registry_completeness(self):
        """INPUT_SCHEMA_REGISTRY must map kt4, lectures, questions."""
        print("\n[TEST] test_input_schema_registry_completeness")

        for key in ("kt4", "lectures", "questions"):
            assert key in INPUT_SCHEMA_REGISTRY
            print(f"  ✓ '{key}' in INPUT_SCHEMA_REGISTRY")

    def test_output_schema_registry_completeness(self):
        """OUTPUT_SCHEMA_REGISTRY must map all 3 output datasets."""
        print("\n[TEST] test_output_schema_registry_completeness")

        for key in ("aggregated_student_features", "user_vectors", "recommendations_batch"):
            assert key in OUTPUT_SCHEMA_REGISTRY
            print(f"  ✓ '{key}' in OUTPUT_SCHEMA_REGISTRY")

    # ── Allowed output columns ──────────────────────────────────────────

    def test_allowed_output_columns_derived_from_schemas(self):
        """ALLOWED_OUTPUT_COLUMNS should match fields of output schemas."""
        print("\n[TEST] test_allowed_output_columns_derived_from_schemas")

        agg_fields = {f.name for f in AGGREGATED_STUDENT_FEATURES_SCHEMA.fields}
        assert set(ALLOWED_OUTPUT_COLUMNS["aggregated_student_features"]) == agg_fields
        print("  ✓ aggregated_student_features allowed columns match schema")

        vec_fields = {f.name for f in USER_VECTORS_SCHEMA.fields}
        assert set(ALLOWED_OUTPUT_COLUMNS["user_vectors"]) == vec_fields
        print("  ✓ user_vectors allowed columns match schema")
