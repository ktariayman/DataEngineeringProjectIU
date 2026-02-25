"""
Pipeline step 2 – Feature Engineering.

Enriches raw KT4 interactions with derived features:
  - is_correct (correctness label from questions join)
  - response_time_ms (capped elapsed_time)
  - hour_of_day, day_of_week (temporal features)
  - part (from questions metadata join)

Architecture diagram: "Feature Engineering → Join interactions +
                        questions, compute is_correct, time features"
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from pyspark.sql import DataFrame

_project_root = str(Path(__file__).resolve().parents[4])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from microservices.processing.src.feature_builder import enrich_interactions

logger = logging.getLogger(__name__)


def run_feature_engineering(
    dataframes: dict[str, DataFrame],
    cfg: dict,
) -> DataFrame:
    """Execute the feature engineering step.

    Parameters
    ----------
    dataframes : dict[str, DataFrame]
        Must contain ``kt4`` and ``questions``.
    cfg : dict
        Full processing config dict.

    Returns
    -------
    DataFrame
        Enriched interactions with derived feature columns.
    """
    kt4_df = dataframes["kt4"]
    questions_df = dataframes["questions"]

    fe_cfg = cfg.get("feature_engineering", {})

    enriched = enrich_interactions(
        kt4_df=kt4_df,
        questions_df=questions_df,
        correctness_join=fe_cfg.get("correctness_join", True),
        time_features=fe_cfg.get("time_features", True),
        response_time_cap_ms=fe_cfg.get("response_time_cap_ms", 300_000),
    )

    logger.info(
        "[feature_engineering] Enriched %d columns for downstream aggregation.",
        len(enriched.columns),
    )
    return enriched
