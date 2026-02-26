"""
PySpark schema definitions for the processing microservice.

Governance
----------
- Explicit schema definitions prevent silent data corruption.
- Schema versions enable forward-compatible evolution.
- Allowed-column lists enforce the privacy layer.

The processing microservice reads from the **raw zone** (ingestion output)
and writes to the **curated zone** (aggregated features, user vectors,
recommendation batches).
"""

from __future__ import annotations

from pyspark.sql.types import (
    DoubleType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
)

# ══════════════════════════════════════════════════════════════════════════
# Schema versions  (Governance)
# ══════════════════════════════════════════════════════════════════════════
PROCESSING_SCHEMA_VERSION = "1.0.0"
AGGREGATED_FEATURES_SCHEMA_VERSION = "1.0.0"
USER_VECTORS_SCHEMA_VERSION = "1.0.0"
RECOMMENDATIONS_SCHEMA_VERSION = "1.0.0"

SCHEMA_VERSIONS: dict[str, str] = {
    "processing": PROCESSING_SCHEMA_VERSION,
    "aggregated_student_features": AGGREGATED_FEATURES_SCHEMA_VERSION,
    "user_vectors": USER_VECTORS_SCHEMA_VERSION,
    "recommendations_batch": RECOMMENDATIONS_SCHEMA_VERSION,
}

# ══════════════════════════════════════════════════════════════════════════
# INPUT schemas — raw zone Parquet produced by ingestion
# ══════════════════════════════════════════════════════════════════════════

# KT4 interactions  (with user_id derived from file path during ingestion)
KT4_INPUT_SCHEMA = StructType([
    StructField("user_id", StringType(), nullable=False),
    StructField("timestamp", LongType(), nullable=False),
    StructField("action_type", StringType(), nullable=False),
    StructField("item_id", StringType(), nullable=False),
    StructField("source", StringType(), nullable=True),
    StructField("user_answer", StringType(), nullable=True),
    StructField("platform", StringType(), nullable=True),
    StructField("cursor_time", LongType(), nullable=True),
    StructField("event_date", StringType(), nullable=True),
])

LECTURES_INPUT_SCHEMA = StructType([
    StructField("lecture_id", StringType(), nullable=False),
    StructField("tags", StringType(), nullable=True),
    StructField("part", IntegerType(), nullable=True),
])

QUESTIONS_INPUT_SCHEMA = StructType([
    StructField("question_id", StringType(), nullable=False),
    StructField("bundle_id", StringType(), nullable=True),
    StructField("explanation_id", StringType(), nullable=True),
    StructField("correct_answer", StringType(), nullable=True),
    StructField("part", IntegerType(), nullable=True),
    StructField("tags", StringType(), nullable=True),
])

# ══════════════════════════════════════════════════════════════════════════
# INTERMEDIATE schema — enriched interactions after feature engineering
# ══════════════════════════════════════════════════════════════════════════

ENRICHED_INTERACTION_SCHEMA = StructType([
    StructField("user_id", StringType(), nullable=False),
    StructField("timestamp", LongType(), nullable=False),
    StructField("action_type", StringType(), nullable=False),
    StructField("item_id", StringType(), nullable=False),
    StructField("source", StringType(), nullable=True),
    StructField("user_answer", StringType(), nullable=True),
    StructField("platform", StringType(), nullable=True),
    StructField("cursor_time", LongType(), nullable=True),
    StructField("event_date", StringType(), nullable=True),
    StructField("correct_answer", StringType(), nullable=True),
    StructField("part", IntegerType(), nullable=True),
    StructField("is_correct", IntegerType(), nullable=True),
    StructField("response_time_ms", LongType(), nullable=True),
    StructField("hour_of_day", IntegerType(), nullable=True),
    StructField("day_of_week", IntegerType(), nullable=True),
])

# ══════════════════════════════════════════════════════════════════════════
# OUTPUT schemas — curated zone
# ══════════════════════════════════════════════════════════════════════════

AGGREGATED_STUDENT_FEATURES_SCHEMA = StructType([
    StructField("user_id", StringType(), nullable=False),
    StructField("total_interactions", LongType(), nullable=False),
    StructField("correct_count", LongType(), nullable=False),
    StructField("incorrect_count", LongType(), nullable=False),
    StructField("accuracy_rate", DoubleType(), nullable=True),
    StructField("avg_response_time_ms", DoubleType(), nullable=True),
    StructField("total_elapsed_time_ms", LongType(), nullable=True),
    StructField("unique_questions_attempted", LongType(), nullable=False),
    StructField("unique_lectures_viewed", LongType(), nullable=False),
    StructField("active_days", LongType(), nullable=False),
    StructField("interactions_part_1", LongType(), nullable=False),
    StructField("interactions_part_2", LongType(), nullable=False),
    StructField("interactions_part_3", LongType(), nullable=False),
    StructField("interactions_part_4", LongType(), nullable=False),
    StructField("interactions_part_5", LongType(), nullable=False),
    StructField("interactions_part_6", LongType(), nullable=False),
    StructField("interactions_part_7", LongType(), nullable=False),
])

USER_VECTORS_SCHEMA = StructType([
    StructField("user_id", StringType(), nullable=False),
    StructField("accuracy_rate", DoubleType(), nullable=True),
    StructField("avg_response_time_ms", DoubleType(), nullable=True),
    StructField("total_interactions", DoubleType(), nullable=True),
    StructField("unique_questions_attempted", DoubleType(), nullable=True),
    StructField("unique_lectures_viewed", DoubleType(), nullable=True),
    StructField("active_days", DoubleType(), nullable=True),
])

RECOMMENDATIONS_SCHEMA = StructType([
    StructField("user_id", StringType(), nullable=False),
    StructField("recommended_user_id", StringType(), nullable=False),
    StructField("similarity_score", DoubleType(), nullable=False),
    StructField("rank", IntegerType(), nullable=False),
])

# ══════════════════════════════════════════════════════════════════════════
# Schema registry  (Governance)
# ══════════════════════════════════════════════════════════════════════════

INPUT_SCHEMA_REGISTRY: dict[str, StructType] = {
    "kt4": KT4_INPUT_SCHEMA,
    "lectures": LECTURES_INPUT_SCHEMA,
    "questions": QUESTIONS_INPUT_SCHEMA,
}

OUTPUT_SCHEMA_REGISTRY: dict[str, StructType] = {
    "aggregated_student_features": AGGREGATED_STUDENT_FEATURES_SCHEMA,
    "user_vectors": USER_VECTORS_SCHEMA,
    "recommendations_batch": RECOMMENDATIONS_SCHEMA,
}

# Column allowlists derived from output schemas  (Privacy)
ALLOWED_OUTPUT_COLUMNS: dict[str, list[str]] = {
    name: [f.name for f in schema.fields]
    for name, schema in OUTPUT_SCHEMA_REGISTRY.items()
}
