"""
Feature aggregation for the processing microservice.

Aggregates enriched per-interaction rows into **one row per student**,
producing the ``aggregated_student_features`` curated-zone dataset.

Computed features:
  - total_interactions          – count of all KT4 rows
  - correct_count               – sum(is_correct) where is_correct IS NOT NULL
  - incorrect_count             – respond rows minus correct_count
  - accuracy_rate               – correct_count / respond_count
  - avg_response_time_ms        – mean response time for "respond" actions
  - total_elapsed_time_ms       – sum of all elapsed_time
  - unique_questions_attempted  – distinct item_ids with action_type="respond"
  - unique_lectures_viewed      – distinct item_ids with action_type="enter"
  - active_days                 – distinct event_date values
  - interactions_part_N         – interaction count per TOEIC part (1–7)

Architecture diagram: "Feature Aggregation → per-student feature vector"
"""

from __future__ import annotations

import logging

from pyspark.sql import DataFrame
from pyspark.sql.functions import (
    avg,
    col,
    count,
    countDistinct,
    lit,
    sum as _sum,
    when,
)

logger = logging.getLogger(__name__)


def aggregate_student_features(df: DataFrame) -> DataFrame:
    """Aggregate enriched interactions into one row per student.

    Parameters
    ----------
    df : DataFrame
        Enriched interactions (output of :func:`enrich_interactions`).
        Must contain: user_id, action_type, item_id, elapsed_time,
        event_date, is_correct, response_time_ms, part.

    Returns
    -------
    DataFrame
        One row per ``user_id`` with all aggregated features.
    """
    respond_filter = col("action_type") == "respond"
    enter_filter = col("action_type") == "enter"

    agg_df = df.groupBy("user_id").agg(
        # Total interactions
        count("*").alias("total_interactions"),

        # Correctness
        _sum(
            when(col("is_correct") == 1, lit(1)).otherwise(lit(0))
        ).alias("correct_count"),
        _sum(
            when(
                respond_filter & (col("is_correct") == 0),
                lit(1),
            ).otherwise(lit(0))
        ).alias("incorrect_count"),

        # Accuracy  (correct / respond_count) — computed below
        _sum(when(respond_filter, lit(1)).otherwise(lit(0))).alias("_respond_count"),

        # Response time
        avg(
            when(respond_filter, col("response_time_ms"))
        ).alias("avg_response_time_ms"),

        # Total elapsed time
        _sum(col("elapsed_time")).alias("total_elapsed_time_ms"),

        # Distinct counts
        countDistinct(
            when(respond_filter, col("item_id"))
        ).alias("unique_questions_attempted"),
        countDistinct(
            when(enter_filter, col("item_id"))
        ).alias("unique_lectures_viewed"),
        countDistinct(col("event_date")).alias("active_days"),

        # Per-part interactions (TOEIC parts 1–7)
        *[
            _sum(
                when(col("part") == part_num, lit(1)).otherwise(lit(0))
            ).alias(f"interactions_part_{part_num}")
            for part_num in range(1, 8)
        ],
    )

    # Derive accuracy_rate avoiding division by zero
    agg_df = agg_df.withColumn(
        "accuracy_rate",
        when(
            col("_respond_count") > 0,
            col("correct_count") / col("_respond_count"),
        ).otherwise(lit(0.0)),
    ).drop("_respond_count")

    logger.info(
        "[feature_aggregation] Aggregated features for students. Columns: %s",
        agg_df.columns,
    )
    return agg_df


def filter_min_interactions(
    df: DataFrame,
    min_interactions: int = 5,
) -> DataFrame:
    """Remove students with fewer than *min_interactions* total rows.

    Parameters
    ----------
    df : DataFrame
        Aggregated student features (must contain ``total_interactions``).
    min_interactions : int
        Minimum threshold.

    Returns
    -------
    DataFrame
        Filtered DataFrame.
    """
    before = df.count()
    filtered = df.filter(col("total_interactions") >= min_interactions)
    after = filtered.count()
    dropped = before - after
    logger.info(
        "[feature_aggregation] Filtered students: %d → %d (dropped %d with < %d interactions).",
        before, after, dropped, min_interactions,
    )
    return filtered
