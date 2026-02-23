"""
Pipeline step 2 - Structural Validation.

Runs required-columns check, row count check, null-ratio check, type casting
enforcement, and basic normalisation (trim strings, empty → null).

Architecture diagram: "Structural Validation → Required columns check,
                        Rows Check, Type casting, Basic Normalization"
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

from microservices.ingestion.src.structural_validator import StructuralValidator

logger = logging.getLogger(__name__)


def _load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def build_validator(config_path: str) -> StructuralValidator:
    """Instantiate a :class:`StructuralValidator` from the YAML config."""
    cfg = _load_config(config_path)
    v_cfg = cfg.get("validation", {})
    return StructuralValidator(
        max_null_ratio=v_cfg.get("max_null_ratio", 0.05),
        min_row_count=v_cfg.get("min_row_count", 1),
        required_columns=v_cfg.get("required_columns", {}),
    )


def validate_sources(
    dataframes: dict[str, DataFrame],
    config_path: str,
) -> dict[str, DataFrame]:
    """Validate every source DataFrame and return cleaned versions.

    Parameters
    ----------
    dataframes : dict[str, DataFrame]
        Output of the file_intake step.
    config_path : str
        Path to ``ingestion_config.yaml``.

    Returns
    -------
    dict[str, DataFrame]
        Validated + normalised DataFrames (same keys).
    """
    validator = build_validator(config_path)
    validated: dict[str, DataFrame] = {}

    for name, df in dataframes.items():
        try:
            validated[name] = validator.validate(df, source_name=name)
        except Exception as exc:
            logger.error(
                "[structural_validation] Source '%s' FAILED validation: %s",
                name, exc,
            )

    if not validated:
        raise RuntimeError("All sources failed structural validation. Aborting pipeline.")

    return validated


if __name__ == "__main__":
    # Standalone execution is only useful for testing with pre-read Parquet
    parser = argparse.ArgumentParser(description="Step 2 - Structural Validation.")
    parser.add_argument("--config", type=str, default="microservices/ingestion/config/ingestion_config.yaml")
    args = parser.parse_args()
    logger.info("Validator built successfully: %s", build_validator(args.config))
