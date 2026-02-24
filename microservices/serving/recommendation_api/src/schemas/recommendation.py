"""
Pydantic response models for the Recommendation API.

Privacy NFR: returns IDs + score only.
  - No names, emails, or raw interaction data ever leave this API.
  - 'user_id' and 'recommended_user_id' are anonymized EdNet identifiers.

Governance NFR: 'generation_date' always present so consumers know data freshness.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class RecommendationItem(BaseModel):
    """A single recommended user for the requesting learner."""

    recommended_user_id: str = Field(
        description="Anonymized ID of the similar learner being recommended."
    )
    similarity_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Cosine similarity score in [0, 1]. Higher = more similar learning path.",
    )
    generation_date: date = Field(
        description="UTC date when this recommendation batch was generated."
    )


class RecommendationsResponse(BaseModel):
    """Full response envelope for GET /v1/recommendations/me."""

    user_id: str = Field(description="The requesting user's anonymized ID.")
    count: int = Field(ge=0, description="Number of recommendations returned.")
    results: list[RecommendationItem] = Field(
        description="Ordered list of recommendations (highest similarity first)."
    )

    model_config = {"json_schema_extra": {
        "example": {
            "user_id": "u12345",
            "count": 3,
            "results": [
                {"recommended_user_id": "u67890", "similarity_score": 0.94, "generation_date": "2026-02-23"},
                {"recommended_user_id": "u11111", "similarity_score": 0.87, "generation_date": "2026-02-23"},
                {"recommended_user_id": "u22222", "similarity_score": 0.81, "generation_date": "2026-02-23"},
            ],
        }
    }}
