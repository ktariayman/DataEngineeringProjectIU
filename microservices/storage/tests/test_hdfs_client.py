"""Tests for :mod:`microservices.storage.src.hdfs_client`.

Covers reliability guarantees:
  - WebHDFS URL construction for all operations
  - JMX response parsing (DataNode count, capacity, safe mode)
  - Environment-based configuration
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_project_root = str(Path(__file__).resolve().parents[3])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from microservices.storage.src.hdfs_client import HDFSClient, HDFSConfig


class TestHDFSConfig:
    """Verify HDFS connection configuration."""

    def test_default_config_values(self) -> None:
        print("\n[TEST] Default HDFSConfig values")
        cfg = HDFSConfig()
        print(f"  namenode_host      = '{cfg.namenode_host}'")
        print(f"  namenode_port      = {cfg.namenode_port}")
        print(f"  web_port           = {cfg.web_port}")
        print(f"  default_fs         = '{cfg.default_fs}'")
        print(f"  user               = '{cfg.user}'")
        print(f"  replication_factor = {cfg.replication_factor}")
        assert cfg.namenode_host == "namenode"
        assert cfg.namenode_port == 9000
        assert cfg.web_port == 9870
        assert cfg.replication_factor == 3
        print("  ✓ All defaults match architecture spec")

    def test_web_url_property(self) -> None:
        print("\n[TEST] HDFSConfig.web_url property")
        cfg = HDFSConfig()
        print(f"  web_url = '{cfg.web_url}'")
        assert cfg.web_url == "http://namenode:9870"
        print("  ✓ Web URL constructed correctly")

    def test_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        print("\n[TEST] HDFSConfig.from_env() reads environment variables")
        monkeypatch.setenv("HDFS_NAMENODE_HOST", "myhost")
        monkeypatch.setenv("HDFS_NAMENODE_PORT", "8020")
        monkeypatch.setenv("HDFS_NAMENODE_WEB_PORT", "50070")
        monkeypatch.setenv("HDFS_USER", "testuser")
        monkeypatch.setenv("HDFS_REPLICATION", "2")
        cfg = HDFSConfig.from_env()
        print(f"  namenode_host      = '{cfg.namenode_host}'")
        print(f"  namenode_port      = {cfg.namenode_port}")
        print(f"  web_port           = {cfg.web_port}")
        print(f"  user               = '{cfg.user}'")
        print(f"  replication_factor = {cfg.replication_factor}")
        assert cfg.namenode_host == "myhost"
        assert cfg.namenode_port == 8020
        assert cfg.web_port == 50070
        assert cfg.user == "testuser"
        assert cfg.replication_factor == 2
        print("  ✓ Config loaded from environment")


class TestWebHDFSUrls:
    """Verify WebHDFS URL construction."""

    def test_mkdir_url(self) -> None:
        print("\n[TEST] build_mkdir_url constructs correct URL")
        client = HDFSClient(HDFSConfig())
        url = client.build_mkdir_url("/data/raw", "755")
        print(f"  URL: {url}")
        assert "op=MKDIRS" in url
        assert "permission=755" in url
        assert "/data/raw" in url
        assert "user.name=hdfs" in url
        print("  ✓ MKDIRS URL includes path, permission, user")

    def test_status_url(self) -> None:
        print("\n[TEST] build_status_url constructs correct URL")
        client = HDFSClient(HDFSConfig())
        url = client.build_status_url("/data/raw/kt4")
        print(f"  URL: {url}")
        assert "op=GETFILESTATUS" in url
        assert "/data/raw/kt4" in url
        print("  ✓ GETFILESTATUS URL correct")

    def test_list_url(self) -> None:
        print("\n[TEST] build_list_url constructs correct URL")
        client = HDFSClient(HDFSConfig())
        url = client.build_list_url("/data/curated")
        print(f"  URL: {url}")
        assert "op=LISTSTATUS" in url
        assert "/data/curated" in url
        print("  ✓ LISTSTATUS URL correct")

    def test_chmod_url(self) -> None:
        print("\n[TEST] build_chmod_url constructs correct URL")
        client = HDFSClient(HDFSConfig())
        url = client.build_chmod_url("/data/raw", "755")
        print(f"  URL: {url}")
        assert "op=SETPERMISSION" in url
        assert "permission=755" in url
        print("  ✓ SETPERMISSION URL correct")

    def test_chown_url(self) -> None:
        print("\n[TEST] build_chown_url constructs correct URL")
        client = HDFSClient(HDFSConfig())
        url = client.build_chown_url("/data/raw", "hdfs", "hadoop")
        print(f"  URL: {url}")
        assert "op=SETOWNER" in url
        assert "owner=hdfs" in url
        assert "group=hadoop" in url
        print("  ✓ SETOWNER URL correct")

    def test_jmx_url(self) -> None:
        print("\n[TEST] build_jmx_url constructs correct URL")
        client = HDFSClient(HDFSConfig())
        url = client.build_jmx_url()
        print(f"  URL: {url}")
        assert "/jmx" in url
        assert "FSNamesystem" in url
        print("  ✓ JMX URL correct")


class TestJMXParsing:
    """Verify NameNode JMX response parsing."""

    def test_parse_live_datanodes(self) -> None:
        print("\n[TEST] Parse NumLiveDataNodes from JMX")
        jmx_data = {
            "beans": [
                {"name": "Hadoop:service=NameNode,name=FSNamesystem",
                 "NumLiveDataNodes": 3, "NumDeadDataNodes": 0}
            ]
        }
        result = HDFSClient.parse_live_datanodes(jmx_data)
        print(f"  NumLiveDataNodes = {result}")
        assert result == 3
        print("  ✓ Correctly parsed 3 live DataNodes")

    def test_parse_live_datanodes_missing(self) -> None:
        print("\n[TEST] Parse JMX with no NumLiveDataNodes key")
        jmx_data = {"beans": [{"name": "other_bean"}]}
        result = HDFSClient.parse_live_datanodes(jmx_data)
        print(f"  Result = {result}")
        assert result == 0
        print("  ✓ Returns 0 when key is missing")

    def test_parse_capacity_info(self) -> None:
        print("\n[TEST] Parse capacity metrics from JMX")
        jmx_data = {
            "beans": [{
                "CapacityTotal": 107374182400,
                "CapacityUsed": 10737418240,
                "CapacityRemaining": 96636764160,
            }]
        }
        result = HDFSClient.parse_capacity_info(jmx_data)
        print(f"  Total:     {result['total_bytes']:>15,} bytes")
        print(f"  Used:      {result['used_bytes']:>15,} bytes")
        print(f"  Remaining: {result['remaining_bytes']:>15,} bytes")
        assert result["total_bytes"] == 107374182400
        assert result["used_bytes"] == 10737418240
        assert result["remaining_bytes"] == 96636764160
        print("  ✓ All capacity metrics parsed correctly")

    def test_parse_safe_mode_false(self) -> None:
        print("\n[TEST] Parse safe mode = OFF from JMX")
        jmx_data = {"beans": [{"Safemode": ""}]}
        result = HDFSClient.parse_safe_mode(jmx_data)
        print(f"  Safe mode active = {result}")
        assert result is False
        print("  ✓ Empty Safemode string → not in safe mode")

    def test_parse_safe_mode_true(self) -> None:
        print("\n[TEST] Parse safe mode = ON from JMX")
        jmx_data = {"beans": [{"Safemode": "Resources are low on NN"}]}
        result = HDFSClient.parse_safe_mode(jmx_data)
        print(f"  Safe mode active = {result}")
        assert result is True
        print("  ✓ Non-empty Safemode string → in safe mode")
