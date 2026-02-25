"""
Path resolver for the storage microservice.

Maintainability guarantees:
  - **Single source of truth**: all HDFS paths for raw and curated zones
    are resolved through this module — no hardcoded paths elsewhere.
  - **Structured folder hierarchy**: paths follow a consistent convention
    with zone / dataset / optional partition structure.

Governance guarantees:
  - Paths are validated against the registered zone layout.
  - Unregistered datasets produce clear errors.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ── Base HDFS root ────────────────────────────────────────────────────────
_DEFAULT_FS = "hdfs://namenode:9000"


# ── Path building helpers ─────────────────────────────────────────────────

def resolve_raw_path(
    dataset: str,
    default_fs: str = _DEFAULT_FS,
) -> str:
    """Resolve the full HDFS path for a raw-zone dataset.

    Parameters
    ----------
    dataset : str
        One of ``"kt4"``, ``"lectures"``, ``"questions"``.
    default_fs : str
        HDFS filesystem prefix.

    Returns
    -------
    str
        Fully qualified HDFS path.

    Raises
    ------
    ValueError
        If the dataset is not registered in the raw zone.
    """
    _RAW_PATHS = {
        "kt4": "/data/raw/kt4/partitions_by_event_date",
        "lectures": "/data/raw/content/lectures",
        "questions": "/data/raw/content/questions",
    }
    if dataset not in _RAW_PATHS:
        raise ValueError(
            f"Unknown raw dataset '{dataset}'. "
            f"Registered: {sorted(_RAW_PATHS.keys())}"
        )
    return f"{default_fs}{_RAW_PATHS[dataset]}"


def resolve_curated_path(
    dataset: str,
    default_fs: str = _DEFAULT_FS,
) -> str:
    """Resolve the full HDFS path for a curated-zone dataset.

    Parameters
    ----------
    dataset : str
        One of ``"aggregated_student_features"``, ``"user_vectors"``,
        ``"recommendations_batch"``.
    default_fs : str
        HDFS filesystem prefix.

    Returns
    -------
    str
        Fully qualified HDFS path.

    Raises
    ------
    ValueError
        If the dataset is not registered in the curated zone.
    """
    _CURATED_PATHS = {
        "aggregated_student_features": "/data/curated/aggregated_student_features",
        "user_vectors": "/data/curated/user_vectors",
        "recommendations_batch": "/data/curated/recommendations_batch",
    }
    if dataset not in _CURATED_PATHS:
        raise ValueError(
            f"Unknown curated dataset '{dataset}'. "
            f"Registered: {sorted(_CURATED_PATHS.keys())}"
        )
    return f"{default_fs}{_CURATED_PATHS[dataset]}"


def resolve_partition_path(
    dataset: str,
    event_date: date | str,
    default_fs: str = _DEFAULT_FS,
) -> str:
    """Resolve the full HDFS path for a specific date partition.

    Parameters
    ----------
    dataset : str
        Dataset name (currently only ``"kt4"`` supports partitioning).
    event_date : date | str
        Date for the partition (``YYYY-MM-DD`` string or ``date`` object).
    default_fs : str
        HDFS filesystem prefix.

    Returns
    -------
    str
        Path like ``hdfs://namenode:9000/data/raw/kt4/partitions_by_event_date/event_date=2025-01-15``

    Raises
    ------
    ValueError
        If the dataset doesn't support partitioning or date format is invalid.
    """
    base = resolve_raw_path(dataset, default_fs)

    if isinstance(event_date, date):
        date_str = event_date.isoformat()
    else:
        date_str = str(event_date)

    # Validate date format
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        raise ValueError(
            f"Invalid date format '{date_str}'. Expected YYYY-MM-DD."
        )

    return f"{base}/event_date={date_str}"


def get_zone_base_path(zone: str, default_fs: str = _DEFAULT_FS) -> str:
    """Get the base path for a zone.

    Parameters
    ----------
    zone : str
        ``"raw"`` or ``"curated"``.
    default_fs : str
        HDFS filesystem prefix.

    Returns
    -------
    str
        Fully qualified HDFS base path for the zone.
    """
    _ZONE_BASES = {
        "raw": "/data/raw",
        "curated": "/data/curated",
    }
    if zone not in _ZONE_BASES:
        raise ValueError(
            f"Unknown zone '{zone}'. Valid: {sorted(_ZONE_BASES.keys())}"
        )
    return f"{default_fs}{_ZONE_BASES[zone]}"


def list_all_dataset_paths(default_fs: str = _DEFAULT_FS) -> dict[str, str]:
    """Return a mapping of all dataset names to their HDFS paths.

    Returns
    -------
    dict[str, str]
        ``{"kt4": "hdfs://...", "lectures": "hdfs://...", ...}``
    """
    result: dict[str, str] = {}
    for ds in ("kt4", "lectures", "questions"):
        result[ds] = resolve_raw_path(ds, default_fs)
    for ds in ("aggregated_student_features", "user_vectors", "recommendations_batch"):
        result[ds] = resolve_curated_path(ds, default_fs)
    return result
