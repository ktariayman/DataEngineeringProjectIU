"""
Recommendation Loader – Pipeline Orchestrator.

Reads curated datasets from HDFS and loads them into PostgreSQL:
  1. recommendations_batch  → recommendations table
  2. aggregated_student_features → student_features table

Usage (via spark-submit inside Docker):
    spark-submit load_to_postgres.py --config loader_config.yaml
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import yaml

_project_root = str(Path(__file__).resolve().parents[4])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from microservices.serving.recommendation_loader.src.reader import read_parquet_from_hdfs
from microservices.serving.recommendation_loader.src.writer import write_df_to_postgres

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recommendation Loader")
    parser.add_argument(
        "--config",
        type=str,
        default="/app/microservices/serving/recommendation_loader/config/loader_config.yaml",
        help="Path to loader_config.yaml",
    )
    return parser.parse_args()


def _build_spark():
    from pyspark.sql import SparkSession

    # PostgreSQL JDBC driver jar
    pg_jar = "/opt/spark/jars/postgresql-42.7.1.jar"

    builder = SparkSession.builder \
        .appName("ednet-recommendation-loader") \
        .master("local[*]") \
        .config("spark.jars", pg_jar) \
        .config("spark.driver.extraClassPath", pg_jar)

    return builder.getOrCreate()


def main() -> None:
    _setup_logging()
    args = _parse_args()

    with open(args.config, "r") as f:
        cfg = yaml.safe_load(f)

    logger.info("=== Recommendation Loader – START ===")

    spark = _build_spark()

    # ── Resolve PostgreSQL credentials from env (Security) ───────────
    pg_cfg = cfg["postgres"]
    jdbc_url = pg_cfg["jdbc_url"]
    pg_user = os.getenv("POSTGRES_USER", "postgres")
    pg_password = os.getenv("POSTGRES_PASSWORD", "changeme")
    write_mode = pg_cfg.get("write_mode", "overwrite")
    batch_size = pg_cfg.get("batch_size", 5000)

    tables = pg_cfg["tables"]

    # ── Step 1: Load recommendations_batch ───────────────────────────
    recs_path = cfg["sources"]["recommendations_batch"]["path"]
    try:
        recs_df = read_parquet_from_hdfs(spark, recs_path)
        # Select only expected columns, drop any extras
        recs_df = recs_df.select("user_id", "recommended_user_id", "similarity_score", "rank")
        write_df_to_postgres(
            df=recs_df,
            jdbc_url=jdbc_url,
            table=tables["recommendations"],
            user=pg_user,
            password=pg_password,
            mode=write_mode,
            batch_size=batch_size,
        )
    except Exception:
        logger.exception("[loader] Failed to load recommendations_batch.")
        raise

    # ── Step 2: Load aggregated_student_features ─────────────────────
    features_path = cfg["sources"]["aggregated_student_features"]["path"]
    try:
        features_df = read_parquet_from_hdfs(spark, features_path)
        # Select expected columns
        expected_cols = [
            "user_id", "total_interactions", "correct_count", "incorrect_count",
            "accuracy_rate", "avg_response_time_ms", "total_elapsed_time_ms",
            "unique_questions_attempted", "unique_lectures_viewed", "active_days",
        ]
        available = [c for c in expected_cols if c in features_df.columns]
        features_df = features_df.select(*available)
        write_df_to_postgres(
            df=features_df,
            jdbc_url=jdbc_url,
            table=tables["student_features"],
            user=pg_user,
            password=pg_password,
            mode=write_mode,
            batch_size=batch_size,
        )
    except Exception:
        logger.exception("[loader] Failed to load aggregated_student_features.")
        raise

    logger.info("=== Recommendation Loader – COMPLETE ===")
    spark.stop()


if __name__ == "__main__":
    main()
