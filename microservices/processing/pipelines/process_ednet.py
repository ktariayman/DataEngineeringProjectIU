"""
EdNet Processing Pipeline – Orchestrator.

Runs the complete processing pipeline in sequence:
  1. Data Intake          → Read Parquet from HDFS raw zone
  2. Feature Engineering  → Enrich interactions (correctness, time features)
  3. Feature Aggregation  → Per-student aggregation
  4. Similarity Comp.     → Normalise, cosine similarity, top-K
  *  Privacy Guardrails   → PII scan + column allowlist   (Privacy)
  *  Data Quality         → Validate outputs               (Reliability)
  *  Lineage record       → Audit trail saved as JSON      (Governance)

Each step is implemented in its own pipeline sub-module and can also be
executed independently.

Usage
-----
    spark-submit \\
        --master spark://master:7077 \\
        microservices/processing/pipelines/process_ednet.py \\
        --config microservices/processing/config/processing_config.yaml \\
        [--mode initial | incremental]
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_project_root = str(Path(__file__).resolve().parents[3])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from microservices.processing.src.config_loader import load_config
from microservices.processing.src.data_quality import DataQualityValidator
from microservices.processing.src.lineage import ProcessingLineageRecord, save_lineage
from microservices.processing.src.logging_config import configure_logging
from microservices.processing.src.privacy import (
    enforce_column_allowlist,
    scan_for_pii_columns,
)
from microservices.processing.src.retry import retry
from microservices.processing.src.schemas import SCHEMA_VERSIONS

from microservices.processing.pipelines.data_intake.run import read_raw_sources
from microservices.processing.pipelines.feature_engineering.run import (
    run_feature_engineering,
)
from microservices.processing.pipelines.feature_aggregation.run import (
    run_feature_aggregation,
)
from microservices.processing.pipelines.similarity_computation.run import (
    run_similarity_computation,
)

# ── Structured logging (Maintainability) ──────────────────────────────────
configure_logging()
logger = logging.getLogger(__name__)


# ── HDFS writer with retry (Reliability) ─────────────────────────────────
@retry(max_retries=3, backoff_sec=2.0, backoff_factor=2.0)
def _write_parquet(df, path: str, mode: str = "overwrite") -> None:
    """Write a DataFrame to HDFS Parquet with retry on transient failures."""
    df.write.format("parquet").mode(mode).save(path)
    logger.info("[write] Parquet written → %s (mode=%s)", path, mode)


def main(config_path: str, mode: str = "initial") -> None:
    """Execute the full processing pipeline.

    Parameters
    ----------
    config_path : str
        Path to ``processing_config.yaml``.
    mode : str
        ``"initial"`` for full reprocessing (overwrite) or
        ``"incremental"`` for windowed reprocessing.
    """
    write_mode = "overwrite" if mode == "initial" else "overwrite"
    logger.info("=== EdNet Processing Pipeline [%s mode] ===", mode)

    cfg = load_config(config_path)

    # ── Lineage setup (Governance) ─────────────────────────────────────
    lineage_cfg = cfg.get("lineage", {})
    lineage_enabled = lineage_cfg.get("enabled", False)
    lineage: ProcessingLineageRecord | None = None
    if lineage_enabled:
        lineage = ProcessingLineageRecord(
            pipeline_name="ednet-processing",
            pipeline_version=lineage_cfg.get("pipeline_version", "0.0.0"),
            run_mode=mode,
        )

    # ── Data quality validator (Reliability) ──────────────────────────
    dq_cfg = cfg.get("data_quality", {})
    dq_validator = DataQualityValidator(
        max_null_ratio=dq_cfg.get("max_null_ratio", 0.10),
        min_row_count=dq_cfg.get("min_row_count", 1),
        required_columns=dq_cfg.get("required_output_columns", {}),
    )

    # ── Privacy config ────────────────────────────────────────────────
    privacy_cfg = cfg.get("privacy", {})
    pii_strict = privacy_cfg.get("pii_scan_strict", True)
    enforce_allowlist = privacy_cfg.get("enforce_allowlist", True)
    allowed_columns = privacy_cfg.get("allowed_output_columns", {})

    # ── Step 1 – Data Intake ─────────────────────────────────────────
    logger.info("── Step 1/4: Data Intake ──")
    window_days = None
    if mode == "incremental":
        window_days = cfg.get("processing_window", {}).get("window_days", 7)

    dataframes = read_raw_sources(cfg, window_days=window_days)

    if lineage:
        for name, df in dataframes.items():
            src_path = cfg["sources"][name]["path"]
            lineage.record_source(
                name=name,
                path=src_path,
                row_count=df.count(),
                columns=df.columns,
                schema_version=SCHEMA_VERSIONS.get(name, "unknown"),
            )
        lineage.record_step("data_intake")

    # ── Step 2 – Feature Engineering ─────────────────────────────────
    logger.info("── Step 2/4: Feature Engineering ──")
    enriched_df = run_feature_engineering(dataframes, cfg)
    if lineage:
        lineage.record_transformation(
            name="feature_engineering",
            input_rows=dataframes["kt4"].count(),
            output_rows=enriched_df.count(),
        )
        lineage.record_step("feature_engineering")

    # ── Step 3 – Feature Aggregation ─────────────────────────────────
    logger.info("── Step 3/4: Feature Aggregation ──")
    aggregated_df = run_feature_aggregation(enriched_df, cfg)
    if lineage:
        lineage.record_transformation(
            name="feature_aggregation",
            input_rows=enriched_df.count(),
            output_rows=aggregated_df.count(),
        )
        lineage.record_step("feature_aggregation")

    # ── Step 4 – Similarity Computation ──────────────────────────────
    logger.info("── Step 4/4: Similarity Computation ──")
    user_vectors, recommendations = run_similarity_computation(aggregated_df, cfg)
    if lineage:
        lineage.record_transformation(
            name="similarity_computation",
            input_rows=aggregated_df.count(),
            output_rows=recommendations.count(),
            details={"user_vectors_rows": user_vectors.count()},
        )
        lineage.record_step("similarity_computation")

    # ── Privacy guardrails (Data Privacy) ─────────────────────────────
    logger.info("── Privacy Guardrails ──")
    outputs = {
        "aggregated_student_features": aggregated_df,
        "user_vectors": user_vectors,
        "recommendations_batch": recommendations,
    }

    for name, df in list(outputs.items()):
        scan_for_pii_columns(df, dataset_name=name, strict=pii_strict)
        if enforce_allowlist and name in allowed_columns:
            outputs[name] = enforce_column_allowlist(
                df,
                allowed_columns=allowed_columns[name],
                dataset_name=name,
            )

    if lineage:
        lineage.record_step("privacy_guardrails")

    # ── Data quality validation (Reliability) ─────────────────────────
    logger.info("── Data Quality Validation ──")
    pk_map = {
        "aggregated_student_features": "user_id",
        "user_vectors": "user_id",
        "recommendations_batch": "user_id",
    }
    for name, df in outputs.items():
        dq_validator.validate(df, dataset_name=name, primary_key=pk_map[name])

    if lineage:
        lineage.record_step("data_quality_validation")

    # ── Write to curated zone ─────────────────────────────────────────
    logger.info("── Writing to curated zone ──")
    targets = cfg["targets"]
    for name, df in outputs.items():
        target = targets[name]
        target_path = target["path"]
        _write_parquet(df, target_path, mode=write_mode)

        if lineage:
            lineage.record_target(
                name=name,
                path=target_path,
                row_count=df.count(),
                format="parquet",
                write_mode=write_mode,
            )

    if lineage:
        lineage.record_step("curated_zone_write")

    # ── Lineage finalisation ──────────────────────────────────────────
    if lineage:
        lineage.record_metric("users_processed", aggregated_df.count())
        lineage.record_metric("recommendations_generated", recommendations.count())
        lineage.finish(status="success")
        save_lineage(
            lineage,
            output_dir=lineage_cfg.get("output_dir", "lineage"),
        )

    # ── Summary ───────────────────────────────────────────────────────
    logger.info(
        "=== EdNet Processing Pipeline completed  |  mode=%s  "
        "users=%d  recommendations=%d ===",
        mode,
        aggregated_df.count(),
        recommendations.count(),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="EdNet Processing Pipeline – full orchestrator."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="microservices/processing/config/processing_config.yaml",
        help="Path to the YAML configuration file.",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["initial", "incremental"],
        default="initial",
        help="'initial' for full reprocessing (overwrite), "
             "'incremental' for windowed reprocessing.",
    )
    args = parser.parse_args()
    main(args.config, args.mode)
