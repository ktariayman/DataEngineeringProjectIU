"""
Recommendation API – route definitions.
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException, Query

from ..schemas import (
    RecommendationsResponse,
    RecommendationItem,
    StudentFeaturesResponse,
    HealthResponse,
)
from ..services.recommendation_service import get_recommendations, get_student_features
from ..services.database import get_connection

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check():
    """Liveness / readiness probe."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return HealthResponse(status="healthy")
    except Exception as exc:
        logger.error("[health] Database unreachable: %s", exc)
        raise HTTPException(status_code=503, detail="Database unreachable")


@router.get(
    "/recommendations/{user_id}",
    response_model=RecommendationsResponse,
    tags=["Recommendations"],
)
def fetch_recommendations(
    user_id: str,
    top_k: int = Query(default=10, ge=1, le=50, description="Number of recommendations"),
):
    """Return top-K similar users for a given student."""
    results = get_recommendations(user_id, top_k=top_k)
    if not results:
        raise HTTPException(status_code=404, detail=f"No recommendations found for user '{user_id}'.")
    return RecommendationsResponse(
        user_id=user_id,
        recommendations=[RecommendationItem(**r) for r in results],
        count=len(results),
    )


@router.get(
    "/students/{user_id}/features",
    response_model=StudentFeaturesResponse,
    tags=["Students"],
)
def fetch_student_features(user_id: str):
    """Return aggregated features for a given student."""
    features = get_student_features(user_id)
    if features is None:
        raise HTTPException(status_code=404, detail=f"No features found for user '{user_id}'.")
    return StudentFeaturesResponse(**features)
