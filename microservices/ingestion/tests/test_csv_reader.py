"""
Unit tests for EdNetCSVReader.

These tests write small temporary CSV / TSV files and verify that the reader
produces correct DataFrames with the expected schemas and data.
"""

from __future__ import annotations

import os
import sys
import textwrap
from pathlib import Path

import pytest
from pyspark.sql import SparkSession
from pyspark.sql.types import LongType, StringType, IntegerType

# Add project root to path for direct execution
_project_root = str(Path(__file__).resolve().parents[3])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from microservices.ingestion.src.csv_reader import CSVReaderConfig, EdNetCSVReader


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures – tiny CSV / TSV files
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture()
def kt4_dir(tmp_path: Path) -> Path:
    """Create a small KT4-style TSV directory with two user files."""
    data_dir = tmp_path / "kt4"
    data_dir.mkdir()

    # user_0001.csv
    (data_dir / "user_0001.csv").write_text(
        textwrap.dedent("""\
            timestamp\taction_type\titem_id\tsource\tuser_answer\tplatform\telapsed_time
            1566780382000\tenter\tq100\tmain\t\tios\t0
            1566780392000\trespond\tq100\tmain\ta\tios\t10000
        """),
        encoding="utf-8",
    )

    # user_0002.csv
    (data_dir / "user_0002.csv").write_text(
        textwrap.dedent("""\
            timestamp\taction_type\titem_id\tsource\tuser_answer\tplatform\telapsed_time
            1566780400000\tenter\tq200\trecommend\t\tandroid\t0
        """),
        encoding="utf-8",
    )
    return data_dir


@pytest.fixture()
def lectures_file(tmp_path: Path) -> Path:
    fp = tmp_path / "lectures.csv"
    fp.write_text(
        textwrap.dedent("""\
            lecture_id,tags,part
            L001,math;algebra,1
            L002,english;reading,3
        """),
        encoding="utf-8",
    )
    return fp


@pytest.fixture()
def questions_file(tmp_path: Path) -> Path:
    fp = tmp_path / "questions.csv"
    fp.write_text(
        textwrap.dedent("""\
            question_id,bundle_id,explanation_id,correct_answer,part,tags
            q100,b10,e10,a,2,math
            q200,b20,e20,c,5,english;reading
        """),
        encoding="utf-8",
    )
    return fp


# ═══════════════════════════════════════════════════════════════════════════
# Tests – KT4
# ═══════════════════════════════════════════════════════════════════════════

class TestReadKT4:
    def test_row_count(self, spark: SparkSession, kt4_dir: Path) -> None:
        print("\n[TEST] Read KT4 TSV files - row count")
        reader = EdNetCSVReader(spark)
        df = reader.read_kt4(path=str(kt4_dir))
        count = df.count()
        print(f"  Source: {kt4_dir}")
        print(f"  Rows loaded: {count}")
        print(f"  ✓ Expected 3 rows (2 from user_0001, 1 from user_0002)")
        assert count == 3

    def test_schema_types(self, spark: SparkSession, kt4_dir: Path) -> None:
        print("\n[TEST] Read KT4 TSV files - schema validation")
        reader = EdNetCSVReader(spark)
        df = reader.read_kt4(path=str(kt4_dir))
        fields = {f.name: f.dataType for f in df.schema.fields}
        print(f"  Columns: {list(fields.keys())}")
        print(f"  timestamp: {fields['timestamp']}")
        print(f"  action_type: {fields['action_type']}")
        print(f"  item_id: {fields['item_id']}")
        print(f"  elapsed_time: {fields['elapsed_time']}")
        print(f"  ✓ All types match KT4 schema")

        assert isinstance(fields["timestamp"], LongType)
        assert isinstance(fields["action_type"], StringType)
        assert isinstance(fields["item_id"], StringType)
        assert isinstance(fields["elapsed_time"], LongType)

    def test_values(self, spark: SparkSession, kt4_dir: Path) -> None:
        print("\n[TEST] Read KT4 TSV files - data values")
        reader = EdNetCSVReader(spark)
        df = reader.read_kt4(path=str(kt4_dir))
        rows = df.orderBy("timestamp").collect()
        print(f"  Row 0: action={rows[0]['action_type']}, item={rows[0]['item_id']}")
        print(f"  Row 1: action={rows[1]['action_type']}, answer={rows[1]['user_answer']}")
        print(f"  ✓ Values parsed correctly")

        assert rows[0]["action_type"] == "enter"
        assert rows[0]["item_id"] == "q100"
        assert rows[1]["user_answer"] == "a"


# ═══════════════════════════════════════════════════════════════════════════
# Tests – Lectures
# ═══════════════════════════════════════════════════════════════════════════

