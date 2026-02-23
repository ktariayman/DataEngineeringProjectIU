"""
Pipeline step 4 - Compaction: merge small Parquet files.

Runs after format conversion to consolidate many small files into fewer,
larger files (target ~128-512 MB each).

Architecture diagram: "Compaction (by event_date) → Merge small files,
                        Target file size ~128-512MB, Daily incremental files"
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml

_project_root = str(Path(__file__).resolve().parents[4])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from microservices.ingestion.src.compactor import compact_parquet_path
from microservices.ingestion.src.spark_session import get_spark_session

logger = logging.getLogger(__name__)


def _load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def compact_all(config_path: str) -> None:
    """Compact every raw-zone target defined in the config.

    Parameters
    ----------
    config_path : str
        Path to ``ingestion_config.yaml``.
    """
    cfg = _load_config(config_path)
    compaction_cfg = cfg.get("compaction", {})
    target_size = compaction_cfg.get("target_file_size_mb", 128)

    spark = get_spark_session(
        app_name=cfg["spark"]["app_name"] + "-compaction",
        master=cfg["spark"].get("master"),
        extra_config=cfg["spark"].get("config"),
    )

    targets = cfg["targets"]
    for name, t in targets.items():
        try:
            compact_parquet_path(
                spark=spark,
                path=t["path"],
                target_size_mb=target_size,
                partition_by=t.get("partition_by"),
            )
            logger.info("[compaction] '%s' compacted.", name)
        except Exception as exc:
            logger.error("[compaction] Failed for '%s': %s", name, exc)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 4 - Compaction.")
    parser.add_argument("--config", type=str, default="microservices/ingestion/config/ingestion_config.yaml")
    args = parser.parse_args()
    compact_all(args.config)
