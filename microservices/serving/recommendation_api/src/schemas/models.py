"""
Pydantic response schemas for the Recommendation API.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class RecommendationItem(BaseModel):
    """A single recommendation entry."""
    recommended_user_id: str
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    rank: int = Field(..., ge=1)


class RecommendationsResponse(BaseModel):
    """Response for GET /recommendations/{user_id}."""
    user_id: str
    recommendations: list[RecommendationItem]
    count: int


class StudentFeaturesResponse(BaseModel):
    """Response for GET /students/{user_id}/features."""
    user_id: str
    total_interactions: Optional[int] = None
    correct_count: Optional[int] = None
    incorrect_count: Optional[int] = None
    accuracy_rate: Optional[float] = None
    avg_response_time_ms: Optional[float] = None
    total_elapsed_time_ms: Optional[int] = None
    unique_questions_attempted: Optional[int] = None
    unique_lectures_viewed: Optional[int] = None
    active_days: Optional[int] = None


class HealthResponse(BaseModel):
    """Response for GET /health."""
    status: str
    service: str = "recommendation-api"


class ErrorResponse(BaseModel):
    """Generic error response."""
    detail: str
