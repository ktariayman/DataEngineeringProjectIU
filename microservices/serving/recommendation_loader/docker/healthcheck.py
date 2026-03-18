#!/usr/bin/env python3
"""
Health-check script for the recommendation_loader container.

Verifies:
  1. PySpark is importable.
  2. PostgreSQL is reachable via TCP.
"""

from __future__ import annotations

import os
import socket
import sys


def _check_spark_importable() -> bool:
    try:
        import pyspark  # noqa: F401
        return True
    except ImportError:
        print("[healthcheck] FAIL – pyspark not importable", file=sys.stderr)
        return False


def _check_postgres_reachable(
    host: str = "postgres",
    port: int = 5432,
    timeout: float = 5.0,
) -> bool:
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except OSError as exc:
        print(f"[healthcheck] FAIL – cannot reach {host}:{port}: {exc}", file=sys.stderr)
        return False


def main() -> int:
    pg_host = os.getenv("POSTGRES_HOST", "postgres")
    ok = _check_spark_importable() and _check_postgres_reachable(host=pg_host)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
