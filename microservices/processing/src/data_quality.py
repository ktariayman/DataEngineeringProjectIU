"""
Data quality validation for the processing microservice.

Reliability guarantee: every curated-zone output is validated before being
persisted, ensuring downstream consumers (serving layer, analytics) receive
structurally sound data.

Checks performed:
  1. Required columns present
  2. Minimum row count
  3. Null-ratio within threshold
  4. No duplicate primary keys
"""

from __future__ import annotations

import logging
from typing import Optional

from pyspark.sql import DataFrame
from pyspark.sql.functions import col, isnan
from pyspark.sql.types import DoubleType, FloatType

logger = logging.getLogger(__name__)


class DataQualityError(Exception):
    """Raised when a processed DataFrame fails quality validation."""


class DataQualityValidator:
    """Validate processed DataFrames before writing to curated zone."""

    def __init__(
        self,
        max_null_ratio: float = 0.10,
        min_row_count: int = 1,
        required_columns: Optional[dict[str, list[str]]] = None,
    ) -> None:
        self.max_null_ratio = max_null_ratio
        self.min_row_count = min_row_count
        self.required_columns = required_columns or {}

    def validate(
        self,
        df: DataFrame,
        dataset_name: str,
        primary_key: str = "user_id",
    ) -> DataFrame:
        """Run all quality checks on a processed DataFrame.

        Parameters
        ----------
        df : DataFrame
            The DataFrame to validate.
        dataset_name : str
            Logical name for error messages (e.g. ``aggregated_student_features``).
        primary_key : str
            Column to check for uniqueness.

        Returns
        -------
        DataFrame
            The validated (unchanged) DataFrame.

        Raises
        ------
        DataQualityError
            If any check fails.
        """
        logger.info("[data_quality] Validating '%s' …", dataset_name)

        self._check_required_columns(df, dataset_name)
        self._check_row_count(df, dataset_name)
        self._check_null_ratio(df, dataset_name)
        pk_cols = [primary_key] if isinstance(primary_key, str) else list(primary_key)
        if all(c in df.columns for c in pk_cols):
            self._check_duplicates(df, dataset_name, pk_cols)

        logger.info("[data_quality] '%s' passed all quality checks.", dataset_name)
        return df

    def _check_required_columns(self, df: DataFrame, dataset_name: str) -> None:
        expected = set(self.required_columns.get(dataset_name, []))
        actual = set(df.columns)
        missing = expected - actual
        if missing:
            raise DataQualityError(
                f"[{dataset_name}] Missing required columns: {sorted(missing)}"
            )

    def _check_row_count(self, df: DataFrame, dataset_name: str) -> None:
        count = df.count()
        if count < self.min_row_count:
            raise DataQualityError(
                f"[{dataset_name}] Row count {count} < minimum {self.min_row_count}"
            )
        logger.info("[data_quality] [%s] Row count: %d", dataset_name, count)

    def _check_null_ratio(self, df: DataFrame, dataset_name: str) -> None:
        required = self.required_columns.get(dataset_name, [])
        if not required:
            return

        total = df.count()
        if total == 0:
            return

        for col_name in required:
            if col_name not in df.columns:
                continue
            field = df.schema[col_name]
            # NaN applies to floating types; for integer-like types
            # we only need SQL NULL checks.
            if isinstance(field.dataType, (FloatType, DoubleType)):
                null_count = df.filter(
                    col(col_name).isNull() | isnan(col(col_name))
                ).count()
            else:
                null_count = df.filter(col(col_name).isNull()).count()
            ratio = null_count / total
            if ratio > self.max_null_ratio:
                raise DataQualityError(
                    f"[{dataset_name}] Column '{col_name}' null ratio "
                    f"{ratio:.2%} exceeds threshold {self.max_null_ratio:.2%}"
                )
            logger.info(
                "[data_quality] [%s] Column '%s' null ratio: %.2f%%",
                dataset_name, col_name, ratio * 100,
            )

    @staticmethod
    def _check_duplicates(
        df: DataFrame,
        dataset_name: str,
        primary_key: list,
    ) -> None:
        """Ensure no duplicate rows across the primary key column(s)."""
        total = df.count()
        distinct = df.select(*primary_key).distinct().count()
        duplicates = total - distinct
        if duplicates > 0:
            raise DataQualityError(
                f"[{dataset_name}] Found {duplicates} duplicate(s) "
                f"in primary key {primary_key}"
            )
        logger.info(
            "[data_quality] [%s] No duplicates in %s.",
            dataset_name, primary_key,
        )
