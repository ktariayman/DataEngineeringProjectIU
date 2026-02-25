"""Tests for :mod:`microservices.storage.docker.healthcheck`.

Verifies the healthcheck probe logic used by Docker HEALTHCHECK
to monitor the HDFS cluster. Tests use mocked HTTP responses since
no real NameNode is available in the test environment.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_project_root = str(Path(__file__).resolve().parents[3])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Import the healthcheck module
from microservices.storage.docker import healthcheck


class TestHealthcheckNameNodeWeb:
    """Verify NameNode web UI reachability check."""

    @patch("microservices.storage.docker.healthcheck.urllib.request.urlopen")
    def test_namenode_reachable(self, mock_urlopen: MagicMock) -> None:
        print("\n[TEST] NameNode web UI reachable → healthy")
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value = mock_response

        result = healthcheck._check_namenode_web()
        print(f"  Result: {result}")
        assert result is True
        print("  ✓ HTTP 200 → healthy")

    @patch("microservices.storage.docker.healthcheck.urllib.request.urlopen")
    def test_namenode_unreachable(self, mock_urlopen: MagicMock) -> None:
        print("\n[TEST] NameNode web UI unreachable → unhealthy")
        mock_urlopen.side_effect = ConnectionError("refused")

        result = healthcheck._check_namenode_web()
        print(f"  Result: {result}")
        assert result is False
        print("  ✓ Connection error → unhealthy")


class TestHealthcheckLiveDataNodes:
    """Verify DataNode count health check."""

    @patch("microservices.storage.docker.healthcheck.urllib.request.urlopen")
    def test_enough_datanodes(self, mock_urlopen: MagicMock) -> None:
        print("\n[TEST] 3 live DataNodes (min=1) → healthy")
        jmx_data = json.dumps({
            "beans": [{"NumLiveDataNodes": 3}]
        }).encode("utf-8")
        mock_response = MagicMock()
        mock_response.read.return_value = jmx_data
        mock_urlopen.return_value = mock_response

        result = healthcheck._check_live_datanodes(min_nodes=1)
        print(f"  Result: {result}")
        assert result is True
        print("  ✓ 3 >= 1 → healthy")

    @patch("microservices.storage.docker.healthcheck.urllib.request.urlopen")
    def test_too_few_datanodes(self, mock_urlopen: MagicMock) -> None:
        print("\n[TEST] 0 live DataNodes (min=1) → unhealthy")
        jmx_data = json.dumps({
            "beans": [{"NumLiveDataNodes": 0}]
        }).encode("utf-8")
        mock_response = MagicMock()
        mock_response.read.return_value = jmx_data
        mock_urlopen.return_value = mock_response

        result = healthcheck._check_live_datanodes(min_nodes=1)
        print(f"  Result: {result}")
        assert result is False
        print("  ✓ 0 < 1 → unhealthy")


class TestHealthcheckSafeMode:
    """Verify safe mode detection."""

    @patch("microservices.storage.docker.healthcheck.urllib.request.urlopen")
    def test_safe_mode_off(self, mock_urlopen: MagicMock) -> None:
        print("\n[TEST] Safe mode OFF → healthy")
        jmx_data = json.dumps({
            "beans": [{"Safemode": ""}]
        }).encode("utf-8")
        mock_response = MagicMock()
        mock_response.read.return_value = jmx_data
        mock_urlopen.return_value = mock_response

        result = healthcheck._check_safe_mode()
        print(f"  Result: {result}")
        assert result is True
        print("  ✓ Empty Safemode → OFF → healthy")

    @patch("microservices.storage.docker.healthcheck.urllib.request.urlopen")
    def test_safe_mode_on(self, mock_urlopen: MagicMock) -> None:
        print("\n[TEST] Safe mode ON → unhealthy")
        jmx_data = json.dumps({
            "beans": [{"Safemode": "Resources are low on NN"}]
        }).encode("utf-8")
        mock_response = MagicMock()
        mock_response.read.return_value = jmx_data
        mock_urlopen.return_value = mock_response

        result = healthcheck._check_safe_mode()
        print(f"  Result: {result}")
        assert result is False
        print("  ✓ Non-empty Safemode → ON → unhealthy")


class TestHealthcheckMain:
    """Verify the main entrypoint combines all checks."""

    @patch("microservices.storage.docker.healthcheck._check_safe_mode", return_value=True)
    @patch("microservices.storage.docker.healthcheck._check_live_datanodes", return_value=True)
    @patch("microservices.storage.docker.healthcheck._check_namenode_web", return_value=True)
    def test_all_healthy(self, mock_web: MagicMock, mock_dn: MagicMock, mock_safe: MagicMock) -> None:
        print("\n[TEST] All checks pass → exit code 0")
        result = healthcheck.main()
        print(f"  Exit code: {result}")
        assert result == 0
        print("  ✓ All healthy → 0")

    @patch("microservices.storage.docker.healthcheck._check_safe_mode", return_value=True)
    @patch("microservices.storage.docker.healthcheck._check_live_datanodes", return_value=False)
    @patch("microservices.storage.docker.healthcheck._check_namenode_web", return_value=True)
    def test_one_check_fails(self, mock_web: MagicMock, mock_dn: MagicMock, mock_safe: MagicMock) -> None:
        print("\n[TEST] One check fails → exit code 1")
        result = healthcheck.main()
        print(f"  Exit code: {result}")
        assert result == 1
        print("  ✓ Any failure → 1")
