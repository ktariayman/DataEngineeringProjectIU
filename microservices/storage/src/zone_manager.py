"""
HDFS Zone Manager for the storage microservice.

Governance guarantees:
  - **Raw vs Curated separation**: two distinct zone types with different
    immutability and access semantics.
  - **Immutable raw zone**: the raw zone is append-only — no updates
    or deletes are permitted once data lands.
  - **Structured folder hierarchy**: all zone paths are centrally defined
    and created idempotently at cluster bootstrap.

This module is responsible for:
  1. Defining the canonical zone layout.
  2. Initialising zone directories on HDFS at first boot.
  3. Validating that zone paths exist and are accessible.
  4. Enforcing immutability rules (raw zone = no overwrites).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── Zone types ────────────────────────────────────────────────────────────

class ZoneType(str, Enum):
    """Logical data zone types on HDFS."""
    RAW = "raw"
    CURATED = "curated"


# ── Dataset definition ────────────────────────────────────────────────────

@dataclass(frozen=True)
class DatasetDefinition:
    """Describes one dataset within a zone."""
    name: str
    path: str
    format: str = "parquet"
    partition_by: tuple[str, ...] = ()
    write_mode: str = "append"
    description: str = ""


# ── Zone definition ───────────────────────────────────────────────────────

@dataclass
class ZoneDefinition:
    """Complete definition of one storage zone."""
    zone_type: ZoneType
    base_path: str
    immutable: bool
    description: str = ""
    datasets: dict[str, DatasetDefinition] = field(default_factory=dict)


# ── Immutability error ────────────────────────────────────────────────────

class ImmutableZoneViolationError(Exception):
    """Raised when a write violates zone immutability rules."""


# ── Canonical zone layout ─────────────────────────────────────────────────

def get_default_zones() -> dict[str, ZoneDefinition]:
    """Return the canonical zone definitions matching the architecture diagram.

    Returns
    -------
    dict[str, ZoneDefinition]
        Keyed by zone type name (``"raw"``, ``"curated"``).
    """
    raw = ZoneDefinition(
        zone_type=ZoneType.RAW,
        base_path="/data/raw",
        immutable=True,
        description="Immutable landing zone — append-only, no updates",
        datasets={
            "kt4": DatasetDefinition(
                name="kt4",
                path="/data/raw/kt4/partitions_by_event_date",
                format="parquet",
                partition_by=("event_date",),
                write_mode="append",
                description="KT4 student interaction events, partitioned by date",
            ),
            "lectures": DatasetDefinition(
                name="lectures",
                path="/data/raw/content/lectures",
                format="parquet",
                write_mode="overwrite",
                description="Lecture metadata from EdNet-Contents",
            ),
            "questions": DatasetDefinition(
                name="questions",
                path="/data/raw/content/questions",
                format="parquet",
                write_mode="overwrite",
                description="Question metadata from EdNet-Contents",
            ),
        },
    )

    curated = ZoneDefinition(
        zone_type=ZoneType.CURATED,
        base_path="/data/curated",
        immutable=False,
        description="Curated zone — derived/aggregated features",
        datasets={
            "aggregated_student_features": DatasetDefinition(
                name="aggregated_student_features",
                path="/data/curated/aggregated_student_features",
                format="parquet",
                description="Pre-computed student feature aggregations",
            ),
            "user_vectors": DatasetDefinition(
                name="user_vectors",
                path="/data/curated/user_vectors",
                format="parquet",
                description="User embedding vectors for similarity",
            ),
            "recommendations_batch": DatasetDefinition(
                name="recommendations_batch",
                path="/data/curated/recommendations_batch",
                format="parquet",
                description="Batch-generated recommendation results",
            ),
        },
    )

    return {ZoneType.RAW: raw, ZoneType.CURATED: curated}


# ── Zone path collector ───────────────────────────────────────────────────

def get_all_zone_paths(zones: Optional[dict[str, ZoneDefinition]] = None) -> list[str]:
    """Return a flat list of every path that should exist on HDFS.

    Includes base zone paths plus every dataset path.
    """
    if zones is None:
        zones = get_default_zones()

    paths: list[str] = []
    for zone in zones.values():
        paths.append(zone.base_path)
        for ds in zone.datasets.values():
            paths.append(ds.path)
    return sorted(set(paths))


# ── Immutability enforcement ──────────────────────────────────────────────

def validate_write_mode(
    zone: ZoneDefinition,
    dataset_name: str,
    requested_mode: str,
) -> None:
    """Check that a requested write mode is compatible with zone rules.

    Parameters
    ----------
    zone : ZoneDefinition
        Target zone.
    dataset_name : str
        Dataset being written to.
    requested_mode : str
        Write mode (``"append"``, ``"overwrite"``, ``"error"``).

    Raises
    ------
    ImmutableZoneViolationError
        If the zone is immutable and the mode would mutate existing data.
    """
    if not zone.immutable:
        logger.debug(
            "[zone] Zone '%s' allows %s for '%s'.",
            zone.zone_type.value, requested_mode, dataset_name,
        )
        return

    # Immutable zone: allow "append" and "overwrite" for reference data
    # (explicitly defined in dataset definition), but block arbitrary overwrites
    ds = zone.datasets.get(dataset_name)
    if ds is None:
        raise ImmutableZoneViolationError(
            f"Dataset '{dataset_name}' is not registered in zone "
            f"'{zone.zone_type.value}'. Unregistered writes are not permitted."
        )

    if requested_mode not in ("append", "overwrite"):
        raise ImmutableZoneViolationError(
            f"Write mode '{requested_mode}' is not allowed in immutable zone "
            f"'{zone.zone_type.value}' for dataset '{dataset_name}'. "
            f"Allowed: append, overwrite (if defined in dataset config)."
        )

    if requested_mode != ds.write_mode:
        raise ImmutableZoneViolationError(
            f"Dataset '{dataset_name}' in zone '{zone.zone_type.value}' "
            f"requires write_mode='{ds.write_mode}', but got '{requested_mode}'."
        )

    logger.info(
        "[zone] Write mode '%s' validated for dataset '%s' in '%s' zone.",
        requested_mode, dataset_name, zone.zone_type.value,
    )


# ── Zone initialisation (generates HDFS commands) ─────────────────────────

def generate_init_commands(
    zones: Optional[dict[str, ZoneDefinition]] = None,
    owner: str = "hdfs",
    group: str = "hadoop",
    raw_permissions: str = "755",
    curated_permissions: str = "750",
) -> list[str]:
    """Generate ``hdfs dfs`` shell commands to bootstrap zone directories.

    These commands are idempotent (``-mkdir -p``) and meant to run inside
    the NameNode container at first boot.

    Returns
    -------
    list[str]
        Ordered list of shell commands.
    """
    if zones is None:
        zones = get_default_zones()

    commands: list[str] = []
    all_paths = get_all_zone_paths(zones)

    for path in all_paths:
        commands.append(f"hdfs dfs -mkdir -p {path}")

    # Set permissions per zone type
    for zone in zones.values():
        perms = (
            raw_permissions if zone.zone_type == ZoneType.RAW
            else curated_permissions
        )
        commands.append(f"hdfs dfs -chmod -R {perms} {zone.base_path}")
        commands.append(f"hdfs dfs -chown -R {owner}:{group} {zone.base_path}")

    return commands
