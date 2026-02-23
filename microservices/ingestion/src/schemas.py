"""
EdNet dataset schema definitions for PySpark.

Governance
----------
- License  : CC BY-NC 4.0 – non-commercial use only.
- Citation : Choi et al., "EdNet: A Large-Scale Hierarchical Dataset in
             Education", 2020.  https://arxiv.org/abs/1912.03072

References
----------
- KT4 format : https://github.com/riiid/ednet#kt4
- Contents   : https://github.com/riiid/ednet#contents
"""

from pyspark.sql.types import (
    StructType,
    StructField,
    LongType,
    StringType,
    IntegerType,
)

# ═══════════════════════════════════════════════════════════════════════════
# Schema version tracking  (Governance)
#
# Bump these when a column is added / removed / renamed / retyped.
# The lineage module records these alongside every pipeline run so that
# downstream consumers know which schema produced their data.
# ═══════════════════════════════════════════════════════════════════════════
KT4_SCHEMA_VERSION = "1.0.0"
LECTURES_SCHEMA_VERSION = "1.0.0"
QUESTIONS_SCHEMA_VERSION = "1.0.0"

SCHEMA_VERSIONS: dict[str, str] = {
    "kt4": KT4_SCHEMA_VERSION,
    "lectures": LECTURES_SCHEMA_VERSION,
    "questions": QUESTIONS_SCHEMA_VERSION,
}

# ═══════════════════════════════════════════════════════════════════════════
# KT4 – per-user interaction logs  (TSV, one file per user)
# Columns: timestamp, action_type, item_id, source, user_answer,
#           platform, elapsed_time
# ═══════════════════════════════════════════════════════════════════════════
KT4_SCHEMA = StructType(
    [
        StructField("timestamp", LongType(), nullable=False),
        StructField("action_type", StringType(), nullable=False),
        StructField("item_id", StringType(), nullable=False),
        StructField("source", StringType(), nullable=True),
        StructField("user_answer", StringType(), nullable=True),
        StructField("platform", StringType(), nullable=True),
        StructField("elapsed_time", LongType(), nullable=True),
    ]
)

# ═══════════════════════════════════════════════════════════════════════════
# Lectures metadata  (CSV)
# Columns: lecture_id, tags, part
# ═══════════════════════════════════════════════════════════════════════════
LECTURES_SCHEMA = StructType(
    [
        StructField("lecture_id", StringType(), nullable=False),
        StructField("tags", StringType(), nullable=True),
        StructField("part", IntegerType(), nullable=True),
    ]
)

# ═══════════════════════════════════════════════════════════════════════════
# Questions metadata  (CSV)
# Columns: question_id, bundle_id, explanation_id, correct_answer,
#           part, tags
# ═══════════════════════════════════════════════════════════════════════════
QUESTIONS_SCHEMA = StructType(
    [
        StructField("question_id", StringType(), nullable=False),
        StructField("bundle_id", StringType(), nullable=True),
        StructField("explanation_id", StringType(), nullable=True),
        StructField("correct_answer", StringType(), nullable=True),
        StructField("part", IntegerType(), nullable=True),
        StructField("tags", StringType(), nullable=True),
    ]
)

# Convenience mapping used by the generic CSV reader
SCHEMA_REGISTRY: dict[str, StructType] = {
    "kt4": KT4_SCHEMA,
    "lectures": LECTURES_SCHEMA,
    "questions": QUESTIONS_SCHEMA,
}

# ═══════════════════════════════════════════════════════════════════════════
# Column allowlists derived from schemas  (Privacy)
#
# These are the *only* columns that will survive the privacy guardrail.
# Keeps the allowlist in sync with the schema definitions above.
# ═══════════════════════════════════════════════════════════════════════════
ALLOWED_COLUMNS: dict[str, list[str]] = {
    name: [f.name for f in schema.fields]
    for name, schema in SCHEMA_REGISTRY.items()
}
