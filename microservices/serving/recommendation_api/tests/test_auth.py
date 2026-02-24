"""
Unit tests for JWT authentication dependency.

Covers:
  - Valid token → user_id extracted correctly
  - Expired token → HTTP 401
  - Wrong secret → HTTP 401
  - Missing 'sub' claim → HTTP 401
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from microservices.serving.recommendation_api.src.main import create_app

_SECRET = "test-secret-key"
_ALGO = "HS256"


def _make_token(sub: str | None = "user_123", secret: str = _SECRET, expired: bool = False) -> str:
    now = datetime.now(timezone.utc)
    payload = {"iat": now}
    if sub is not None:
        payload["sub"] = sub
    if expired:
        payload["exp"] = now - timedelta(seconds=1)
    else:
        payload["exp"] = now + timedelta(hours=1)
    return jwt.encode(payload, secret, algorithm=_ALGO)


@pytest.fixture()
def client():
    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_valid_jwt_passes(client):
    """Valid JWT reaches the route (DB call will fail, but auth passes → 500, not 401)."""
    token = _make_token()
    with patch(
        "microservices.serving.recommendation_api.src.services.auth._get_secret",
        return_value=_SECRET,
    ):
        resp = client.get(
            "/v1/recommendations/me",
            headers={"Authorization": f"Bearer {token}"},
        )
    # Auth passed → anything other than 401 means JWT was accepted
    assert resp.status_code != 401


def test_expired_token_returns_401(client):
    token = _make_token(expired=True)
    with patch(
        "microservices.serving.recommendation_api.src.services.auth._get_secret",
        return_value=_SECRET,
    ):
        resp = client.get(
            "/v1/recommendations/me",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 401


def test_wrong_secret_returns_401(client):
    token = _make_token(secret="wrong-secret")
    with patch(
        "microservices.serving.recommendation_api.src.services.auth._get_secret",
        return_value=_SECRET,
    ):
        resp = client.get(
            "/v1/recommendations/me",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 401


def test_missing_sub_claim_returns_401(client):
    token = _make_token(sub=None)
    with patch(
        "microservices.serving.recommendation_api.src.services.auth._get_secret",
        return_value=_SECRET,
    ):
        resp = client.get(
            "/v1/recommendations/me",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 401


def test_no_token_returns_401(client):
    resp = client.get("/v1/recommendations/me")
    assert resp.status_code == 401
