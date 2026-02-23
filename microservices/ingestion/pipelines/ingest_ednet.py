"""
EdNet Ingestion Pipeline - Orchestrator.

Runs the complete ingestion pipeline in sequence:
  0. (Pre)  Checksum verification  (Security)
  1. File Intake                   → Read CSV/TSV files
  2. Structural Validation         → Required columns, row checks, type casting
  3. Privacy Guardrails            → PII scan + column allowlist  (Privacy)
  4. Format Conversion + Compaction → CSV → Parquet, merge small files
  5. Raw Storage Write             → Persist to HDFS raw zone
  *  Lineage record                → Audit trail saved as JSON  (Governance)

Each step is implemented in its own pipeline sub-module and can also be
executed independently.

Usage
-----
    spark-submit \\
        --master spark://master:7077 \\
        microservices/ingestion/pipelines/file_intake/ingest_ednet.py \\
        --config microservices/ingestion/config/ingestion_config.yaml \\
        [--mode initial | daily]
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

from microservices.ingestion.pipelines.file_intake.read_csv import read_all_sources
from microservices.ingestion.pipelines.structural_validation.validate import validate_sources
from microservices.ingestion.pipelines.raw_storage_write.write_to_hdfs import write_to_raw_zone
from microservices.ingestion.src.checksum import (
    compute_checksums,
    save_manifest,
    verify_checksums,
)
from microservices.ingestion.src.compactor import compact
from microservices.ingestion.src.lineage import LineageRecord, save_lineage
from microservices.ingestion.src.logging_config import configure_logging
from microservices.ingestion.src.privacy import (
    enforce_column_allowlist,
    scan_for_pii_columns,
)
from microservices.ingestion.src.schemas import ALLOWED_COLUMNS, SCHEMA_VERSIONS

# ── Structured logging (Maintainability) ──────────────────────────────────
configure_logging()
logger = logging.getLogger(__name__)


def main(config_path: str, mode: str = "initial") -> None:
    """Execute the full ingestion pipeline.

    Parameters
    ----------
    config_path : str
        Path to ``ingestion_config.yaml``.
    mode : str
        ``"initial"`` for the one-time historical dump (overwrite) or
        ``"daily"`` for incremental append.
    """
    write_mode = "overwrite" if mode == "initial" else "append"
    logger.info("=== EdNet Ingestion Pipeline [%s mode] ===", mode)

    with open(config_path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)

    # ── Lineage setup (Governance) ─────────────────────────────────────
    lineage_cfg = cfg.get("lineage", {})
    lineage_enabled = lineage_cfg.get("enabled", False)
    lineage: LineageRecord | None = None
    if lineage_enabled:
        lineage = LineageRecord(
            pipeline_name="ednet-ingestion",
            pipeline_version=lineage_cfg.get("pipeline_version", "0.0.0"),
            run_mode=mode,
        )

    # ── Pre-step: Checksum verification (Security) ────────────────────
    checksum_cfg = cfg.get("checksum", {})
    if checksum_cfg.get("enabled", False):
        manifest_dir = checksum_cfg.get("manifest_dir", "checksums")
        for source_name, src_cfg in cfg["sources"].items():
            src_path = src_cfg["path"]
            manifest_file = f"{manifest_dir}/{source_name}.sha256.json"
            try:
                if mode == "initial":
                    logger.info(
                        "[checksum] Computing manifests for '%s' …",
                        source_name,
                    )
                    manifest = compute_checksums(
                        src_path,
                        glob_pattern=src_cfg.get("glob_pattern", "*"),
                    )
                    save_manifest(manifest, manifest_file)
                else:
                    logger.info(
                        "[checksum] Verifying '%s' against manifest …",
                        source_name,
                    )
                    verify_checksums(
                        src_path,
                        manifest_file,
                        glob_pattern=src_cfg.get("glob_pattern", "*"),
                    )
            except Exception as exc:
                logger.error(
                    "[checksum] '%s' FAILED verification: %s",
                    source_name,
                    exc,
                )
        if lineage:
            lineage.record_step("checksum_verification")

    # ── Step 1 – File Intake ──────────────────────────────────────────
    logger.info("── Step 1/5: File Intake ──")
    dataframes = read_all_sources(config_path)
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
        lineage.record_step("file_intake")

    # ── Step 2 – Structural Validation ────────────────────────────────
    logger.info("── Step 2/5: Structural Validation ──")
    dataframes = validate_sources(dataframes, config_path)
    if lineage:
        lineage.record_step("structural_validation")

    # ── Step 3 – Privacy Guardrails ───────────────────────────────────
    logger.info("── Step 3/5: Privacy Guardrails ──")
    privacy_cfg = cfg.get("privacy", {})
    pii_strict = privacy_cfg.get("pii_scan_strict", True)
    enforce_allowlist = privacy_cfg.get("enforce_allowlist", True)

    for name, df in list(dataframes.items()):
        try:
            # 3a. PII column-name scan
            scan_for_pii_columns(df, source_name=name, strict=pii_strict)

            # 3b. Column allowlist enforcement
            if enforce_allowlist and name in ALLOWED_COLUMNS:
                dataframes[name] = enforce_column_allowlist(
                    df,
                    allowed_columns=ALLOWED_COLUMNS[name],
                    source_name=name,
                )
        except Exception as exc:
            logger.error(
                "[privacy] Source '%s' failed privacy checks: %s", name, exc
            )
            raise

    if lineage:
        lineage.record_step("privacy_guardrails")

    # ── Step 4 – Format Conversion + Compaction ───────────────────────
    logger.info("── Step 4/5: Format Conversion + Compaction ──")
    target_size = cfg.get("compaction", {}).get("target_file_size_mb", 128)
    dataframes = {name: compact(df, target_size) for name, df in dataframes.items()}
    if lineage:
        lineage.record_step("format_conversion_compaction")

    # ── Step 5 – Raw Storage Write (to HDFS) ─────────────────────────
    logger.info("── Step 5/5: Raw Storage Write ──")
    write_to_raw_zone(dataframes, config_path, mode_override=write_mode)
    if lineage:
        for name, df in dataframes.items():
            target_path = cfg["targets"][name]["path"]
            lineage.record_target(
                name=name,
                path=target_path,
                row_count=df.count(),
                format="parquet",
                write_mode=write_mode,
            )
        lineage.record_step("raw_storage_write")

    # ── Lineage finalisation ──────────────────────────────────────────
    if lineage:
        lineage.finish(status="success")
        save_lineage(
            lineage,
            output_dir=lineage_cfg.get("output_dir", "lineage"),
        )

    # ── Summary ───────────────────────────────────────────────────────
    logger.info(
        "=== EdNet Ingestion Pipeline completed  |  sources=%s  mode=%s ===",
        list(dataframes.keys()),
        mode,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="EdNet Ingestion Pipeline - full orchestrator."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="microservices/ingestion/config/ingestion_config.yaml",
        help="Path to the YAML configuration file.",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["initial", "daily"],
        default="initial",
        help="'initial' for historical dump (overwrite), 'daily' for incremental (append).",
    )
    args = parser.parse_args()
    main(args.config, args.mode)
