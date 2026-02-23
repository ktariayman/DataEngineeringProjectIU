"""
Pipeline step 5 - Raw Storage Write (HDFS).

Orchestrates the full write path: Parquet already written by step 3 lives
in the raw zone.  This step exists as a logical boundary for the scheduler
and can also handle the distinction between *initial historical dump* and
*daily incremental files*.

Architecture diagram: "Raw Storage Write → Initial Historical dump,
                        Daily incremental files"
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml
from pyspark.sql import DataFrame

_project_root = str(Path(__file__).resolve().parents[4])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from microservices.ingestion.src.format_converter import convert_to_parquet
from microservices.ingestion.src.spark_session import get_spark_session

logger = logging.getLogger(__name__)


def _load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def write_to_raw_zone(
    dataframes: dict[str, DataFrame],
    config_path: str,
    mode_override: str | None = None,
) -> None:
    """Persist DataFrames to the HDFS raw zone.

    Parameters
    ----------
    dataframes : dict[str, DataFrame]
        Validated (and optionally compacted) DataFrames.
    config_path : str
        Path to ``ingestion_config.yaml``.
    mode_override : str | None
        If provided, overrides the write mode for *all* targets.
        Use ``"overwrite"`` for the initial historical dump and
        ``"append"`` for daily incremental files.
    """
    cfg = _load_config(config_path)
    targets = cfg["targets"]

    for name, df in dataframes.items():
        t = targets[name]
        write_mode = mode_override or t.get("mode", "overwrite")
        convert_to_parquet(
            df=df,
            output_path=t["path"],
            mode=write_mode,
            partition_by=t.get("partition_by"),
        )
        logger.info(
            "[raw_storage_write] '%s' written to %s (mode=%s).",
            name, t["path"], write_mode,
        )
