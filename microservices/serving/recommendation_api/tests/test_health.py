"""
Unit tests for GET /health

Rules:
  - Always HTTP 200 (Reliability NFR)
  - Returns {"status": "ok", "db": "ok"} when DB is reachable
  - Returns {"status": "degraded", "db": "unavailable"} when DB probe fails
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from microservices.serving.recommendation_api.src.main import create_app


@pytest.fixture()
def client():
    app = create_app()
    # Skip lifespan (no real DB in unit tests)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_health_ok(client):
    """Health returns 200 + ok when DB pool probe succeeds."""
    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=1)
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "microservices.serving.recommendation_api.src.routes.health._pool",
        mock_pool,
    ):
        resp = client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"


def test_health_degraded_when_db_unreachable(client):
    """Health returns 200 (not 500) + degraded when DB is down."""
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(
        side_effect=ConnectionRefusedError("DB is down")
    )
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "microservices.serving.recommendation_api.src.routes.health._pool",
        mock_pool,
    ):
        resp = client.get("/health")

    assert resp.status_code == 200  # still 200 — Reliability NFR
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["db"] == "unavailable"


def test_health_degraded_when_pool_none(client):
    """Health returns degraded when pool has not been initialised yet."""
    with patch(
        "microservices.serving.recommendation_api.src.routes.health._pool",
        None,
    ):
        resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.json()["status"] == "degraded"
