"""
Unit tests for GET /health

Rules:
  - Returns 200 + {"status": "healthy"} when the DB is reachable
  - Returns 503 when the DB is unreachable

All tests target the live ``app.py`` entrypoint (sync / psycopg2).
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from microservices.serving.recommendation_api.src.app import app


@pytest.fixture()
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_health_ok(client):
    """Health returns 200 + healthy when DB is reachable."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (1,)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    with patch(
        "microservices.serving.recommendation_api.src.routes.recommendations.get_connection",
    ) as mock_get_conn:
        mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        resp = client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"


def test_health_503_when_db_unreachable(client):
    """Health returns 503 when DB is down."""
    with patch(
        "microservices.serving.recommendation_api.src.routes.recommendations.get_connection",
        side_effect=ConnectionRefusedError("DB is down"),
    ):
        resp = client.get("/health")

    assert resp.status_code == 503
