"""
User similarity computation for the processing microservice.

Computes cosine similarity between student feature vectors and produces
a top-K recommendation list per student.

Architecture diagram: "Similarity Computation → cosine similarity,
                        top-K recommendations per student"

Algorithm
---------
1. Normalise each feature column to [0, 1] using min-max scaling.
2. Self-join the normalised vectors table (user_a × user_b, a < b).
3. Compute cosine similarity as:
       dot(a, b) / (||a|| × ||b||)
   Since features are already non-negative after min-max, this is
   well-defined.
4. Rank similarities per user and keep top-K.
"""

from __future__ import annotations

import logging
from typing import List

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════
# Min-max normalisation
# ══════════════════════════════════════════════════════════════════════════

def normalize_features(
    df: DataFrame,
    feature_columns: List[str],
) -> DataFrame:
    """Min-max normalise the specified feature columns to [0, 1].

    Parameters
    ----------
    df : DataFrame
        Must contain ``user_id`` and all ``feature_columns``.
    feature_columns : list[str]
        Columns to normalise.

    Returns
    -------
    DataFrame
        DataFrame with normalised feature columns (suffixed ``_norm``) and
        the original ``user_id``.
    """
    result = df.select("user_id", *feature_columns)

    for c in feature_columns:
        min_val = result.agg(F.min(c)).head()[0]
        max_val = result.agg(F.max(c)).head()[0]
        range_val = (max_val or 0) - (min_val or 0)

        if range_val == 0:
            result = result.withColumn(f"{c}_norm", F.lit(0.0))
        else:
            result = result.withColumn(
                f"{c}_norm",
                ((F.col(c) - F.lit(min_val)) / F.lit(range_val)).cast("double"),
            )

    # Keep only user_id and normalised columns
    norm_cols = [f"{c}_norm" for c in feature_columns]
    result = result.select("user_id", *norm_cols)
    logger.info(
        "[similarity] Normalised %d feature(s) for %d users.",
        len(feature_columns), result.count(),
    )
    return result


# ══════════════════════════════════════════════════════════════════════════
# Cosine similarity
# ══════════════════════════════════════════════════════════════════════════

def compute_cosine_similarity(
    df: DataFrame,
    feature_columns: List[str],
) -> DataFrame:
    """Compute pairwise cosine similarity between all user pairs.

    Parameters
    ----------
    df : DataFrame
        Normalised feature vectors (columns: user_id, <feat>_norm …).
    feature_columns : list[str]
        Original feature column names (will look for ``<name>_norm``).

    Returns
    -------
    DataFrame
        Columns: ``user_id``, ``other_user_id``, ``similarity_score``.
    """
    norm_cols = [f"{c}_norm" for c in feature_columns]

    a = df.alias("a")
    b = df.alias("b")

    # Self-join with a < b to avoid duplicates and self-pairs
    pairs = a.join(b, F.col("a.user_id") < F.col("b.user_id"))

    # dot(a, b)
    dot_expr = sum(
        F.col(f"a.{nc}") * F.col(f"b.{nc}") for nc in norm_cols
    )

    # ||a|| and ||b||
    mag_a = F.sqrt(sum(F.col(f"a.{nc}") ** 2 for nc in norm_cols))
    mag_b = F.sqrt(sum(F.col(f"b.{nc}") ** 2 for nc in norm_cols))

    similarity = pairs.select(
        F.col("a.user_id").alias("user_id"),
        F.col("b.user_id").alias("other_user_id"),
        F.when(
            (mag_a > 0) & (mag_b > 0),
            (dot_expr / (mag_a * mag_b)),
        ).otherwise(F.lit(0.0)).alias("similarity_score"),
    )

    # Mirror the pairs so every user appears in the user_id column
    mirrored = similarity.select(
        F.col("other_user_id").alias("user_id"),
        F.col("user_id").alias("other_user_id"),
        F.col("similarity_score"),
    )

    full = similarity.unionByName(mirrored)

    logger.info("[similarity] Computed pairwise cosine similarity.")
    return full


# ══════════════════════════════════════════════════════════════════════════
# Top-K ranking
# ══════════════════════════════════════════════════════════════════════════

def get_top_k_recommendations(
    similarity_df: DataFrame,
    top_k: int = 10,
) -> DataFrame:
    """Rank similar users per student and keep only the top-K.

    Parameters
    ----------
    similarity_df : DataFrame
        Columns: ``user_id``, ``other_user_id``, ``similarity_score``.
    top_k : int
        Number of recommendations per user.

    Returns
    -------
    DataFrame
        Columns: ``user_id``, ``recommended_user_id``, ``similarity_score``,
        ``rank``.
    """
    window = Window.partitionBy("user_id").orderBy(
        F.col("similarity_score").desc()
    )

    ranked = similarity_df.withColumn("rank", F.row_number().over(window))
    top = ranked.filter(F.col("rank") <= top_k)

    result = top.select(
        F.col("user_id"),
        F.col("other_user_id").alias("recommended_user_id"),
        F.col("similarity_score"),
        F.col("rank").cast("int"),
    )

    logger.info(
        "[similarity] Top-%d recommendations generated.", top_k,
    )
    return result


# ══════════════════════════════════════════════════════════════════════════
# Convenience orchestrator
# ══════════════════════════════════════════════════════════════════════════

def build_recommendations(
    aggregated_features: DataFrame,
    feature_columns: List[str],
    top_k: int = 10,
) -> tuple[DataFrame, DataFrame]:
    """End-to-end: normalise → cosine similarity → top-K.

    Returns
    -------
    tuple[DataFrame, DataFrame]
        (user_vectors, recommendations_batch)  — both ready for curated zone.
    """
    user_vectors = normalize_features(aggregated_features, feature_columns)
    similarity = compute_cosine_similarity(user_vectors, feature_columns)
    recommendations = get_top_k_recommendations(similarity, top_k)
    return user_vectors, recommendations
