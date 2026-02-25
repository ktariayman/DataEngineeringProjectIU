#!/usr/bin/env python3
"""
Health-check script for the processing microservice Docker container.

Verifies that the runtime environment is functional:
  1. PySpark is importable (driver-side sanity check).
  2. HDFS NameNode is reachable (network / DNS check).

Exit codes
----------
0 – healthy
1 – unhealthy
"""

from __future__ import annotations

import os
import socket
import sys


def _check_spark_importable() -> bool:
    """Return ``True`` if PySpark can be imported."""
    try:
        import pyspark  # noqa: F401
        return True
    except ImportError:
        print("[healthcheck] FAIL – pyspark not importable", file=sys.stderr)
        return False


def _check_hdfs_reachable(
    host: str = "namenode",
    port: int = 9000,
    timeout: float = 5.0,
) -> bool:
    """Return ``True`` if the HDFS NameNode is reachable via TCP."""
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except (OSError, socket.timeout):
        print(
            f"[healthcheck] FAIL – cannot reach {host}:{port}",
            file=sys.stderr,
        )
        return False


def main() -> int:
    """Run all health checks; return 0 if all pass, 1 otherwise."""
    hdfs_url = os.environ.get("HDFS_URL", "hdfs://namenode:9000")
    host = hdfs_url.replace("hdfs://", "").split(":")[0]
    port = int(hdfs_url.replace("hdfs://", "").split(":")[-1])

    checks = [
        ("spark_importable", _check_spark_importable()),
        ("hdfs_reachable", _check_hdfs_reachable(host, port)),
    ]

    all_ok = all(ok for _, ok in checks)

    for name, ok in checks:
        status = "PASS" if ok else "FAIL"
        print(f"[healthcheck] {name}: {status}")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
