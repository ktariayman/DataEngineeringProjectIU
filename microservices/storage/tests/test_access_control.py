"""Tests for :mod:`microservices.storage.src.access_control`.

Covers security guarantees:
  - RBAC permissions (raw=755, curated=750)
  - Ownership (hdfs:hadoop)
  - Permission validation
  - Encryption zone configuration
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_project_root = str(Path(__file__).resolve().parents[3])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from microservices.storage.src.access_control import (
    AccessRule,
    EncryptionConfig,
    PermissionLevel,
    check_permission_compliance,
    generate_permission_commands,
    get_default_access_rules,
    validate_permission_string,
)


class TestPermissionLevels:
    """Verify permission enum values."""

    def test_owner_full(self) -> None:
        print("\n[TEST] PermissionLevel.OWNER_FULL = 755")
        print(f"  Value: {PermissionLevel.OWNER_FULL.value}")
        assert PermissionLevel.OWNER_FULL.value == "755"
        print("  ✓ 755 = rwxr-xr-x")

    def test_group_restricted(self) -> None:
        print("\n[TEST] PermissionLevel.GROUP_RESTRICTED = 750")
        print(f"  Value: {PermissionLevel.GROUP_RESTRICTED.value}")
        assert PermissionLevel.GROUP_RESTRICTED.value == "750"
        print("  ✓ 750 = rwxr-x---")


class TestDefaultAccessRules:
    """Verify the default RBAC rules."""

    def test_rules_exist(self) -> None:
        print("\n[TEST] Default access rules are defined")
        rules = get_default_access_rules()
        print(f"  Number of rules: {len(rules)}")
        for r in rules:
            print(f"    {r.path} → {r.permissions} ({r.owner}:{r.group})")
        assert len(rules) >= 7
        print("  ✓ At least 7 access rules defined")

    def test_raw_zone_permissions(self) -> None:
        print("\n[TEST] Raw zone has 755 permissions")
        rules = get_default_access_rules()
        raw_rules = [r for r in rules if r.path.startswith("/data/raw")]
        for r in raw_rules:
            print(f"  {r.path} → {r.permissions}")
            assert r.permissions == "755"
        print("  ✓ All raw zone paths have 755 (world-readable)")

    def test_curated_zone_permissions(self) -> None:
        print("\n[TEST] Curated zone has 750 permissions")
        rules = get_default_access_rules()
        curated_rules = [r for r in rules if r.path.startswith("/data/curated")]
        for r in curated_rules:
            print(f"  {r.path} → {r.permissions}")
            assert r.permissions == "750"
        print("  ✓ All curated zone paths have 750 (group-restricted)")

    def test_all_owned_by_hdfs_hadoop(self) -> None:
        print("\n[TEST] All rules owned by hdfs:hadoop")
        rules = get_default_access_rules()
        for r in rules:
            assert r.owner == "hdfs"
            assert r.group == "hadoop"
        print(f"  ✓ All {len(rules)} rules have owner=hdfs, group=hadoop")


class TestValidatePermission:
    """Verify permission string validation."""

    def test_valid_permissions(self) -> None:
        print("\n[TEST] Valid permission strings")
        for perm in ("755", "750", "700", "444", "000"):
            result = validate_permission_string(perm)
            print(f"  '{perm}' → valid={result}")
            assert result is True
        print("  ✓ All valid octal permissions accepted")

    def test_invalid_permissions(self) -> None:
        print("\n[TEST] Invalid permission strings")
        for perm in ("999", "7755", "abc", "", "rwx"):
            result = validate_permission_string(perm)
            print(f"  '{perm}' → valid={result}")
            assert result is False
        print("  ✓ All invalid permissions rejected")


class TestCheckCompliance:
    """Verify permission compliance checking."""

    def test_compliant(self) -> None:
        print("\n[TEST] Matching permissions → compliant")
        ok, msg = check_permission_compliance("755", "755", "/data/raw")
        print(f"  compliant = {ok}")
        print(f"  message   = '{msg}'")
        assert ok is True
        print("  ✓ 755 == 755 → compliant")

    def test_non_compliant(self) -> None:
        print("\n[TEST] Mismatched permissions → non-compliant")
        ok, msg = check_permission_compliance("777", "750", "/data/curated")
        print(f"  compliant = {ok}")
        print(f"  message   = '{msg}'")
        assert ok is False
        assert "MISMATCH" in msg
        print("  ✓ 777 != 750 → MISMATCH detected")


class TestGeneratePermissionCommands:
    """Verify HDFS permission commands."""

    def test_generates_chmod_and_chown(self) -> None:
        print("\n[TEST] Generate chmod + chown commands for all rules")
        cmds = generate_permission_commands()
        chmod_cmds = [c for c in cmds if "chmod" in c]
        chown_cmds = [c for c in cmds if "chown" in c]
        print(f"  Total commands: {len(cmds)}")
        print(f"  chmod commands: {len(chmod_cmds)}")
        print(f"  chown commands: {len(chown_cmds)}")
        # Each rule gets 1 chmod + 1 chown
        assert len(chmod_cmds) == len(chown_cmds)
        assert len(chmod_cmds) >= 7
        print("  ✓ Paired chmod+chown for every access rule")

    def test_custom_rules(self) -> None:
        print("\n[TEST] Generate commands for custom rules")
        custom = [
            AccessRule(path="/data/test", owner="root", group="root",
                      permissions="700", description="Test rule"),
        ]
        cmds = generate_permission_commands(custom)
        print(f"  Commands: {cmds}")
        assert len(cmds) == 2
        assert "700" in cmds[0]
        assert "root:root" in cmds[1]
        print("  ✓ Custom rule → correct chmod+chown pair")


class TestEncryptionConfig:
    """Verify encryption zone configuration."""

    def test_disabled_by_default(self) -> None:
        print("\n[TEST] Encryption is disabled by default")
        cfg = EncryptionConfig()
        print(f"  enabled   = {cfg.enabled}")
        print(f"  key_name  = '{cfg.key_name}'")
        print(f"  zone_path = '{cfg.zone_path}'")
        cmds = cfg.generate_setup_commands()
        print(f"  Commands: {cmds}")
        assert cfg.enabled is False
        assert "DISABLED" in cmds[0]
        print("  ✓ Encryption disabled → no operational commands")

    def test_enabled_generates_commands(self) -> None:
        print("\n[TEST] Enabled encryption generates KMS/crypto commands")
        cfg = EncryptionConfig(enabled=True, key_name="test-key", zone_path="/data")
        cmds = cfg.generate_setup_commands()
        print(f"  Commands ({len(cmds)}):")
        for c in cmds:
            print(f"    {c}")
        assert any("hadoop key create" in c for c in cmds)
        assert any("hdfs crypto -createZone" in c for c in cmds)
        print("  ✓ Encryption enabled → key creation + crypto zone setup")