class TestReadLectures:
    def test_row_count(self, spark: SparkSession, lectures_file: Path) -> None:
        print("\n[TEST] Read lectures.csv - row count")
        reader = EdNetCSVReader(spark)
        df = reader.read_lectures(path=str(lectures_file))
        count = df.count()
        print(f"  Source: {lectures_file}")
        print(f"  Rows loaded: {count}")
        print(f"  ✓ Expected 2 lectures")
        assert count == 2

    def test_schema(self, spark: SparkSession, lectures_file: Path) -> None:
        print("\n[TEST] Read lectures.csv - schema validation")
        reader = EdNetCSVReader(spark)
        df = reader.read_lectures(path=str(lectures_file))
        fields = {f.name: f.dataType for f in df.schema.fields}
        print(f"  Columns: {list(fields.keys())}")
        print(f"  lecture_id: {fields['lecture_id']}")
        print(f"  part: {fields['part']}")
        print(f"  ✓ Schema matches lectures definition")

        assert isinstance(fields["lecture_id"], StringType)
        assert isinstance(fields["part"], IntegerType)

    def test_values(self, spark: SparkSession, lectures_file: Path) -> None:
        print("\n[TEST] Read lectures.csv - data values")
        reader = EdNetCSVReader(spark)
        df = reader.read_lectures(path=str(lectures_file))
        row = df.filter(df.lecture_id == "L001").first()
        print(f"  L001 tags: {row['tags']}")
        print(f"  ✓ Tags parsed with semicolon delimiter")
        assert row["tags"] == "math;algebra"


# ═══════════════════════════════════════════════════════════════════════════
# Tests – Questions
# ═══════════════════════════════════════════════════════════════════════════

class TestReadQuestions:
    def test_row_count(self, spark: SparkSession, questions_file: Path) -> None:
        print("\n[TEST] Read questions.csv - row count")
        reader = EdNetCSVReader(spark)
        df = reader.read_questions(path=str(questions_file))
        count = df.count()
        print(f"  Source: {questions_file}")
        print(f"  Rows loaded: {count}")
        print(f"  ✓ Expected 2 questions")
        assert count == 2

    def test_schema(self, spark: SparkSession, questions_file: Path) -> None:
        print("\n[TEST] Read questions.csv - schema validation")
        reader = EdNetCSVReader(spark)
        df = reader.read_questions(path=str(questions_file))
        fields = {f.name: f.dataType for f in df.schema.fields}
        print(f"  Columns: {list(fields.keys())}")
        print(f"  question_id: {fields['question_id']}")
        print(f"  correct_answer: {fields['correct_answer']}")
        print(f"  part: {fields['part']}")
        print(f"  ✓ Schema matches questions definition")

        assert isinstance(fields["question_id"], StringType)
        assert isinstance(fields["correct_answer"], StringType)
        assert isinstance(fields["part"], IntegerType)

    def test_values(self, spark: SparkSession, questions_file: Path) -> None:
        print("\n[TEST] Read questions.csv - data values")
        reader = EdNetCSVReader(spark)
        df = reader.read_questions(path=str(questions_file))
        row = df.filter(df.question_id == "q200").first()
        print(f"  q200 correct_answer: {row['correct_answer']}")
        print(f"  q200 part: {row['part']}")
        print(f"  ✓ Values parsed correctly")
        assert row["correct_answer"] == "c"
        assert row["part"] == 5


# ═══════════════════════════════════════════════════════════════════════════
# Tests – Error handling
# ═══════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_missing_path_raises(self, spark: SparkSession) -> None:
        print("\n[TEST] Missing path raises FileNotFoundError")
        reader = EdNetCSVReader(spark)
        print("  Attempting to read non-existent path...")
        with pytest.raises(FileNotFoundError):
            reader.read_kt4(path="/nonexistent/path/to/kt4")
        print("  ✓ FileNotFoundError raised as expected")

    def test_custom_schema_override(
        self, spark: SparkSession, kt4_dir: Path
    ) -> None:
        """Passing a custom schema via CSVReaderConfig should override the registry."""
        print("\n[TEST] Custom schema override")
        from pyspark.sql.types import StructType, StructField, StringType

        custom = StructType(
            [StructField("timestamp", StringType()), StructField("action_type", StringType())]
        )
        cfg = CSVReaderConfig(
            path=str(kt4_dir),
            schema_name="kt4",
            delimiter="\t",
            glob_pattern="*.csv",
            custom_schema=custom,
        )
        reader = EdNetCSVReader(spark)
        df = reader.read(cfg)
        print(f"  Custom schema columns: {df.columns}")
        print(f"  timestamp type: {df.schema['timestamp'].dataType}")
        print(f"  ✓ Custom schema overrides registry")
        assert len(df.columns) == 2
        assert isinstance(df.schema["timestamp"].dataType, StringType)
