"""
Unit tests for JWT authentication dependency.

Covers:
  - Valid token → user_id extracted correctly
  - Expired token → HTTP 401
  - Wrong secret → HTTP 401
  - Missing 'sub' claim → HTTP 401
  - No token at all → HTTP 401

All tests target the live ``app.py`` entrypoint (sync / psycopg2).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from microservices.serving.recommendation_api.src.app import app

_SECRET = "test-secret-key"
_ALGO = "HS256"


def _make_token(
    sub: str | None = "u1",
    secret: str = _SECRET,
    expired: bool = False,
) -> str:
    """Create a test JWT."""
    now = datetime.now(timezone.utc)
    payload: dict = {"iat": now}
    if sub is not None:
        payload["sub"] = sub
    if expired:
        payload["exp"] = now - timedelta(seconds=1)
    else:
        payload["exp"] = now + timedelta(hours=1)
    return jwt.encode(payload, secret, algorithm=_ALGO)


@pytest.fixture()
def client():
    """TestClient wrapping the live FastAPI app."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_valid_jwt_passes(client):
    """Valid JWT reaches the route — auth succeeds (not 401)."""
    token = _make_token(sub="u1")

    # Mock psycopg2 connection so we don't need a real DB
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [("u2", 0.92, 1)]
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

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
        resp = client.get(
            "/recommendations/u1",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code != 401


def test_expired_token_returns_401(client):
    """Expired JWT returns 401."""
    token = _make_token(expired=True)
    with patch(
        "microservices.serving.recommendation_api.src.services.auth._get_secret",
        return_value=_SECRET,
    ):
        resp = client.get(
            "/recommendations/u1",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 401


def test_wrong_secret_returns_401(client):
    """JWT signed with a different secret returns 401."""
    token = _make_token(secret="wrong-secret")
    with patch(
        "microservices.serving.recommendation_api.src.services.auth._get_secret",
        return_value=_SECRET,
    ):
        resp = client.get(
            "/recommendations/u1",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 401


def test_missing_sub_claim_returns_401(client):
    """JWT without a 'sub' claim returns 401."""
    token = _make_token(sub=None)
    with patch(
        "microservices.serving.recommendation_api.src.services.auth._get_secret",
        return_value=_SECRET,
    ):
        resp = client.get(
            "/recommendations/u1",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 401


def test_no_token_returns_401(client):
    """Request without Authorization header returns 401."""
    resp = client.get("/recommendations/u1")
    assert resp.status_code == 401
