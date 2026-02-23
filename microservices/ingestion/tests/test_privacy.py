"""Tests for :mod:`microservices.ingestion.src.privacy`."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pyspark.sql import SparkSession

# Add project root to path for direct execution
_project_root = str(Path(__file__).resolve().parents[3])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from microservices.ingestion.src.privacy import (
    PrivacyViolationError,
    enforce_column_allowlist,
    scan_for_pii_columns,
)


class TestEnforceColumnAllowlist:
    def test_keeps_only_allowed(self, spark: SparkSession) -> None:
        print("\n[TEST] Enforce column allowlist")
        df = spark.createDataFrame(
            [(1, "a", "extra")], ["id", "name", "secret"]
        )
        print(f"  Original columns: {df.columns}")
        print(f"  Allowlist: ['id', 'name']")
        result = enforce_column_allowlist(df, ["id", "name"], "test")
        print(f"  Result columns: {result.columns}")
        print(f"  ✓ Only allowed columns kept (secret dropped)")
        assert result.columns == ["id", "name"]

    def test_missing_allowed_col_ignored(self, spark: SparkSession) -> None:
        print("\n[TEST] Missing allowed columns ignored")
        df = spark.createDataFrame([(1,)], ["id"])
        print(f"  DataFrame columns: {df.columns}")
        print(f"  Allowlist: ['id', 'missing']")
        result = enforce_column_allowlist(df, ["id", "missing"], "test")
        print(f"  Result columns: {result.columns}")
        print(f"  ✓ Missing 'missing' column ignored gracefully")
        assert result.columns == ["id"]

    def test_all_columns_allowed(self, spark: SparkSession) -> None:
        print("\n[TEST] All columns allowed")
        df = spark.createDataFrame([(1, "a")], ["id", "name"])
        print(f"  DataFrame columns: {df.columns}")
        print(f"  Allowlist: ['id', 'name']")
        result = enforce_column_allowlist(df, ["id", "name"], "test")
        print(f"  Result columns: {result.columns}")
        assert set(result.columns) == {"id", "name"}
        print(f"  ✓ All columns kept, schema intact")

    def test_no_columns_allowed(self, spark: SparkSession) -> None:
        print("\n[TEST] No columns allowed (empty allowlist)")
        df = spark.createDataFrame([(1, "a")], ["id", "name"])
        print(f"  DataFrame columns: {df.columns}")
        print(f"  Allowlist: []")
        result = enforce_column_allowlist(df, [], "test")
        print(f"  Result columns: {result.columns}")
        print(f"  ✓ All columns dropped")
        assert result.columns == []


class TestScanForPiiColumns:
    def test_clean_df_passes(self, spark: SparkSession) -> None:
        print("\n[TEST] PII scan on clean DataFrame")
        df = spark.createDataFrame(
            [(1, "enter", "q1")], ["timestamp", "action_type", "item_id"]
        )
        print(f"  Columns to scan: {df.columns}")
        flagged = scan_for_pii_columns(df, "test", strict=False)
        print(f"  Flagged columns: {flagged if flagged else 'None'}")
        print(f"  ✓ No PII detected")
        assert flagged == []

    def test_detects_email_column(self, spark: SparkSession) -> None:
        print("\n[TEST] PII scan detects email column")
        df = spark.createDataFrame(
            [("a@b.com",)], ["email"]
        )
        print(f"  Column name: email")
        flagged = scan_for_pii_columns(df, "test", strict=False)
        print(f"  Flagged: {flagged}")
        print(f"  ✓ Email column detected as PII")
        assert "email" in flagged

    def test_detects_phone_column(self, spark: SparkSession) -> None:
        print("\n[TEST] PII scan detects phone column")
        df = spark.createDataFrame(
            [("555-0100",)], ["phone"]
        )
        print(f"  Column name: phone")
        flagged = scan_for_pii_columns(df, "test", strict=False)
        print(f"  Flagged: {flagged}")
        print(f"  ✓ Phone column detected as PII")
        assert "phone" in flagged

    def test_detects_ssn_column(self, spark: SparkSession) -> None:
        print("\n[TEST] PII scan detects SSN column")
        df = spark.createDataFrame(
            [("123-45-6789",)], ["ssn"]
        )
        print(f"  Column name: ssn")
        flagged = scan_for_pii_columns(df, "test", strict=False)
        print(f"  Flagged: {flagged}")
        print(f"  ✓ SSN column detected as PII")
        assert "ssn" in flagged

    def test_detects_firstname_column(self, spark: SparkSession) -> None:
        print("\n[TEST] PII scan detects first_name column")
        df = spark.createDataFrame(
            [("Alice",)], ["first_name"]
        )
        print(f"  Column name: first_name")
        flagged = scan_for_pii_columns(df, "test", strict=False)
        print(f"  Flagged: {flagged}")
        print(f"  ✓ first_name column detected as PII")
        assert "first_name" in flagged

    def test_strict_mode_raises(self, spark: SparkSession) -> None:
        print("\n[TEST] Strict mode raises on PII detection")
        df = spark.createDataFrame(
            [("a@b.com",)], ["email"]
        )
        print(f"  Column name: email (PII)")
        print(f"  Mode: strict=True")
        with pytest.raises(PrivacyViolationError):
            scan_for_pii_columns(df, "test", strict=True)
        print(f"  ✓ PrivacyViolationError raised as expected")

    def test_multiple_pii_columns(self, spark: SparkSession) -> None:
        print("\n[TEST] PII scan detects multiple PII columns")
        df = spark.createDataFrame(
            [("a@b.com", "555-0100", "Alice")],
            ["email", "phone", "firstname"],
        )
        print(f"  Columns: {df.columns}")
        flagged = scan_for_pii_columns(df, "test", strict=False)
        print(f"  Flagged columns: {flagged}")
        print(f"  ✓ All 3 PII columns detected (email, phone, firstname)")
        assert len(flagged) == 3
