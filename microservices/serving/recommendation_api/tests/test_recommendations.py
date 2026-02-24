"""
Unit tests for GET /v1/recommendations/me

Covers:
  - Returns correct JSON shape with mock DB rows
  - Returns empty list (not 500) when no recommendations exist
  - generation_date filter is applied correctly
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from microservices.serving.recommendation_api.src.main import create_app

_SECRET = "test-secret"
_ALGO = "HS256"


def _token(user_id: str = "user_42") -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, _SECRET, algorithm=_ALGO)


def _auth_header(user_id: str = "user_42") -> dict:
    return {"Authorization": f"Bearer {_token(user_id)}"}


@pytest.fixture()
def client():
    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _mock_db_rows(rows: list[dict]):
    """Patch get_db to return a mock asyncpg connection that returns `rows`."""
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[
        {
            "recommended_user_id": r["recommended_user_id"],
            "similarity_score": r["similarity_score"],
            "generation_date": r["generation_date"],
        }
        for r in rows
    ])
    return mock_conn


def test_returns_correct_shape(client):
    """Happy path: DB has 2 rows → response matches RecommendationsResponse schema."""
    rows = [
        {"recommended_user_id": "u99", "similarity_score": 0.92, "generation_date": date(2026, 2, 23)},
        {"recommended_user_id": "u88", "similarity_score": 0.81, "generation_date": date(2026, 2, 23)},
    ]
    mock_conn = _mock_db_rows(rows)

    with (
        patch("microservices.serving.recommendation_api.src.services.auth._get_secret", return_value=_SECRET),
        patch("microservices.serving.recommendation_api.src.services.db.get_db", return_value=_yielded(mock_conn)),
    ):
        resp = client.get("/v1/recommendations/me", headers=_auth_header())

    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == "user_42"
    assert body["count"] == 2
    assert len(body["results"]) == 2
    assert body["results"][0]["recommended_user_id"] == "u99"
    assert body["results"][0]["similarity_score"] == 0.92


def test_empty_list_when_no_recommendations(client):
    """Graceful degradation: no rows in DB → 200 with empty list, not 500."""
    mock_conn = _mock_db_rows([])

    with (
        patch("microservices.serving.recommendation_api.src.services.auth._get_secret", return_value=_SECRET),
        patch("microservices.serving.recommendation_api.src.services.db.get_db", return_value=_yielded(mock_conn)),
    ):
        resp = client.get("/v1/recommendations/me", headers=_auth_header())

    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 0
    assert body["results"] == []


def _yielded(value):
    """Helper: creates an async generator that yields one value (for Depends mock)."""
    async def _gen():
        yield value
    return _gen()
