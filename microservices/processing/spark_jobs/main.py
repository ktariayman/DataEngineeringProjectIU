"""
Spark-submit entry point for the processing microservice.

This module is the ``--py-files`` / ``spark-submit`` target invoked by
the Docker container or the scheduler cron job.

Usage
-----
    spark-submit \\
        --master spark://master:7077 \\
        /app/spark_jobs/main.py \\
        --mode initial

Environment variables
---------------------
MODE : str
    ``initial`` or ``incremental``.  Overridden by ``--mode`` CLI arg.
PROCESSING_CONFIG : str
    Path to the YAML config file (default: ``/app/config/processing_config.yaml``).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Ensure the project root is on sys.path so cross-module imports work
# when launched via spark-submit inside the Docker container.
_project_root = str(Path(__file__).resolve().parents[3])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from microservices.processing.pipelines.process_ednet import main as run_pipeline


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="EdNet Processing – spark-submit entry point.")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["initial", "incremental"],
        default=os.environ.get("MODE", "initial"),
        help="Pipeline run mode (default from $MODE or 'initial').",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=os.environ.get(
            "PROCESSING_CONFIG",
            "microservices/processing/config/processing_config.yaml",
        ),
        help="Path to processing_config.yaml.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_pipeline(config_path=args.config, mode=args.mode)
