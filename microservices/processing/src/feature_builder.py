"""
Feature engineering for the processing microservice.

Transforms raw EdNet KT4 interactions into enriched feature rows by:
  1. Joining with questions metadata to determine correctness.
  2. Computing ``is_correct`` (binary) for "respond" actions.
  3. Capping outlier response times.
  4. Extracting temporal features (hour_of_day, day_of_week).

Architecture diagram: "Feature Engineering → is_correct, response_time,
                        action_type, part, time features"
"""

from __future__ import annotations

import logging

from pyspark.sql import DataFrame
from pyspark.sql.functions import (
    col,
    dayofweek,
    from_unixtime,
    hour,
    lit,
    when,
)

logger = logging.getLogger(__name__)


def enrich_interactions(
    kt4_df: DataFrame,
    questions_df: DataFrame,
    correctness_join: bool = True,
    time_features: bool = True,
    response_time_cap_ms: int = 300_000,
) -> DataFrame:
    """Enrich raw KT4 interactions with derived feature columns.

    Parameters
    ----------
    kt4_df : DataFrame
        Raw KT4 interactions (user_id, timestamp, action_type, item_id,
        source, user_answer, platform, elapsed_time, event_date).
    questions_df : DataFrame
        Questions metadata (question_id, correct_answer, part, …).
    correctness_join : bool
        Whether to join with ``questions_df`` for correctness labelling.
    time_features : bool
        Whether to extract hour_of_day / day_of_week from timestamp.
    response_time_cap_ms : int
        Maximum response time in milliseconds; values above are capped.

    Returns
    -------
    DataFrame
        Enriched DataFrame with additional columns: ``correct_answer``,
        ``part``, ``is_correct``, ``response_time_ms``, ``hour_of_day``,
        ``day_of_week``.
    """
    df = kt4_df.alias("kt4")

    # ── 1. Join with questions for correct_answer + part ─────────────
    if correctness_join:
        q = questions_df.select(
            col("question_id"),
            col("correct_answer"),
            col("part"),
        ).alias("q")

        df = df.join(
            q,
            col("kt4.item_id") == col("q.question_id"),
            how="left",
        ).select(
            "kt4.*",
            col("q.correct_answer"),
            col("q.part"),
        )
    else:
        df = df.withColumn("correct_answer", lit(None))
        df = df.withColumn("part", lit(None))

    # ── 2. Compute is_correct (only for "respond" actions) ───────────
    df = df.withColumn(
        "is_correct",
        when(
            (col("action_type") == "respond") & col("correct_answer").isNotNull(),
            when(col("user_answer") == col("correct_answer"), lit(1)).otherwise(lit(0)),
        ).otherwise(lit(None)).cast("int"),
    )

    # ── 3. Cap response time ─────────────────────────────────────────
    df = df.withColumn(
        "response_time_ms",
        when(
            col("elapsed_time").isNotNull(),
            when(
                col("elapsed_time") > response_time_cap_ms,
                lit(response_time_cap_ms),
            ).otherwise(col("elapsed_time")),
        ).otherwise(lit(None)).cast("long"),
    )

    # ── 4. Time features ─────────────────────────────────────────────
    if time_features:
        ts_col = from_unixtime(col("timestamp") / 1000)
        df = df.withColumn("hour_of_day", hour(ts_col).cast("int"))
        df = df.withColumn("day_of_week", dayofweek(ts_col).cast("int"))
    else:
        df = df.withColumn("hour_of_day", lit(None).cast("int"))
        df = df.withColumn("day_of_week", lit(None).cast("int"))

    logger.info(
        "[feature_engineering] Enriched interactions: %d columns",
        len(df.columns),
    )
    return df


def cap_response_time(df: DataFrame, cap_ms: int = 300_000) -> DataFrame:
    """Cap ``elapsed_time`` values to ``cap_ms`` (standalone utility).

    Useful when called outside the full enrichment pipeline.
    """
    return df.withColumn(
        "elapsed_time",
        when(
            col("elapsed_time") > cap_ms,
            lit(cap_ms),
        ).otherwise(col("elapsed_time")),
    )
