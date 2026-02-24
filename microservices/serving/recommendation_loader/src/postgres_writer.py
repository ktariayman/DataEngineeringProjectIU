"""
PostgreSQL batch writer for the Recommendation Loader.

Two write modes (matching ingestion's pattern):
  - initial: TRUNCATE then bulk COPY (fast, replaces all data)
  - daily:   INSERT ... ON CONFLICT DO UPDATE (idempotent upsert)

Design rules:
  - Idempotency: running twice produces the same result (Reliability NFR)
  - No business logic — only persistence
  - Logs rows inserted per batch for observability
"""

from __future__ import annotations

import logging
import os
from itertools import islice
from typing import Iterable

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

_BATCH_SIZE = 5_000  # rows per INSERT batch


def _get_conn():
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
        dbname=os.environ.get("POSTGRES_DB", "recommendations"),
    )


def write_recommendations(rows: Iterable[dict], mode: str) -> int:
    """
    Write recommendation rows to PostgreSQL.

    Parameters
    ----------
    rows : Iterable[dict]
        Each dict must have: user_id, recommended_user_id, similarity_score, generation_date
    mode : str
        "initial" → TRUNCATE + bulk copy
        "daily"   → idempotent upsert (INSERT ON CONFLICT DO UPDATE)

    Returns
    -------
    int : total rows written
    """
    if mode not in ("initial", "daily"):
        raise ValueError(f"Invalid mode '{mode}'. Must be 'initial' or 'daily'.")

    conn = _get_conn()
    total_written = 0

    try:
        with conn:  # auto-commit / rollback via context manager
            with conn.cursor() as cur:
                if mode == "initial":
                    logger.info("Initial mode: truncating recommendations table.")
                    cur.execute("TRUNCATE TABLE recommendations RESTART IDENTITY CASCADE;")

                total_written = _write_batches(conn, rows, mode)

        logger.info("Loader complete. Total rows written: %d (mode=%s)", total_written, mode)

    finally:
        conn.close()

    return total_written


def _write_batches(conn, rows: Iterable[dict], mode: str) -> int:
    """Write rows in batches of _BATCH_SIZE. Returns total rows written."""
    rows_iter = iter(rows)
    total = 0

    while True:
        batch = list(islice(rows_iter, _BATCH_SIZE))
        if not batch:
            break

        tuples = [
            (
                r["user_id"],
                r["recommended_user_id"],
                r["similarity_score"],
                r["generation_date"],
            )
            for r in batch
        ]

        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO recommendations
                    (user_id, recommended_user_id, similarity_score, generation_date)
                VALUES %s
                ON CONFLICT (user_id, recommended_user_id, generation_date)
                DO UPDATE SET
                    similarity_score = EXCLUDED.similarity_score,
                    created_at       = NOW()
                """,
                tuples,
                page_size=_BATCH_SIZE,
            )

        total += len(batch)
        logger.info("Batch written: %d rows (total so far: %d)", len(batch), total)

    return total
