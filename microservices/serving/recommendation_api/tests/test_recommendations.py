"""
Unit tests for GET /recommendations/{user_id}

Covers:
  - Correct JSON shape with mock DB rows
  - 404 when no recommendations exist
  - 403 when requesting another user's recommendations

All tests target the live ``app.py`` entrypoint (sync / psycopg2).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from microservices.serving.recommendation_api.src.app import app

_SECRET = "test-secret"
_ALGO = "HS256"


def _token(user_id: str = "u1") -> str:
    """Create a test JWT for the given user."""
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, _SECRET, algorithm=_ALGO)


def _auth_header(user_id: str = "u1") -> dict:
    return {"Authorization": f"Bearer {_token(user_id)}"}


@pytest.fixture()
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _mock_db_connection(rows: list[tuple]):
    """Return a mock psycopg2 connection that returns ``rows`` from fetchall."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = rows
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn


def test_returns_correct_shape(client):
    """Happy path: DB has 2 rows → response matches RecommendationsResponse."""
    rows = [
        ("u99", 0.92, 1),
        ("u88", 0.81, 2),
    ]
    mock_conn = _mock_db_connection(rows)

    with (
        patch(
            "microservices.serving.recommendation_api.src.services.auth._get_secret",
            return_value=_SECRET,
        ),
        patch(
            "microservices.serving.recommendation_api.src.services.database.get_connection",
        ) as mock_get_conn,
    ):
        mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        resp = client.get("/recommendations/u1", headers=_auth_header("u1"))

    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == "u1"
    assert body["count"] == 2
    assert len(body["recommendations"]) == 2
    assert body["recommendations"][0]["recommended_user_id"] == "u99"
    assert body["recommendations"][0]["similarity_score"] == 0.92
    assert body["recommendations"][0]["rank"] == 1


def test_404_when_no_recommendations(client):
    """No rows in DB → 404 (user has no recommendations)."""
    mock_conn = _mock_db_connection([])

    with (
        patch(
            "microservices.serving.recommendation_api.src.services.auth._get_secret",
            return_value=_SECRET,
        ),
        patch(
            "microservices.serving.recommendation_api.src.services.database.get_connection",
        ) as mock_get_conn,
    ):
        mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        resp = client.get("/recommendations/u1", headers=_auth_header("u1"))

    assert resp.status_code == 404


def test_403_when_accessing_other_users_data(client):
    """User u1 cannot fetch recommendations for u99 → 403."""
    with patch(
        "microservices.serving.recommendation_api.src.services.auth._get_secret",
        return_value=_SECRET,
    ):
        resp = client.get("/recommendations/u99", headers=_auth_header("u1"))

    assert resp.status_code == 403
