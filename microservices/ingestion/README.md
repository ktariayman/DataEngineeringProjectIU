# Ingestion Microservice

**Role in the pipeline:** First stage — reads raw EdNet CSV files, validates structure, enforces privacy guardrails, converts to Parquet, and writes to the HDFS raw zone.

```mermaid
flowchart LR
    A["EdNet CSV files"] --> B["Ingestion"]
    B --> C["HDFS raw zone"]
    C --> D["consumed by Processing"]
```

---

## Pipeline Stages

The orchestrator (`pipelines/ingest_ednet.py`) drives data through five sequential stages:

### 1. File Intake — `pipelines/file_intake/`

Reads EdNet CSV/TSV files into Spark DataFrames. Handles three file types: **KT4** (per-user interactions), **questions** (metadata), and **lectures** (metadata). Derives `event_date` from epoch timestamps and extracts `user_id` from filenames.

### 2. Structural Validation — `pipelines/structural_validation/`

Checks each DataFrame before the pipeline proceeds:

- Required-column presence
- Non-empty row count
- Null ratio ≤ 5 % per column
- Type casting and whitespace normalisation

KT4 validation failure is **fatal** — the pipeline aborts to prevent bad data from propagating.

### 3. Privacy Guardrails — `src/privacy.py`

Prevents PII from entering the data lake:

- **PII column-name scan** — regex detects patterns like `name`, `email`, `phone`, `address`
- **Column allowlist** — only columns listed in `src/schemas.py` (`ALLOWED_COLUMNS`) are retained; all others are dropped

### 4. Format Conversion & Compaction — `src/format_converter.py`, `src/compactor.py`

- Converts CSV to **Snappy-compressed Parquet** (~70 % smaller, columnar I/O)
- Compacts many small files into ~128 MB files to reduce NameNode metadata overhead

### 5. Raw Storage Write — `pipelines/raw_storage_write/`

Writes final Parquet files to HDFS:

| Mode | Behaviour |
|---|---|
| **Initial** | Full overwrite (one-time historical load) |
| **Daily** | Append-only (adds new day's data to existing partitions) |

KT4 data is partitioned by `event_date`. Lecture and question metadata are overwritten on each run.

---

## Cross-Cutting Modules

| Module | Purpose |
|---|---|
| `src/checksum.py` | SHA-256 hash verification on source files |
| `src/lineage.py` | JSON audit record per run (source path, row counts, schema version, timestamps) |
| `src/retry.py` | Exponential backoff (1 s → 2 s → 4 s …) for transient HDFS errors |
| `src/logging_config.py` | Structured JSON logging |
| `src/spark_session.py` | Configured Spark session factory (memory limits, executor settings) |

---

## Configuration

All tunables in `config/ingestion_config.yaml`:

- Spark resource limits (memory, executors)
- Source and target HDFS paths
- Validation thresholds (max null ratio)
- Compaction target file size
- Feature toggles (checksum, privacy scan, lineage)

No code changes required to modify behaviour.

---

## Non-Functional Requirements

| Category | Implementation |
|---|---|
| **Reliability** | Retry with exponential backoff on HDFS writes; SHA-256 checksum verification; KT4 validation failure aborts early; idempotent writes (overwrite / append) |
| **Scalability** | Spark with AQE + dynamic allocation (1–10 executors); date partitioning; Snappy Parquet (~70 % compression); file compaction to ~128 MB |
| **Maintainability** | Modular pipeline (one folder per stage); YAML config; structured JSON logging; lineage audit trail |
| **Security** | Non-root container; input validation at pipeline boundary; secrets via environment variables |
| **Privacy** | PII column-name regex scan; column allowlists drop anything not explicitly permitted |
| **Governance** | Schema contract enforcement; lineage metadata per run; checksum manifest for auditability |
