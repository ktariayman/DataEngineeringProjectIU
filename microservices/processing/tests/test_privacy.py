"""
Tests for the privacy module.
Covers PII column-name scanning, column allowlist enforcement,
and false-positive avoidance.
"""

from __future__ import annotations

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import pytest

from src.privacy import (
    PrivacyViolationError,
    enforce_column_allowlist,
    scan_for_pii_columns,
)


class TestPIIScan:
    """Validate PII column-name scanning heuristics."""

    def test_detects_email_column(self, spark):
        """Columns named 'email' or similar should be flagged."""
        print("\n[TEST] test_detects_email_column")

        df = spark.createDataFrame([("u1", "a@b.com")], ["user_id", "email"])
        flagged = scan_for_pii_columns(df, dataset_name="test", strict=False)
        assert "email" in flagged
        print("  ✓ 'email' column flagged as PII")

    def test_detects_phone_column(self, spark):
        """Columns named 'phone_number' should be flagged."""
        print("\n[TEST] test_detects_phone_column")

        df = spark.createDataFrame([("u1", "555-1234")], ["user_id", "phone_number"])
        flagged = scan_for_pii_columns(df, dataset_name="test", strict=False)
        assert "phone_number" in flagged
        print("  ✓ 'phone_number' flagged as PII")

    def test_detects_ssn_column(self, spark):
        """Columns named 'ssn' should be flagged."""
        print("\n[TEST] test_detects_ssn_column")

        df = spark.createDataFrame([("u1", "123-45-6789")], ["user_id", "ssn"])
        flagged = scan_for_pii_columns(df, dataset_name="test", strict=False)
        assert "ssn" in flagged
        print("  ✓ 'ssn' flagged as PII")

    def test_clean_columns_pass(self, spark):
        """Non-PII column names should produce an empty set."""
        print("\n[TEST] test_clean_columns_pass")

        df = spark.createDataFrame([(1, 0.9)], ["total_interactions", "accuracy_rate"])
        flagged = scan_for_pii_columns(df, dataset_name="test", strict=False)
        assert len(flagged) == 0
        print("  ✓ no PII columns flagged on clean data")

    def test_strict_mode_raises(self, spark):
        """In strict mode, detected PII should raise PrivacyViolationError."""
        print("\n[TEST] test_strict_mode_raises")

        df = spark.createDataFrame([("u1", "a@b.com")], ["user_id", "email_address"])
        with pytest.raises(PrivacyViolationError):
            scan_for_pii_columns(df, dataset_name="test", strict=True)
        print("  ✓ PrivacyViolationError raised in strict mode")


class TestColumnAllowlist:
    """Validate column allowlist enforcement."""

    def test_keeps_only_allowed_columns(self, spark):
        """Columns not in the allowlist should be dropped."""
        print("\n[TEST] test_keeps_only_allowed_columns")

        df = spark.createDataFrame(
            [("u1", 10, 0.85, "secret")],
            ["user_id", "total_interactions", "accuracy_rate", "internal_debug"],
        )
        allowed = ["user_id", "total_interactions", "accuracy_rate"]
        result = enforce_column_allowlist(df, allowed, dataset_name="test")
        assert set(result.columns) == set(allowed)
        print(f"  ✓ output has only {len(allowed)} allowed columns")
        assert "internal_debug" not in result.columns
        print("  ✓ 'internal_debug' column dropped")

    def test_allowlist_preserves_data(self, spark):
        """Allowed columns should retain their data unchanged."""
        print("\n[TEST] test_allowlist_preserves_data")

        df = spark.createDataFrame(
            [("u1", 10)],
            ["user_id", "total_interactions"],
        )
        result = enforce_column_allowlist(df, ["user_id", "total_interactions"], dataset_name="test")
        row = result.first()
        assert row["user_id"] == "u1"
        assert row["total_interactions"] == 10
        print("  ✓ data values preserved after allowlist enforcement")

    def test_allowlist_with_missing_column(self, spark):
        """If an allowed column is missing from the DataFrame, it should be silently skipped."""
        print("\n[TEST] test_allowlist_with_missing_column")

        df = spark.createDataFrame([("u1",)], ["user_id"])
        result = enforce_column_allowlist(df, ["user_id", "nonexistent_col"], dataset_name="test")
        assert "user_id" in result.columns
        print("  ✓ existing allowed column retained")
        # nonexistent_col just gets skipped (select only what exists)
        assert result.count() == 1
        print("  ✓ row count preserved")
