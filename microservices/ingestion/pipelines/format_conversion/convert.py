"""
Pipeline step 3 - Format Conversion: CSV (DataFrame) → Parquet.

This step takes validated DataFrames and writes them as Parquet to the
configured HDFS raw-zone paths.

Architecture diagram: "Format Conversion → CSV → Parquet"
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

logger = logging.getLogger(__name__)


def _load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def convert_all(
    dataframes: dict[str, DataFrame],
    config_path: str,
) -> None:
    """Write every validated DataFrame to Parquet in the raw zone.

    Parameters
    ----------
    dataframes : dict[str, DataFrame]
        Output of the structural_validation step.
    config_path : str
        Path to ``ingestion_config.yaml``.
    """
    cfg = _load_config(config_path)
    targets = cfg["targets"]

    for name, df in dataframes.items():
        t = targets[name]
        convert_to_parquet(
            df=df,
            output_path=t["path"],
            mode=t.get("mode", "overwrite"),
            partition_by=t.get("partition_by"),
        )
        logger.info("[format_conversion] '%s' → Parquet complete.", name)
