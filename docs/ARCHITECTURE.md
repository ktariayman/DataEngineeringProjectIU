# Architecture — University Recommendation System

> *"Designed for production readiness; minimal subset implemented in local environment."*

---

## System Overview

A **batch collaborative filtering recommendation system** for an online learning platform.

- Ingests 100M+ student interaction events (EdNet KT4 format)
- Processes them with Apache Spark to build per-student feature vectors
- Computes cosine similarity between all students (Top-K collaborative filtering)
- Stores precomputed recommendations in PostgreSQL
- Serves them via a JWT-secured FastAPI REST API

**All layers run on a single Docker network (`uni_net`) via Docker Compose.**

---

## Layer Diagram

```
┌───────────────────────────────────────────────────────────┐
│                       Data Sources                        │
│          EdNet KT4 CSVs · EdNet Contents CSVs             │
└────────────────────────┬──────────────────────────────────┘
                         │
                         ▼
┌───────────────────────────────────────────────────────────┐
│             Ingestion Layer  [spark:3.x]                  │
│  file_intake → validation → CSV→Parquet → compaction      │
│                      → HDFS Raw Zone                      │
└────────────────────────┬──────────────────────────────────┘
                         │
                         ▼
┌───────────────────────────────────────────────────────────┐
│             Storage Layer  [bde2020/hadoop]                │
│   HDFS: 1 NameNode + 3 DataNodes (replication=3)          │
│   /data/raw/           ← immutable                        │
│   /data/curated/       ← derived, overwriteable           │
└────────────────────────┬──────────────────────────────────┘
                         │
                         ▼
┌───────────────────────────────────────────────────────────┐
│           Batch Processing Layer  [spark:3.x]             │
│  data_intake → feature_aggregation → feature_engineering  │
│             → similarity_computation                      │
│                      → HDFS Curated Zone                  │
└────────────────────────┬──────────────────────────────────┘
                         │
                         ▼
┌───────────────────────────────────────────────────────────┐
│                  Serving Layer                            │
│  recommendation_loader: HDFS → PostgreSQL (batch ETL)     │
│  recommendation_api:  GET /recommendations/me (FastAPI)   │
└───────────────────────────────────────────────────────────┘
```

---

## Services

| Container | Image | Role | Type |
|---|---|---|---|
| `namenode` | `bde2020/hadoop-namenode` | HDFS metadata server | Always-on |
| `datanode1-3` | `bde2020/hadoop-datanode` | HDFS block storage (×3) | Always-on |
| `postgres` | `postgres:14` | Serving store (recommendations table) | Always-on |
| `recommendation_api` | `uni/recommendation-api:1.0.0` | REST API (FastAPI + JWT) | Always-on |
| `ingestion` | `uni/ingestion:1.0.0` | CSV → Parquet → HDFS raw | Batch (scheduler) |
| `processing` | `uni/processing:1.0.0` | Spark feature engineering + similarity | Batch (scheduler) |
| `recommendation_loader` | `uni/recommendation-loader:1.0.0` | HDFS curated → PostgreSQL | Batch (scheduler) |

---

## HDFS Zone Structure

```
/data/
├── raw/                              ← IMMUTABLE (never modified after write)
│   ├── kt4/
│   │   └── partitions_by_event_date/  ← KT4 events, date-partitioned Parquet
│   └── content/
│       ├── questions/               ← Raw question content
│       └── lectures/                ← Raw lecture content
│
└── curated/                         ← DERIVED (overwritten each batch run)
    ├── Aggregated_student_features/ ← Per-student feature profiles
    ├── User_vectors/                ← Final user embedding vectors
    └── recommendations_batch/       ← Top-K cosine similarity results
```

---

## Scheduler

Two bash scripts orchestrate the pipeline:

| Script | Type | Trigger | What it does |
|---|---|---|---|
| `run_initial_load.sh` | One-time | Manual | Full historical ingest + process + load |
| `run_daily_pipeline.sh` | Cron 02:00 UTC | Automatic | Incremental daily run (yesterday's data) |

Both scripts use `docker compose run --rm <service>` to spin up batch containers on demand.

---

## Data Flow (Step-by-Step)

```
1. SOURCE      KT4 CSVs (>100M rows) + content CSVs
       │
2. INGEST      file_intake → structural_validation → CSV→Parquet
               → compaction (~128–512MB files) → HDFS /data/raw/
       │
3. PROCESS     data_intake (read last N days + join content)
               → feature_aggregation (engagement, skill, stage)
               → feature_engineering (normalization, recency, vectors)
               → similarity_computation (cosine, Top-K)
               → HDFS /data/curated/
       │
4. LOAD        recommendation_loader:
               HDFS /data/curated/recommendations_batch → PostgreSQL
       │
5. SERVE       GET /recommendations/me
               → PostgreSQL recommendations table → JSON response
```

---

## Non-Functional Design

| Property | Implementation |
|---|---|
| **Security** | Non-root containers, JWT auth on API, env-based secrets |
| **Privacy** | Anonymized user IDs only, no PII in any layer |
| **Reliability** | HDFS replication=3, healthchecks on all services, retry logic in scheduler |
| **Idempotency** | All batch jobs can be safely re-run (partition overwrite) |
| **Scalability** | Parquet columnar format, date partitioning, Spark distributed compute |
| **Governance** | Raw zone is immutable, curated zone is derived-only |

---

## Port Map

| Port | Service | URL |
|---|---|---|
| `9870` | HDFS Web UI | http://localhost:9870 |
| `9000` | HDFS RPC | `hdfs://namenode:9000` (internal) |
| `5432` | PostgreSQL | `localhost:5432` |
| `8000` | Recommendation API | http://localhost:8000 |
