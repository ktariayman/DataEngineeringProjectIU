"""
Configuration loader for the processing microservice.

Provides a single entry point for reading and validating the YAML config,
with sensible defaults for every section.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = "microservices/processing/config/processing_config.yaml"


def load_config(path: str | None = None) -> dict[str, Any]:
    """Read ``processing_config.yaml`` and return the parsed dict.

    Parameters
    ----------
    path : str | None
        Explicit path.  Falls back to *_DEFAULT_CONFIG_PATH*.

    Returns
    -------
    dict[str, Any]
        The full configuration dictionary.

    Raises
    ------
    FileNotFoundError
        If the YAML file does not exist.
    yaml.YAMLError
        If the file is not valid YAML.
    """
    config_path = path or _DEFAULT_CONFIG_PATH
    p = Path(config_path)

    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(p, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)

    logger.info("[config] Loaded configuration from %s", config_path)
    return _apply_defaults(cfg)


def _apply_defaults(cfg: dict[str, Any]) -> dict[str, Any]:
    """Merge user config with sensible defaults."""
    cfg.setdefault("spark", {})
    cfg["spark"].setdefault("app_name", "ednet-processing")
    cfg["spark"].setdefault("config", {})

    cfg.setdefault("sources", {})
    cfg.setdefault("targets", {})

    # Feature engineering defaults
    fe = cfg.setdefault("feature_engineering", {})
    fe.setdefault("correctness_join", True)
    fe.setdefault("time_features", True)
    fe.setdefault("response_time_cap_ms", 300_000)

    # Feature aggregation defaults
    fa = cfg.setdefault("feature_aggregation", {})
    fa.setdefault("min_interactions", 5)

    # Similarity defaults
    sim = cfg.setdefault("similarity", {})
    sim.setdefault("method", "cosine")
    sim.setdefault("top_k", 10)
    sim.setdefault("feature_columns", [
        "accuracy_rate",
        "avg_response_time_ms",
        "total_interactions",
        "unique_questions_attempted",
        "unique_lectures_viewed",
        "active_days",
    ])

    # Processing window defaults
    pw = cfg.setdefault("processing_window", {})
    pw.setdefault("window_days", 7)

    # Data quality defaults
    dq = cfg.setdefault("data_quality", {})
    dq.setdefault("max_null_ratio", 0.10)
    dq.setdefault("min_row_count", 1)
    dq.setdefault("required_output_columns", {})

    # Privacy defaults
    priv = cfg.setdefault("privacy", {})
    priv.setdefault("pii_scan_strict", True)
    priv.setdefault("enforce_allowlist", True)
    priv.setdefault("allowed_output_columns", {})

    # Lineage defaults
    lin = cfg.setdefault("lineage", {})
    lin.setdefault("enabled", True)
    lin.setdefault("pipeline_version", "1.0.0")
    lin.setdefault("output_dir", "lineage")

    # Compaction defaults
    comp = cfg.setdefault("compaction", {})
    comp.setdefault("target_file_size_mb", 128)

    return cfg
