#!/usr/bin/env python3
"""
Docker HEALTHCHECK probe for the ingestion microservice.

Validates that the container can:
  1. Import PySpark and create a local SparkSession
  2. Reach HDFS NameNode (if HDFS_NAMENODE_HOST is set)

Exit codes: 0 = healthy, 1 = unhealthy.
"""

from __future__ import annotations

import os
import socket
import sys


def _check_spark_importable() -> bool:
    """Verify PySpark can be imported."""
    try:
        import pyspark  # noqa: F401
        return True
    except ImportError:
        print("UNHEALTHY: PySpark is not importable.", file=sys.stderr)
        return False


def _check_hdfs_reachable() -> bool:
    """Verify the HDFS NameNode is reachable on port 9000."""
    host = os.environ.get("HDFS_NAMENODE_HOST", "")
    if not host:
        # Not configured → skip (local dev)
        return True

    port = int(os.environ.get("HDFS_NAMENODE_PORT", "9000"))
    try:
        with socket.create_connection((host, port), timeout=5):
            return True
    except (ConnectionRefusedError, TimeoutError, OSError) as exc:
        print(
            f"UNHEALTHY: Cannot reach HDFS namenode {host}:{port} — {exc}",
            file=sys.stderr,
        )
        return False


def main() -> int:
    checks = [
        _check_spark_importable(),
        _check_hdfs_reachable(),
    ]
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
