"""
Async PostgreSQL connection pool for the Recommendation API.

Uses asyncpg for non-blocking I/O — critical for a FastAPI async app.
Pool is initialised once at startup and reused across all requests.

No business logic here — only DB connectivity.
"""

from __future__ import annotations

import logging
import os

import asyncpg

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


def _build_dsn() -> str:
    host = os.environ.get("POSTGRES_HOST", "localhost")
    user = os.environ.get("POSTGRES_USER", "postgres")
    password = os.environ.get("POSTGRES_PASSWORD", "postgres")
    db = os.environ.get("POSTGRES_DB", "recommendations")
    return f"postgresql://{user}:{password}@{host}/{db}"


async def init_pool() -> None:
    """Create the asyncpg connection pool. Called once at app startup."""
    global _pool
    dsn = _build_dsn()
    logger.info("Connecting to PostgreSQL at %s", dsn.split("@")[-1])  # hide credentials
    try:
        _pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
        logger.info("PostgreSQL connection pool ready.")
    except Exception as exc:
        logger.error(
            "Failed to connect to PostgreSQL at %s — pool is None. Error: %s",
            dsn.split("@")[-1],
            exc,
        )
        _pool = None  # explicit — health endpoint will show 'degraded'


async def close_pool() -> None:
    """Gracefully close the connection pool on app shutdown."""
    global _pool
    if _pool:
        await _pool.close()
        logger.info("PostgreSQL connection pool closed.")


async def get_db() -> asyncpg.Connection:
    """
    FastAPI dependency — yields one connection from the pool per request.

    Usage:
        @router.get("/my-route")
        async def my_route(db: asyncpg.Connection = Depends(get_db)):
            ...
    """
    if _pool is None:
        raise RuntimeError("Database pool is not initialised. Call init_pool() first.")
    async with _pool.acquire() as connection:
        yield connection
