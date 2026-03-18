"""
Recommendation service – business logic.
"""

from __future__ import annotations

import logging
from typing import Any

from . import database

logger = logging.getLogger(__name__)


def get_recommendations(user_id: str, top_k: int = 10) -> list[dict[str, Any]]:
    """Fetch top-K recommendations for a given user.

    Parameters
    ----------
    user_id : str
        The student user ID.
    top_k : int
        Maximum number of recommendations to return.

    Returns
    -------
    list[dict]
        List of recommendation dicts with keys:
        ``recommended_user_id``, ``similarity_score``, ``rank``.
    """
    query = """
        SELECT recommended_user_id, similarity_score, rank
        FROM recommendations
        WHERE user_id = %s
        ORDER BY rank ASC
        LIMIT %s
    """
    with database.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (user_id, top_k))
            rows = cur.fetchall()

    return [
        {
            "recommended_user_id": row[0],
            "similarity_score": float(row[1]),
            "rank": int(row[2]),
        }
        for row in rows
    ]


def get_student_features(user_id: str) -> dict[str, Any] | None:
    """Fetch aggregated features for a given user.

    Returns
    -------
    dict or None
        Feature dict, or ``None`` if user not found.
    """
    query = """
        SELECT user_id, total_interactions, correct_count, incorrect_count,
               accuracy_rate, avg_response_time_ms, total_elapsed_time_ms,
               unique_questions_attempted, unique_lectures_viewed, active_days
        FROM student_features
        WHERE user_id = %s
    """
    with database.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (user_id,))
            row = cur.fetchone()

    if row is None:
        return None

    return {
        "user_id": row[0],
        "total_interactions": row[1],
        "correct_count": row[2],
        "incorrect_count": row[3],
        "accuracy_rate": float(row[4]) if row[4] is not None else None,
        "avg_response_time_ms": float(row[5]) if row[5] is not None else None,
        "total_elapsed_time_ms": row[6],
        "unique_questions_attempted": row[7],
        "unique_lectures_viewed": row[8],
        "active_days": row[9],
    }
