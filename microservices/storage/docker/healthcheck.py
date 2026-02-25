#!/usr/bin/env python3
"""
Docker HEALTHCHECK probe for the storage microservice containers.

Validates that:
  1. NameNode WebHDFS is reachable (HTTP 200 on port 9870).
  2. There are at least ``min_datanodes`` live DataNodes
     (queried via NameNode JMX endpoint).
  3. NameNode is NOT in safe mode (cluster is operational).

Exit codes: 0 = healthy, 1 = unhealthy.

Reliability guarantee: the healthcheck signals Docker / orchestrator
when the HDFS cluster is degraded, triggering automatic restarts or
alerts per the ``restart: unless-stopped`` policy in storage.yml.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request


def _get_env(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _check_namenode_web() -> bool:
    """Verify NameNode Web UI is reachable."""
    host = _get_env("HDFS_NAMENODE_HOST", "namenode")
    port = _get_env("HDFS_NAMENODE_WEB_PORT", "9870")
    url = f"http://{host}:{port}/"
    try:
        req = urllib.request.urlopen(url, timeout=5)
        if req.getcode() == 200:
            return True
        print(f"UNHEALTHY: NameNode returned HTTP {req.getcode()}", file=sys.stderr)
        return False
    except Exception as exc:
        print(f"UNHEALTHY: Cannot reach NameNode at {url} — {exc}", file=sys.stderr)
        return False


def _check_live_datanodes(min_nodes: int = 1) -> bool:
    """Verify the expected number of DataNodes are alive."""
    host = _get_env("HDFS_NAMENODE_HOST", "namenode")
    port = _get_env("HDFS_NAMENODE_WEB_PORT", "9870")
    url = (
        f"http://{host}:{port}"
        f"/jmx?qry=Hadoop:service=NameNode,name=FSNamesystem"
    )
    try:
        req = urllib.request.urlopen(url, timeout=5)
        data = json.loads(req.read().decode("utf-8"))
        for bean in data.get("beans", []):
            if "NumLiveDataNodes" in bean:
                live = int(bean["NumLiveDataNodes"])
                if live >= min_nodes:
                    return True
                print(
                    f"UNHEALTHY: Only {live}/{min_nodes} DataNodes alive.",
                    file=sys.stderr,
                )
                return False
        print("UNHEALTHY: Could not find NumLiveDataNodes in JMX.", file=sys.stderr)
        return False
    except Exception as exc:
        print(f"UNHEALTHY: JMX query failed — {exc}", file=sys.stderr)
        return False


def _check_safe_mode() -> bool:
    """Verify NameNode is NOT in safe mode."""
    host = _get_env("HDFS_NAMENODE_HOST", "namenode")
    port = _get_env("HDFS_NAMENODE_WEB_PORT", "9870")
    url = (
        f"http://{host}:{port}"
        f"/jmx?qry=Hadoop:service=NameNode,name=FSNamesystem"
    )
    try:
        req = urllib.request.urlopen(url, timeout=5)
        data = json.loads(req.read().decode("utf-8"))
        for bean in data.get("beans", []):
            if "Safemode" in bean:
                # Safemode value is empty string when OFF
                if bean["Safemode"]:
                    print("UNHEALTHY: NameNode is in safe mode.", file=sys.stderr)
                    return False
                return True
        # If Safemode key is missing, assume OK
        return True
    except Exception as exc:
        print(f"UNHEALTHY: Safe mode check failed — {exc}", file=sys.stderr)
        return False


def main() -> int:
    min_dn = int(_get_env("MIN_DATANODES", "1"))
    checks = [
        ("namenode_web", _check_namenode_web()),
        ("live_datanodes", _check_live_datanodes(min_dn)),
        ("safe_mode_off", _check_safe_mode()),
    ]
    failed = [name for name, ok in checks if not ok]
    if failed:
        print(f"UNHEALTHY checks: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
