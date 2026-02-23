# Orchestration Layer

> This layer owns **all infrastructure config** for the project.
> No business logic lives here — only Docker, networking, health checks, and scheduling.

---

## Table of Contents

- [What This Layer Does](#what-this-layer-does)
- [Prerequisites](#prerequisites)
- [Folder Structure](#folder-structure)
- [Environment Variables](#environment-variables)
- [First-Time Setup](#first-time-setup)
- [Starting the System](#starting-the-system)
- [Running the Pipeline](#running-the-pipeline)
  - [Script A — Initial Load (one-time)](#script-a--initial-load-one-time)
  - [Script B — Daily Pipeline (cron)](#script-b--daily-pipeline-cron)
- [Service Reference](#service-reference)
- [Healthchecks](#healthchecks)
- [Scheduler](#scheduler)
- [Checking System Status](#checking-system-status)
- [Stopping the System](#stopping-the-system)
- [Resetting Everything](#resetting-everything)
- [Troubleshooting](#troubleshooting)

---

## What This Layer Does

The orchestration layer is the **glue** that connects all microservices. It is responsible for:

| Concern | Implementation |
|---|---|
| **Networking** | Single Docker bridge network (`uni_net`) shared by all containers |
| **Service Composition** | Docker Compose files — one per service group |
| **Startup Order** | `depends_on` + healthchecks enforce correct boot order |
| **Restart Policies** | Long-running services restart unless explicitly stopped |
| **Scheduling** | Cron triggers the pipeline daily at 02:00 UTC |
| **Health Monitoring** | Per-service shell scripts used as Docker healthchecks |

---

## Prerequisites

| Requirement | Minimum Version | How to Check |
|---|---|---|
| Docker Engine | 24.x+ | `docker --version` |
| Docker Compose | v2.20+ | `docker compose version` |
| Bash | 4.x+ (Linux/macOS) | `bash --version` |
| `curl` | any | `curl --version` |

> **Windows note:** Run all bash scripts inside **WSL2** or **Git Bash**.
> Docker Desktop on Windows must have WSL2 backend enabled.

---

## Folder Structure

```
orchestration/
│
├── README.md                          ← You are here
├── PLAN.md                            ← Implementation task tracker
│
├── network/
│   └── network.yml                    ← Docker bridge network definition
│
├── docker_compose/
│   ├── storage.yml                    ← HDFS cluster (namenode + 3 datanodes)
│   ├── ingestion.yml                  ← Ingestion batch job (PySpark)
│   ├── processing.yml                 ← Spark batch processing job
│   └── serving.yml                    ← PostgreSQL + Loader + FastAPI
│
├── healthchecks/
│   ├── namenode.healthcheck.sh        ← curl http://namenode:9870
│   ├── datanode.healthcheck.sh        ← NameNode JMX: live nodes >= 1
│   ├── postgres.healthcheck.sh        ← pg_isready
│   ├── api.healthcheck.sh             ← curl http://localhost:8000/health
│   ├── ingestion.healthcheck.sh       ← PID file / clean exit check
│   ├── processing.healthcheck.sh      ← PID file / clean exit check
│   └── loader.healthcheck.sh          ← PID file / clean exit check
│
└── scheduler/
    ├── cron/
    │   └── crontab                    ← 0 2 * * * → run_daily_pipeline.sh
    └── scripts/
        ├── initial_load/
        │   └── run_initial_load.sh    ← Script A: one-time historical load
        └── daily_pipeline/
            └── run_daily_pipeline.sh  ← Script B: daily incremental run
```

The root `docker-compose.yml` (project root, one level up) wires all compose files together using `include:`.

---

## Environment Variables

Copy `.env.example` to `.env` at the project root and fill in your values before running anything:

```bash
cp .env.example .env
```

| Variable | Default | Required | Description |
|---|---|---|---|
| `POSTGRES_USER` | `postgres` | Yes | PostgreSQL username |
| `POSTGRES_PASSWORD` | `changeme` | **Yes — change this** | PostgreSQL password |
| `POSTGRES_DB` | `recommendations` | Yes | Database name |
| `JWT_SECRET` | `changeme` | **Yes — change this** | API auth secret key |
| `PROCESSING_WINDOW_DAYS` | `7` | No | Days of history the Spark job recomputes |

> **Security rule:** Never commit `.env` to version control.
> Generate a strong JWT secret with: `openssl rand -hex 32`

---

## First-Time Setup

Run these steps **once** on a fresh machine before anything else.

### Step 1 — Create the shared Docker network

```bash
docker network create uni_net
```

This network is declared as `external` in all compose files, so it must exist before any `docker compose up`. You only ever do this once.

To verify it exists:

```bash
docker network ls | grep uni_net
```

### Step 2 — Configure environment variables

```bash
cp .env.example .env
# Edit .env — at minimum, change POSTGRES_PASSWORD and JWT_SECRET
```

### Step 3 — Pull all Docker images

```bash
docker compose pull
```

This downloads all images that are not built locally (HDFS, PostgreSQL).

### Step 4 — Validate compose files (optional sanity check)

```bash
docker compose -f orchestration/docker_compose/storage.yml config --quiet
docker compose -f orchestration/docker_compose/ingestion.yml config --quiet
docker compose -f orchestration/docker_compose/processing.yml config --quiet
docker compose -f orchestration/docker_compose/serving.yml config --quiet
docker compose config --quiet
```

No output = valid YAML. Any error here means a config problem before you've started anything.

---

## Starting the System

Start **only the long-running services** (HDFS cluster + PostgreSQL + API). The batch jobs (ingestion, processing, loader) are **not** started here — they are run by the scheduler.

```bash
# From the project root
docker compose up -d namenode datanode1 datanode2 datanode3 postgres recommendation_api
```

### Expected startup order (enforced by depends_on + healthchecks)

```
namenode starts
    │
    │  (waits for namenode healthcheck to pass — up to 5 min on first start)
    ▼
datanode1 + datanode2 + datanode3 start
    │
    │  (HDFS cluster is now fully operational)

postgres starts independently
    │
    │  (waits for pg_isready healthcheck to pass)
    ▼
recommendation_api starts
```

> **First-time note:** The NameNode needs up to **60–120 seconds** to format its filesystem and become healthy on the very first start. DataNodes start once NameNode is healthy. This is normal.

### Verify all services are up and healthy:

```bash
docker compose ps
```

Expected output:

```
NAME                  STATUS
namenode              Up (healthy)
datanode1             Up
datanode2             Up
datanode3             Up
postgres              Up (healthy)
recommendation_api    Up (healthy)
```

---

## Running the Pipeline

### Script A — Initial Load (one-time)

Run this **exactly once** to bootstrap the system with the full historical EdNet/KT4 dataset. This may take several hours depending on data volume.

```bash
bash orchestration/scheduler/scripts/initial_load/run_initial_load.sh
```

**What it does, in order:**

```
Step 1/3  →  docker compose run --rm ingestion   (MODE=initial_load)
Step 2/3  →  docker compose run --rm processing  (MODE=initial_load)
Step 3/3  →  docker compose run --rm recommendation_loader (MODE=initial_load)
```

Each step must exit with code `0` before the next begins. If any step fails, the script aborts immediately and prints the failing step.

**Example output:**
```
[2026-02-23T15:00:00Z] ======================================================
[2026-02-23T15:00:00Z]   Initial Load — starting
[2026-02-23T15:00:00Z] ======================================================
[2026-02-23T15:00:01Z] Step 1/3: Running ingestion (MODE=initial_load) ...
[2026-02-23T17:12:04Z] Step 1/3: Ingestion completed successfully.
[2026-02-23T17:12:04Z] Step 2/3: Running processing (MODE=initial_load) ...
...
[2026-02-23T19:45:22Z]   Initial Load — COMPLETED
[2026-02-23T19:45:22Z]   Total duration: 10522s
```

---

### Script B — Daily Pipeline (cron)

This runs automatically every day at **02:00 UTC** via cron. You can also trigger it manually for testing or re-runs.

**Manual trigger:**
```bash
bash orchestration/scheduler/scripts/daily_pipeline/run_daily_pipeline.sh
```

**What it does, in order:**

```
Derive EVENT_DATE = yesterday in UTC  (e.g. 2026-02-22)

Step 1/3  →  docker compose run --rm ingestion
             (MODE=incremental, EVENT_DATE=2026-02-22)

Step 2/3  →  docker compose run --rm processing
             (MODE=incremental, PROCESSING_WINDOW_DAYS=7)

Step 3/3  →  docker compose run --rm recommendation_loader
             (MODE=incremental)
```

**To override the processing window:**
```bash
PROCESSING_WINDOW_DAYS=14 bash orchestration/scheduler/scripts/daily_pipeline/run_daily_pipeline.sh
```

**Pipeline logs** are appended to `/var/log/pipeline.log` when running via cron.

---

## Service Reference

| Service | Compose File | Image | Ports | Restart |
|---|---|---|---|---|
| `namenode` | `storage.yml` | `bde2020/hadoop-namenode:2.0.0-hadoop3.2.1-java8` | 9870, 9000 | `unless-stopped` |
| `datanode1/2/3` | `storage.yml` | `bde2020/hadoop-datanode:2.0.0-hadoop3.2.1-java8` | — | `unless-stopped` |
| `postgres` | `serving.yml` | `postgres:14` | 5432 | `unless-stopped` |
| `recommendation_api` | `serving.yml` | Local build (`python:3.11-slim`) | 8000 | `unless-stopped` |
| `ingestion` | `ingestion.yml` | Local build (`spark:3.x`) | — | ❌ None (batch job) |
| `processing` | `processing.yml` | Local build (`spark:3.x`) | — | ❌ None (batch job) |
| `recommendation_loader` | `serving.yml` | Local build (Python) | — | ❌ None (batch job) |

### Key design rule

Services split into two categories:

- **Always-on** (`restart: unless-stopped`) — HDFS, PostgreSQL, API. These run continuously and serve live traffic.
- **Batch jobs** (no restart policy) — Ingestion, Processing, Loader. These are triggered by the scheduler via `docker compose run --rm`, run to completion, and exit. They are **never** left running.

---

## Healthchecks

Docker uses these scripts to determine if each service is ready. `depends_on: condition: service_healthy` blocks dependent services until the check passes.

| Script | Frequency | What It Tests |
|---|---|---|
| `namenode.healthcheck.sh` | Every 30s | HTTP 200 from NameNode Web UI (`http://namenode:9870`) |
| `datanode.healthcheck.sh` | Every 30s | At least 1 DataNode registered in NameNode JMX API |
| `postgres.healthcheck.sh` | Every 10s | `pg_isready` returns success |
| `api.healthcheck.sh` | Every 30s | HTTP 200 from `GET /health` on the FastAPI app |
| `ingestion.healthcheck.sh` | On demand | Spark driver PID alive, or clean exit = healthy |
| `processing.healthcheck.sh` | On demand | Spark driver PID alive, or clean exit = healthy |
| `loader.healthcheck.sh` | On demand | Python process PID alive, or clean exit = healthy |

> **Batch job healthchecks:** A completed batch job that exited cleanly (`exit 0`) is reported as healthy. This is intentional — a clean exit means success, not failure.

### Manually running a healthcheck

```bash
docker exec namenode /bin/sh -c "curl -f http://namenode:9870 && echo OK"
docker exec postgres pg_isready -U postgres
docker exec recommendation_api curl -f http://localhost:8000/health
```

---

## Scheduler

### How cron triggers the pipeline

The crontab file at `orchestration/scheduler/cron/crontab` is mounted into a cron container (or the host cron). The entry:

```cron
0 2 * * * /scripts/daily_pipeline/run_daily_pipeline.sh >> /var/log/pipeline.log 2>&1
```

- Runs at **02:00 UTC every day**
- All stdout and stderr go to `/var/log/pipeline.log`
- To validate the cron expression: [crontab.guru/#0_2_*_*_*](https://crontab.guru/#0_2_*_*_*)

### Checking pipeline logs

```bash
# If running inside a container
docker exec <cron_container> tail -f /var/log/pipeline.log

# If running on the host directly
tail -f /var/log/pipeline.log
```

### Manually testing the daily pipeline

```bash
# Full dry run (actual data)
bash orchestration/scheduler/scripts/daily_pipeline/run_daily_pipeline.sh

# Override EVENT_DATE to reprocess a specific day
EVENT_DATE=2026-02-01 bash orchestration/scheduler/scripts/daily_pipeline/run_daily_pipeline.sh
```

---

## Checking System Status

### All containers

```bash
docker compose ps
```

### Container logs

```bash
# Follow live logs for a specific service
docker compose logs -f namenode
docker compose logs -f postgres
docker compose logs -f recommendation_api

# Last 100 lines from all services
docker compose logs --tail=100
```

### HDFS Web UI

Open in browser: [http://localhost:9870](http://localhost:9870)

- **Overview tab** → cluster health, total capacity
- **Datanodes tab** → confirm 3 nodes are live
- **Utilities → Browse the file system** → inspect HDFS directories

### PostgreSQL

```bash
# Connect directly
docker exec -it postgres psql -U postgres -d recommendations

# Quick check — count recommendations
docker exec postgres psql -U postgres -d recommendations \
  -c "SELECT COUNT(*), generation_date FROM recommendations GROUP BY generation_date ORDER BY generation_date DESC LIMIT 10;"
```

### API

```bash
# Health endpoint
curl http://localhost:8000/health

# Recommendations (requires JWT — replace TOKEN)
curl -H "Authorization: Bearer TOKEN" http://localhost:8000/recommendations/me
```

---

## Stopping the System

### Stop all services (containers keep state)

```bash
docker compose stop
```

### Stop and remove containers (data volumes preserved)

```bash
docker compose down
```

### Stop specific services only

```bash
docker compose stop recommendation_api
docker compose stop namenode datanode1 datanode2 datanode3
```

---

## Resetting Everything

> ⚠️ **Destructive — deletes all HDFS data and PostgreSQL data.**
> Only do this on a development machine or when starting from scratch.

```bash
# Remove containers AND named volumes (all data deleted)
docker compose down -v

# Remove the shared network
docker network rm uni_net
```

After a full reset, go back to [First-Time Setup](#first-time-setup) to start again.

---

## Troubleshooting

### DataNodes don't start / stay unhealthy

**Symptom:** `datanode1` exits immediately or never reaches `healthy`.

**Cause:** DataNodes wait for the NameNode healthcheck to pass. On first boot, the NameNode needs 60–120 seconds to format its filesystem.

**Fix:** Wait for NameNode to become healthy first, then check datanodes:
```bash
docker compose ps namenode   # Wait until Status shows "(healthy)"
docker compose logs datanode1
```

---

### NameNode healthcheck fails

**Symptom:** `namenode` stays in `starting` state indefinitely.

**Fix 1 — Check if port 9870 is already in use:**
```bash
# On Linux/macOS
lsof -i :9870
# On Windows
netstat -ano | findstr 9870
```

**Fix 2 — Check NameNode logs for errors:**
```bash
docker compose logs namenode | tail -50
```

**Fix 3 — First-ever run may need a fresh volume:**
```bash
docker compose down -v
docker compose up -d namenode
```

---

### PostgreSQL fails to start

**Symptom:** `postgres` container exits immediately.

**Common cause:** A stale volume from a previous run with different `POSTGRES_USER` or `POSTGRES_DB`.

**Fix:**
```bash
docker compose down -v          # Remove old volume
docker compose up -d postgres   # Start fresh
```

---

### Pipeline script fails at Step 1/2/3

**Symptom:** Script prints `ERROR: Step N failed` and exits.

**What to check:**
```bash
# See what the batch job container printed
docker compose logs ingestion    # or processing / recommendation_loader

# Re-run the specific step manually for debugging
docker compose run --rm -e MODE=incremental -e EVENT_DATE=2026-02-22 ingestion
```

The batch container's exit code drives the pipeline — a non-zero exit aborts everything. Fix the root error in the microservice, then re-run the pipeline script.

---

### `uni_net` network not found

**Symptom:** `docker compose up` fails with `network uni_net declared as external, but could not be found`.

**Fix:**
```bash
docker network create uni_net
```

---

### Docker Compose version too old (no `include:` support)

**Symptom:** `docker compose config` fails with `unknown key: include`.

**Fix:** Upgrade Docker Compose to **v2.20 or higher**:
```bash
docker compose version   # Must be >= 2.20.0
```

On Linux:
```bash
sudo apt-get update && sudo apt-get install docker-compose-plugin
```

On macOS / Windows: Update Docker Desktop.
