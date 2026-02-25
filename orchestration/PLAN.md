# Orchestration Layer — Implementation Plan

> Infrastructure config only — no business logic.
> All tasks complete.

---

## Component Summary

| Component | Folder | Files |
|---|---|---|
| Network | `network/` | `network.yml` |
| Docker Compose | `docker_compose/` | 4 service files + 1 root include |
| Healthchecks | `healthchecks/` | 7 shell scripts |
| Scheduler | `scheduler/` | `crontab` + 2 pipeline scripts |

---

## Tasks

### 1. Network — `network/network.yml`

- Bridge network `uni_net`, declared `external` in all compose files
- Created manually once: `docker network create uni_net`

---

### 2. Docker Compose

One file per service group. Root `docker-compose.yml` wires them via `include:` (Compose v2.20+).

#### `storage.yml` — HDFS Cluster

- `namenode` → `bde2020/hadoop-namenode:2.0.0-hadoop3.2.1-java8`, ports 9870 + 9000
- `datanode1/2/3` → same family image, `dfs_replication=3`
- Healthcheck: HTTP poll `http://namenode:9870`
- Restart: `unless-stopped`, network: `uni_net`

#### `ingestion.yml` — PySpark Batch Job

- Local build (`spark:3.x`), `HDFS_URL=hdfs://namenode:9000`
- `depends_on: namenode (healthy)`, no restart policy (scheduler-triggered)

#### `processing.yml` — Spark Processing

- Local build (`spark:3.x`), `HDFS_URL`, `PROCESSING_WINDOW_DAYS=7`
- `depends_on: namenode (healthy)`, no restart policy

#### `serving.yml` — PostgreSQL + Loader + API

- `postgres` → `postgres:14`, port 5432, healthcheck `pg_isready`, `unless-stopped`
- `recommendation_loader` → depends on postgres + namenode, no restart
- `recommendation_api` → `python:3.11-slim`, port 8000, healthcheck `/health`, `unless-stopped`

#### `docker-compose.yml` (project root)

- `include:` all 4 compose files, `uni_net` external network

---

### 3. Healthchecks

All scripts: `chmod +x`, exit `0` → healthy, exit `1` → unhealthy.

| Script | Method |
|---|---|
| `namenode.healthcheck.sh` | `curl -f http://namenode:9870` |
| `datanode.healthcheck.sh` | NameNode JMX → live node count ≥ 1 |
| `postgres.healthcheck.sh` | `pg_isready -h postgres -U postgres` |
| `api.healthcheck.sh` | `curl -f http://localhost:8000/health` |
| `ingestion.healthcheck.sh` | Spark driver PID alive or clean exit |
| `processing.healthcheck.sh` | Spark driver PID alive or clean exit |
| `loader.healthcheck.sh` | Python PID alive or clean exit |

- All 7 created, executable, self-contained

---

### 4. Scheduler

#### `crontab`

- `0 2 * * *` → `run_daily_pipeline.sh >> /var/log/pipeline.log 2>&1`

#### `run_initial_load.sh` — Script A (one-time)

- `set -euo pipefail`
- Steps 1→2→3: ingestion → processing → loader (all `MODE=initial_load`)
- Each step must exit `0`; failure aborts
- Logs start/end timestamps + total duration

#### `run_daily_pipeline.sh` — Script B (daily)

- `set -euo pipefail`, derives `EVENT_DATE=yesterday (UTC)`
- Steps 1→2→3: ingestion → processing → loader (`MODE=incremental`)
- Retry logic, configurable `PROCESSING_WINDOW_DAYS`
- Logs start/end timestamps + total duration

---

## Verification Checklist

- `docker compose config --quiet` on all 5 YAML files
- `bash -n` on both pipeline scripts
- `grep -r "uni_net"` — consistent network name
- `grep -r "namenode\|postgres\|recommendation_api"` — service names match
- `ls -la orchestration/healthchecks/` — all executable
- Cron expression validated at [crontab.guru](https://crontab.guru/#0_2_*_*_*)

---

## File Inventory (15 files + 1 root)

```
orchestration/
├── network/network.yml                        [1]
├── docker_compose/
│   ├── storage.yml                            [2]
│   ├── ingestion.yml                          [3]
│   ├── processing.yml                         [4]
│   └── serving.yml                            [5]
├── healthchecks/
│   ├── namenode.healthcheck.sh                [6]
│   ├── datanode.healthcheck.sh                [7]
│   ├── postgres.healthcheck.sh                [8]
│   ├── api.healthcheck.sh                     [9]
│   ├── ingestion.healthcheck.sh               [10]
│   ├── processing.healthcheck.sh              [11]
│   └── loader.healthcheck.sh                  [12]
└── scheduler/
    ├── cron/crontab                           [13]
    └── scripts/
        ├── initial_load/run_initial_load.sh   [14]
        └── daily_pipeline/run_daily_pipeline.sh [15]

docker-compose.yml                             [+1]
```
