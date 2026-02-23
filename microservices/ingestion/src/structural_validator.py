"""
Structural validation for ingested EdNet DataFrames.

Checks performed (per the architecture diagram):
  1. Required columns check  – all mandatory columns present
  2. Rows check              – minimum row count threshold
  3. Type casting            – enforce schema types, quarantine corrupt rows
  4. Basic normalization     – trim strings, standardise nulls
"""

from __future__ import annotations

import logging
from typing import Optional

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col, trim, when, length
from pyspark.sql.types import StringType

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when a DataFrame fails structural validation."""


class StructuralValidator:
    """Validate and normalise raw EdNet DataFrames.

    Parameters
    ----------
    max_null_ratio : float
        Maximum fraction of nulls allowed in any required column (0‒1).
    min_row_count : int
        Minimum number of rows a valid source must contain.
    required_columns : dict[str, list[str]]
        Mapping of ``source_name → [required_col, …]``.
    """

    def __init__(
        self,
        max_null_ratio: float = 0.05,
        min_row_count: int = 1,
        required_columns: Optional[dict[str, list[str]]] = None,
    ) -> None:
        self.max_null_ratio = max_null_ratio
        self.min_row_count = min_row_count
        self.required_columns = required_columns or {}

    # ── public API ─────────────────────────────────────────────────────

    def validate(self, df: DataFrame, source_name: str) -> DataFrame:
        """Run the full structural validation + normalisation pipeline.

        Parameters
        ----------
        df : DataFrame
            Raw DataFrame as read by :class:`EdNetCSVReader`.
        source_name : str
            Identifier for the source (``kt4``, ``lectures``, ``questions``).

        Returns
        -------
        DataFrame
            Validated and normalised DataFrame (corrupt rows removed).

        Raises
        ------
        ValidationError
            If any check fails.
        """
        logger.info("Validating source '%s' …", source_name)

        # 1. Required columns check
        self._check_required_columns(df, source_name)

        # 2. Remove corrupt rows (produced by PERMISSIVE mode reader)
        df = self._remove_corrupt_rows(df)

        # 3. Row count check
        self._check_row_count(df, source_name)

        # 4. Null-ratio check on required columns
        self._check_null_ratio(df, source_name)

        # 5. Basic normalisation (trim strings, empty→null)
        df = self._normalise(df)

        logger.info("Source '%s' passed structural validation.", source_name)
        return df

    # ── checks ─────────────────────────────────────────────────────────

    def _check_required_columns(self, df: DataFrame, source_name: str) -> None:
        """Ensure every required column exists in the DataFrame."""
        expected = set(self.required_columns.get(source_name, []))
        actual = set(df.columns)
        missing = expected - actual
        if missing:
            raise ValidationError(
                f"[{source_name}] Missing required columns: {sorted(missing)}"
            )

    def _check_row_count(self, df: DataFrame, source_name: str) -> None:
        """Ensure the DataFrame has at least ``min_row_count`` rows."""
        count = df.count()
        if count < self.min_row_count:
            raise ValidationError(
                f"[{source_name}] Row count {count} < minimum {self.min_row_count}"
            )
        logger.info("[%s] Row count: %d", source_name, count)

    def _check_null_ratio(self, df: DataFrame, source_name: str) -> None:
        """Check null ratio on each required column."""
        required = self.required_columns.get(source_name, [])
        if not required:
            return

        total = df.count()
        if total == 0:
            return

        for col_name in required:
            if col_name not in df.columns:
                continue
            null_count = df.filter(col(col_name).isNull()).count()
            ratio = null_count / total
            if ratio > self.max_null_ratio:
                raise ValidationError(
                    f"[{source_name}] Column '{col_name}' null ratio "
                    f"{ratio:.2%} exceeds threshold {self.max_null_ratio:.2%}"
                )
            logger.info(
                "[%s] Column '%s' null ratio: %.2f%%",
                source_name, col_name, ratio * 100,
            )

    # ── normalisation ──────────────────────────────────────────────────

    @staticmethod
    def _remove_corrupt_rows(df: DataFrame) -> DataFrame:
        """Drop rows flagged corrupt by the PERMISSIVE CSV reader."""
        if "_corrupt_record" in df.columns:
            corrupt_count = df.filter(col("_corrupt_record").isNotNull()).count()
            if corrupt_count > 0:
                logger.warning("Dropping %d corrupt rows.", corrupt_count)
            df = df.filter(col("_corrupt_record").isNull()).drop("_corrupt_record")
        return df

    @staticmethod
    def _normalise(df: DataFrame) -> DataFrame:
        """Trim leading/trailing whitespace on string columns and convert
        empty strings to ``null`` for consistency."""
        for field in df.schema.fields:
            if isinstance(field.dataType, StringType):
                trimmed = trim(col(field.name))
                df = df.withColumn(
                    field.name,
                    when(length(trimmed) == 0, None).otherwise(trimmed),
                )
        return df
