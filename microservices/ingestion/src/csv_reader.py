"""
Generic PySpark CSV / TSV reader for the EdNet dataset.

Supports:
  - KT4 interaction logs  (per-user TSV files in a directory)
  - Lectures metadata     (single CSV)
  - Questions metadata    (single CSV)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.types import StructType

from microservices.ingestion.src.schemas import SCHEMA_REGISTRY

logger = logging.getLogger(__name__)


class CSVReaderConfig:
    """Immutable configuration object for a single CSV read operation."""

    def __init__(
        self,
        path: str,
        schema_name: str,
        has_header: bool = True,
        delimiter: str = ",",
        encoding: str = "utf-8",
        glob_pattern: Optional[str] = None,
        custom_schema: Optional[StructType] = None,
    ) -> None:
        self.path = path
        self.schema_name = schema_name
        self.has_header = has_header
        self.delimiter = delimiter
        self.encoding = encoding
        self.glob_pattern = glob_pattern
        # Allow callers to override the registry schema
        self.schema: StructType = custom_schema or SCHEMA_REGISTRY[schema_name]


class EdNetCSVReader:
    """Read EdNet CSV / TSV sources into PySpark DataFrames.

    Parameters
    ----------
    spark : SparkSession
        Active Spark session to use for reading.

    Examples
    --------
    >>> reader = EdNetCSVReader(spark)
    >>> kt4_df = reader.read(CSVReaderConfig(
    ...     path="/data/ednet/KT4",
    ...     schema_name="kt4",
    ...     delimiter="\\t",
    ...     glob_pattern="*.csv",
    ... ))
    >>> kt4_df.printSchema()
    """

    def __init__(self, spark: SparkSession) -> None:
        self._spark = spark

    # ── public API ─────────────────────────────────────────────────────
    def read(self, config: CSVReaderConfig) -> DataFrame:
        """Read a CSV / TSV source into a DataFrame.

        Parameters
        ----------
        config : CSVReaderConfig
            Reader configuration (path, schema, delimiter, …).

        Returns
        -------
        DataFrame
            Raw DataFrame with columns typed according to the schema.

        Raises
        ------
        FileNotFoundError
            When the source path does not exist (local mode only).
        ValueError
            When the resulting DataFrame is empty.
        """
        read_path = self._resolve_path(config)
        logger.info("Reading CSV source '%s' from: %s", config.schema_name, read_path)

        df = (
            self._spark.read.format("csv")
            .option("header", str(config.has_header).lower())
            .option("delimiter", config.delimiter)
            .option("encoding", config.encoding)
            .option("mode", "PERMISSIVE")
            .option("columnNameOfCorruptRecord", "_corrupt_record")
            .schema(config.schema)
            .load(read_path)
        )

        row_count = df.count()
        logger.info(
            "Loaded %d rows for source '%s'.", row_count, config.schema_name
        )

        if row_count == 0:
            raise ValueError(
                f"No data read from '{read_path}' for source '{config.schema_name}'."
            )

        return df

    def read_kt4(
        self,
        path: str,
        glob_pattern: str = "*.csv",
        delimiter: str = "\t",
    ) -> DataFrame:
        """Convenience method to read KT4 interaction logs.

        Parameters
        ----------
        path : str
            Directory containing per-user CSV/TSV files.
        glob_pattern : str
            Glob to filter files inside *path*.
        delimiter : str
            Column delimiter (default ``\\t`` for TSV).

        Returns
        -------
        DataFrame
        """
        cfg = CSVReaderConfig(
            path=path,
            schema_name="kt4",
            delimiter=delimiter,
            glob_pattern=glob_pattern,
        )
        return self.read(cfg)

    def read_lectures(self, path: str) -> DataFrame:
        """Convenience method to read lectures metadata CSV."""
        cfg = CSVReaderConfig(path=path, schema_name="lectures")
        return self.read(cfg)

    def read_questions(self, path: str) -> DataFrame:
        """Convenience method to read questions metadata CSV."""
        cfg = CSVReaderConfig(path=path, schema_name="questions")
        return self.read(cfg)

    # ── internals ──────────────────────────────────────────────────────
    @staticmethod
    def _resolve_path(config: CSVReaderConfig) -> str:
        """Build the final read path, appending a glob when needed.

        For HDFS / S3 paths the glob is simply concatenated.
        For local paths we verify the base directory exists first.
        """
        base = config.path

        # Local-path existence check (skip for hdfs:// s3:// etc.)
        if "://" not in base:
            p = Path(base)
            if not p.exists():
                raise FileNotFoundError(f"Source path does not exist: {base}")

        if config.glob_pattern:
            # Ensure exactly one separator between base and glob
            sep = "" if base.endswith("/") else "/"
            return f"{base}{sep}{config.glob_pattern}"

        return base
