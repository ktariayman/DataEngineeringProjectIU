"""
Tests for the Docker healthcheck script.
Covers Spark importability check and HDFS reachability fallback.
"""

from __future__ import annotations

import importlib
import os
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))


class TestHealthcheckSparkImport:
    """Validate the _check_spark_importable function."""

    def test_spark_is_importable(self):
        """pyspark should be importable in the test environment."""
        print("\n[TEST] test_spark_is_importable")

        # Import the healthcheck module
        spec = importlib.util.spec_from_file_location(
            "healthcheck",
            str(pathlib.Path(__file__).resolve().parents[1] / "docker" / "healthcheck.py"),
        )
        hc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hc)

        result = hc._check_spark_importable()
        assert result is True
        print("  ✓ _check_spark_importable() returned True")

    def test_healthcheck_module_loads(self):
        """The healthcheck module itself should load without errors."""
        print("\n[TEST] test_healthcheck_module_loads")

        spec = importlib.util.spec_from_file_location(
            "healthcheck",
            str(pathlib.Path(__file__).resolve().parents[1] / "docker" / "healthcheck.py"),
        )
        hc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hc)

        assert hasattr(hc, "_check_spark_importable")
        assert hasattr(hc, "_check_hdfs_reachable")
        print("  ✓ healthcheck module loaded with expected functions")


class TestHealthcheckHDFS:
    """Validate HDFS reachability check behaviour."""

    def test_hdfs_unreachable_returns_false(self):
        """When HDFS_URL points to a non-existent host, check returns False."""
        print("\n[TEST] test_hdfs_unreachable_returns_false")

        spec = importlib.util.spec_from_file_location(
            "healthcheck",
            str(pathlib.Path(__file__).resolve().parents[1] / "docker" / "healthcheck.py"),
        )
        hc = importlib.util.module_from_spec(spec)

        # Override HDFS_URL to a dummy address before exec
        os.environ["HDFS_URL"] = "hdfs://nonexistent-host:9000"
        spec.loader.exec_module(hc)

        result = hc._check_hdfs_reachable()
        assert result is False
        print("  ✓ _check_hdfs_reachable() returned False for unreachable host")

    def test_hdfs_missing_env_returns_false(self):
        """When HDFS_URL is not set, check should return False gracefully."""
        print("\n[TEST] test_hdfs_missing_env_returns_false")

        spec = importlib.util.spec_from_file_location(
            "healthcheck",
            str(pathlib.Path(__file__).resolve().parents[1] / "docker" / "healthcheck.py"),
        )
        hc = importlib.util.module_from_spec(spec)

        os.environ.pop("HDFS_URL", None)
        spec.loader.exec_module(hc)

        result = hc._check_hdfs_reachable()
        assert result is False
        print("  ✓ _check_hdfs_reachable() returned False when HDFS_URL missing")
