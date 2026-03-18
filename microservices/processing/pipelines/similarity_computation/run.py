"""
Pipeline step 4 – Similarity Computation.

Builds normalised user feature vectors, computes pairwise cosine
similarity, and produces top-K recommendation lists per student.

Architecture diagram: "Similarity Computation → normalise features,
                        cosine similarity, top-K ranking"
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from pyspark.sql import DataFrame

_project_root = str(Path(__file__).resolve().parents[4])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from microservices.processing.src.similarity import build_recommendations

logger = logging.getLogger(__name__)


def run_similarity_computation(
    aggregated_df: DataFrame,
    cfg: dict,
) -> tuple[DataFrame, DataFrame]:
    """Execute the similarity computation step.

    Parameters
    ----------
    aggregated_df : DataFrame
        Aggregated student features (one row per user).
    cfg : dict
        Full processing config dict.

    Returns
    -------
    tuple[DataFrame, DataFrame]
        ``(user_vectors, recommendations_batch)``
    """
    sim_cfg = cfg.get("similarity", {})
    feature_columns = sim_cfg.get("feature_columns", [
        "accuracy_rate",
        "avg_response_time_ms",
        "total_interactions",
        "unique_questions_attempted",
        "unique_lectures_viewed",
        "active_days",
    ])
    top_k = sim_cfg.get("top_k", 10)

    user_vectors, recommendations = build_recommendations(
        aggregated_features=aggregated_df,
        feature_columns=feature_columns,
        top_k=top_k,
    )

    logger.info(
        "[similarity_computation] user_vectors=%d rows, recommendations=%d rows.",
        user_vectors.count(),
        recommendations.count(),
    )
    return user_vectors, recommendations
