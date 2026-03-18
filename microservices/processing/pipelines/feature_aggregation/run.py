"""
Pipeline step 3 – Feature Aggregation.

Condenses per-interaction enriched rows into **one row per student**,
producing the ``aggregated_student_features`` dataset for the curated zone.

Architecture diagram: "Feature Aggregation → per-student aggregation,
                        accuracy, response time, activity metrics"
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from pyspark.sql import DataFrame

_project_root = str(Path(__file__).resolve().parents[4])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from microservices.processing.src.aggregator import (
    aggregate_student_features,
    filter_min_interactions,
)

logger = logging.getLogger(__name__)


def run_feature_aggregation(
    enriched_df: DataFrame,
    cfg: dict,
) -> DataFrame:
    """Execute the feature aggregation step.

    Parameters
    ----------
    enriched_df : DataFrame
        Enriched interactions (output of feature engineering step).
    cfg : dict
        Full processing config dict.

    Returns
    -------
    DataFrame
        One row per student with all aggregated features.
    """
    agg_cfg = cfg.get("feature_aggregation", {})
    min_interactions = agg_cfg.get("min_interactions", 5)

    # ── Aggregate to one row per user ────────────────────────────────
    aggregated = aggregate_student_features(enriched_df)

    # ── Filter low-activity students ─────────────────────────────────
    filtered = filter_min_interactions(aggregated, min_interactions)

    logger.info(
        "[feature_aggregation] Produced %d student feature rows.",
        filtered.count(),
    )
    return filtered
