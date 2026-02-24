"""
GET /v1/recommendations/me — main recommendation endpoint.

Contract (from architecture diagram):
  - Auth: Bearer JWT required (Security NFR)
  - Reads from PostgreSQL recommendations table (Serving Store)
  - Returns JSON (Privacy NFR: IDs + score only)
  - Graceful degradation: empty list on no rows — never 500 (Reliability NFR)
  - Scalability: queries hit ix_rec_user_date index (user_id, generation_date DESC)
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, Query

from microservices.serving.recommendation_api.src.schemas.recommendation import (
    RecommendationItem,
    RecommendationsResponse,
)
from microservices.serving.recommendation_api.src.services.auth import get_current_user
from microservices.serving.recommendation_api.src.services.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["recommendations"])

_MAX_LIMIT = 100
_DEFAULT_LIMIT = 20


@router.get(
    "/recommendations/me",
    response_model=RecommendationsResponse,
    summary="Get recommendations for the authenticated user",
    description=(
        "Returns the top-K precomputed collaborative-filtering recommendations "
        "for the currently authenticated learner. Results are ordered by similarity "
        "score descending. If no recommendations are available yet, returns an empty list."
    ),
)
async def get_my_recommendations(
    limit: int = Query(default=_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT, description="Max results to return"),
    generation_date: Optional[date] = Query(
        default=None,
        description="Filter by specific generation date (YYYY-MM-DD). Defaults to the most recent batch.",
    ),
    user_id: str = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
) -> RecommendationsResponse:
    """
    Retrieve recommendations for the requesting user.

    If generation_date is not specified, returns results from the most recent batch.
    """
    if generation_date is not None:
        # Specific date requested — fetch that exact batch
        rows = await db.fetch(
            """
            SELECT recommended_user_id, similarity_score, generation_date
            FROM   recommendations
            WHERE  user_id = $1
              AND  generation_date = $2
            ORDER  BY similarity_score DESC
            LIMIT  $3
            """,
            user_id,
            generation_date,
            limit,
        )
    else:
        # Default: return the latest batch (most recent generation_date)
        rows = await db.fetch(
            """
            SELECT recommended_user_id, similarity_score, generation_date
            FROM   recommendations
            WHERE  user_id = $1
              AND  generation_date = (
                  SELECT MAX(generation_date)
                  FROM   recommendations
                  WHERE  user_id = $1
              )
            ORDER  BY similarity_score DESC
            LIMIT  $2
            """,
            user_id,
            limit,
        )

    results = [
        RecommendationItem(
            recommended_user_id=row["recommended_user_id"],
            similarity_score=row["similarity_score"],
            generation_date=row["generation_date"],
        )
        for row in rows
    ]

    logger.info(
        "Served %d recommendations for user=%s generation_date=%s",
        len(results),
        user_id,
        results[0].generation_date if results else "N/A",
    )

    return RecommendationsResponse(
        user_id=user_id,
        count=len(results),
        results=results,
    )
