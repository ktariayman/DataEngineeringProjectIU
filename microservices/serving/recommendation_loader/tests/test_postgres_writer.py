"""
Unit tests for postgres_writer — idempotency focus.

Verifies that:
  - Running write_recommendations twice with the same rows does NOT duplicate them
    (ON CONFLICT DO UPDATE behaviour)
  - Initial mode truncates before writing
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, call, patch

import pytest

from microservices.serving.recommendation_loader.src.postgres_writer import write_recommendations


def _rows(n: int = 3) -> list[dict]:
    return [
        {
            "user_id": f"u{i}",
            "recommended_user_id": f"r{i}",
            "similarity_score": 0.9 - i * 0.1,
            "generation_date": date(2026, 2, 23),
        }
        for i in range(n)
    ]


@pytest.fixture()
def mock_conn():
    """Mock psycopg2 connection + cursor."""
    mock_cur = MagicMock()
    mock_cursor_ctx = MagicMock()
    mock_cursor_ctx.__enter__ = MagicMock(return_value=mock_cur)
    mock_cursor_ctx.__exit__ = MagicMock(return_value=False)

    conn = MagicMock()
    conn.cursor.return_value = mock_cursor_ctx
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    return conn, mock_cur


def test_daily_mode_uses_upsert(mock_conn):
    """Daily mode calls execute_values with ON CONFLICT clause (no TRUNCATE)."""
    conn, cur = mock_conn
    with (
        patch("microservices.serving.recommendation_loader.src.postgres_writer._get_conn", return_value=conn),
        patch("microservices.serving.recommendation_loader.src.postgres_writer.psycopg2.extras.execute_values") as mock_ev,
    ):
        total = write_recommendations(_rows(3), mode="daily")

    assert total == 3
    # execute_values called once (one batch of 3)
    assert mock_ev.call_count == 1
    # No TRUNCATE in daily mode
    truncate_calls = [c for c in cur.execute.call_args_list if "TRUNCATE" in str(c)]
    assert len(truncate_calls) == 0


def test_initial_mode_truncates_first(mock_conn):
    """Initial mode calls TRUNCATE before inserting."""
    conn, cur = mock_conn
    with (
        patch("microservices.serving.recommendation_loader.src.postgres_writer._get_conn", return_value=conn),
        patch("microservices.serving.recommendation_loader.src.postgres_writer.psycopg2.extras.execute_values"),
    ):
        write_recommendations(_rows(2), mode="initial")

    truncate_calls = [c for c in cur.execute.call_args_list if "TRUNCATE" in str(c)]
    assert len(truncate_calls) == 1


def test_invalid_mode_raises():
    with pytest.raises(ValueError, match="Invalid mode"):
        write_recommendations([], mode="unknown")
