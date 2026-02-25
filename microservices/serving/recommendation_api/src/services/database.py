"""
Database connection helper.

Provides a simple connection pool to PostgreSQL using psycopg2.
Credentials are read from environment variables (Security).
"""

from __future__ import annotations

import os
import logging
from contextlib import contextmanager
from typing import Generator

import psycopg2
import psycopg2.pool

logger = logging.getLogger(__name__)

_pool: psycopg2.pool.SimpleConnectionPool | None = None


def get_pool() -> psycopg2.pool.SimpleConnectionPool:
    """Return (and lazily create) the global connection pool."""
    global _pool
    if _pool is None or _pool.closed:
        _pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            host=os.getenv("POSTGRES_HOST", "postgres"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=os.getenv("POSTGRES_DB", "recommendations"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "changeme"),
        )
        logger.info("[db] Connection pool created.")
    return _pool


@contextmanager
def get_connection() -> Generator:
    """Context manager that yields a psycopg2 connection from the pool."""
    pool = get_pool()
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)


def close_pool() -> None:
    """Close all connections in the pool."""
    global _pool
    if _pool is not None and not _pool.closed:
        _pool.closeall()
        logger.info("[db] Connection pool closed.")
    _pool = None
