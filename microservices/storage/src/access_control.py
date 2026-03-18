"""
RBAC access control for the storage microservice.

Security guarantees:
  - **RBAC permissions**: zone-level access control via HDFS file
    permissions (owner / group / other).
  - **Encryption at rest**: transparent encryption zone configuration
    (requires HDFS KMS in production).

Governance guarantees:
  - Permission rules are defined centrally and applied consistently.
  - Permission violations are detected and reported.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


# ── Permission model ──────────────────────────────────────────────────────

class PermissionLevel(str, Enum):
    """Standard HDFS permission levels."""
    READ_ONLY = "444"           # r--r--r--
    READ_EXECUTE = "555"        # r-xr-xr-x
    OWNER_FULL = "755"          # rwxr-xr-x  (raw zone default)
    GROUP_RESTRICTED = "750"    # rwxr-x---  (curated zone default)
    OWNER_ONLY = "700"          # rwx------


@dataclass(frozen=True)
class AccessRule:
    """Access control rule for a zone or path."""
    path: str
    owner: str
    group: str
    permissions: str
    description: str = ""


# ── Default access rules ─────────────────────────────────────────────────

def get_default_access_rules() -> list[AccessRule]:
    """Return the default RBAC rules from the architecture specification.

    Raw zone: ``755`` (owner: rwx, group/other: r-x) — world-readable.
    Curated zone: ``750`` (owner: rwx, group: r-x, other: ---) — restricted.
    """
    return [
        AccessRule(
            path="/data/raw",
            owner="hdfs",
            group="hadoop",
            permissions="755",
            description="Raw zone: owner rwx, group+other r-x (immutable, read-open)",
        ),
        AccessRule(
            path="/data/raw/kt4",
            owner="hdfs",
            group="hadoop",
            permissions="755",
            description="KT4 data: same as raw zone base",
        ),
        AccessRule(
            path="/data/raw/content",
            owner="hdfs",
            group="hadoop",
            permissions="755",
            description="Content data: lectures + questions",
        ),
        AccessRule(
            path="/data/curated",
            owner="hdfs",
            group="hadoop",
            permissions="750",
            description="Curated zone: owner rwx, group r-x, other --- (restricted)",
        ),
        AccessRule(
            path="/data/curated/aggregated_student_features",
            owner="hdfs",
            group="hadoop",
            permissions="750",
            description="Aggregated features: restricted to hadoop group",
        ),
        AccessRule(
            path="/data/curated/user_vectors",
            owner="hdfs",
            group="hadoop",
            permissions="750",
            description="User vectors: restricted to hadoop group",
        ),
        AccessRule(
            path="/data/curated/recommendations_batch",
            owner="hdfs",
            group="hadoop",
            permissions="750",
            description="Recommendations: restricted to hadoop group",
        ),
    ]


# ── Permission validation ────────────────────────────────────────────────

_PERMISSION_PATTERN = re.compile(r"^[0-7]{3}$")


def validate_permission_string(permission: str) -> bool:
    """Validate an octal permission string (e.g. ``"755"``)."""
    return bool(_PERMISSION_PATTERN.match(permission))


def check_permission_compliance(
    actual_permission: str,
    expected_permission: str,
    path: str,
) -> tuple[bool, str]:
    """Check if actual permissions match expected.

    Parameters
    ----------
    actual_permission : str
        Octal permission string from HDFS (e.g. ``"755"``).
    expected_permission : str
        Required permission string.
    path : str
        Path for logging context.

    Returns
    -------
    tuple[bool, str]
        ``(is_compliant, message)``
    """
    if actual_permission == expected_permission:
        return True, f"Path '{path}' permissions OK: {actual_permission}"

    return (
        False,
        f"Path '{path}' permission MISMATCH: "
        f"actual={actual_permission}, expected={expected_permission}",
    )


# ── HDFS command generation ──────────────────────────────────────────────

def generate_permission_commands(
    rules: Optional[list[AccessRule]] = None,
) -> list[str]:
    """Generate ``hdfs dfs`` commands to apply access rules.

    Returns
    -------
    list[str]
        Ordered shell commands for chmod and chown.
    """
    if rules is None:
        rules = get_default_access_rules()

    commands: list[str] = []
    for rule in rules:
        commands.append(
            f"hdfs dfs -chmod -R {rule.permissions} {rule.path}"
        )
        commands.append(
            f"hdfs dfs -chown -R {rule.owner}:{rule.group} {rule.path}"
        )

    return commands


# ── Encryption zone helpers ──────────────────────────────────────────────

@dataclass(frozen=True)
class EncryptionConfig:
    """Transparent encryption zone configuration."""
    enabled: bool = False
    key_name: str = "ednet-encryption-key"
    zone_path: str = "/data"

    def generate_setup_commands(self) -> list[str]:
        """Generate commands to create an HDFS encryption zone.

        Requires HDFS KMS (Key Management Server) to be running.
        """
        if not self.enabled:
            return ["# Encryption at rest: DISABLED (enable in config)"]

        return [
            f"# Create encryption key (run once)",
            f"hadoop key create {self.key_name} -size 128",
            f"# Create encryption zone",
            f"hdfs crypto -createZone -keyName {self.key_name} -path {self.zone_path}",
            f"# Verify encryption zone",
            f"hdfs crypto -listZones",
        ]
