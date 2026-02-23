# Orchestration Layer — Implementation Plan

> Implement this layer first. Every microservice plugs into the contracts defined here.
> No business logic lives here — infrastructure config only.

---

## Overview

| Component | Folder | Files |
|---|---|---|
| Network | `network/` | `network.yml` |
| Docker Compose | `docker_compose/` | 4 service files + 1 root file |
| Healthchecks | `healthchecks/` | 7 shell scripts |
| Scheduler | `scheduler/` | `crontab` + 2 bash scripts |

---

## Tasks

### 1. Network

#### `orchestration/network/network.yml`
- [x] Define a single Docker **bridge network** named `uni_net`
- [x] All compose files will declare this as an **external** network
- [x] Must be created once manually before first `docker compose up`:
  ```bash
  docker network create uni_net
  ```

```yaml
# Target shape
networks:
  uni_net:
    driver: bridge
```

---

### 2. Docker Compose

One file per service group. A root file at the project root wires them all together via `include:`.

> Requires Docker Compose v2.20+

---

#### `orchestration/docker_compose/storage.yml` — HDFS Cluster
- [x] Service: `namenode` — image `bde2020/hadoop-namenode:2.0.0-hadoop3.2.1-java8`, port `9870` (Web UI) + `9000` (RPC)
- [x] Service: `datanode1` — image `bde2020/hadoop-datanode:2.0.0-hadoop3.2.1-java8`
- [x] Service: `datanode2` — same image
- [x] Service: `datanode3` — same image
- [x] Set `HDFS_CONF_dfs_replication=3` on all datanode services
- [x] All services on `uni_net`
- [x] NameNode healthcheck: HTTP poll on `http://namenode:9870`
- [x] Restart policy: `unless-stopped`

---

#### `orchestration/docker_compose/ingestion.yml` — Ingestion Service
- [x] Service: `ingestion` — local build from `microservices/ingestion/docker/`
- [x] Base image: `spark:3.x`
- [x] Env vars: `HDFS_URL=hdfs://namenode:9000`
- [x] `depends_on: namenode` (condition: healthy)
- [x] Mount pipeline source as volume
- [x] Do **not** set `restart: always` — triggered by scheduler only

---

#### `orchestration/docker_compose/processing.yml` — Spark Processing
- [x] Service: `processing` — local build from `microservices/processing/docker/`
- [x] Base image: `spark:3.x`
- [x] Env vars: `HDFS_URL=hdfs://namenode:9000`, `PROCESSING_WINDOW_DAYS=7`
- [x] `depends_on: namenode` (condition: healthy)
- [x] Do **not** set `restart: always` — triggered by scheduler only

---

#### `orchestration/docker_compose/serving.yml` — Serving Layer
- [x] Service: `postgres` — image `postgres:14`, port `5432`
  - Env: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB=recommendations`
  - Healthcheck: `pg_isready -U postgres`
  - Restart: `unless-stopped`
  - Volume: named volume for data persistence
- [x] Service: `recommendation_loader` — local build from `microservices/serving/recommendation_loader/docker/`
  - `depends_on: postgres` (condition: healthy) + `namenode` (condition: healthy)
  - No restart policy — triggered by scheduler
- [x] Service: `recommendation_api` — local build from `microservices/serving/recommendation_api/docker/`
  - Base image: `python:3.11-slim`
  - Port: `8000`
  - `depends_on: postgres` (condition: healthy)
  - Healthcheck: `GET http://localhost:8000/health → 200`
  - Restart: `unless-stopped`

---

#### `docker-compose.yml` *(project root)*
- [x] Use `include:` to pull in all 4 service compose files
- [x] Declare `uni_net` as external network

```yaml
# Target shape
include:
  - orchestration/docker_compose/storage.yml
  - orchestration/docker_compose/ingestion.yml
  - orchestration/docker_compose/processing.yml
  - orchestration/docker_compose/serving.yml

networks:
  uni_net:
    external: true
```

---

### 3. Healthchecks

All scripts must be **executable** (`chmod +x`). Exit `0` = healthy, `1` = unhealthy.

| File | Check |
|---|---|
| `namenode.healthcheck.sh` | `curl -f http://namenode:9870` |
| `datanode.healthcheck.sh` | NameNode REST API confirms datanode registered |
| `postgres.healthcheck.sh` | `pg_isready -h postgres -U postgres` |
| `api.healthcheck.sh` | `curl -f http://localhost:8000/health` |
| `ingestion.healthcheck.sh` | Spark driver process alive check |
| `processing.healthcheck.sh` | Spark driver process alive check |
| `loader.healthcheck.sh` | Python process alive or clean exit 0 |

- [x] Create all 7 scripts in `orchestration/healthchecks/`
- [x] Ensure all are `chmod +x`
- [x] Each script is self-contained (no external dependencies beyond `curl` / `pg_isready`)

---

### 4. Scheduler

#### `orchestration/scheduler/cron/crontab`
- [x] Single cron entry — daily at **02:00 UTC**

```cron
0 2 * * * /scripts/daily_pipeline/run_daily_pipeline.sh >> /var/log/pipeline.log 2>&1
```

---

#### `orchestration/scheduler/scripts/initial_load/run_initial_load.sh` — Script A
- [x] `set -euo pipefail` at top (fail fast)
- [x] Log start timestamp (UTC)
- [x] Step 1: `docker compose run --rm ingestion` (full historical mode)
  - Pass `MODE=initial_load` as env var
  - Wait for exit 0, abort on failure
- [x] Step 2: `docker compose run --rm processing` (full recomputation)
  - Pass `MODE=initial_load`
  - Wait for exit 0, abort on failure
- [x] Step 3: `docker compose run --rm recommendation_loader`
  - Pass `MODE=initial_load`
  - Wait for exit 0, abort on failure
- [x] Log completion timestamp + total duration
- [x] Exit 0 on success, 1 on any step failure

---

#### `orchestration/scheduler/scripts/daily_pipeline/run_daily_pipeline.sh` — Script B
- [x] `set -euo pipefail` at top
- [x] Derive `EVENT_DATE` = yesterday in UTC:
  ```bash
  EVENT_DATE=$(date -u -d "yesterday" +%Y-%m-%d)
  ```
- [x] Log start timestamp + `EVENT_DATE`
- [x] Step 1: `docker compose run --rm ingestion`
  - Pass `MODE=incremental`, `EVENT_DATE`
  - Wait for exit 0, abort on failure
- [x] Step 2: `docker compose run --rm processing`
  - Pass `MODE=incremental`, `PROCESSING_WINDOW_DAYS`
  - Wait for exit 0, abort on failure
- [x] Step 3: `docker compose run --rm recommendation_loader`
  - Wait for exit 0, abort on failure
- [x] Log completion + duration
- [x] Exit 0 on success, 1 on failure

---

## Verification Checklist

### After Writing All Files

- [x] YAML lint — validate each compose file:
  ```bash
  docker compose -f orchestration/docker_compose/storage.yml config --quiet
  docker compose -f orchestration/docker_compose/ingestion.yml config --quiet
  docker compose -f orchestration/docker_compose/processing.yml config --quiet
  docker compose -f orchestration/docker_compose/serving.yml config --quiet
  docker compose -f docker-compose.yml config --quiet
  ```

- [x] Bash syntax check:
  ```bash
  bash -n orchestration/scheduler/scripts/initial_load/run_initial_load.sh
  bash -n orchestration/scheduler/scripts/daily_pipeline/run_daily_pipeline.sh
  ```

- [x] Network name consistency:
  ```bash
  grep -r "uni_net" orchestration/
  ```

- [x] Service name consistency (no typos across files):
  ```bash
  grep -r "namenode\|postgres\|recommendation_api" orchestration/
  ```

- [x] All healthcheck scripts are executable:
  ```bash
  ls -la orchestration/healthchecks/
  ```

- [x] Cron expression `0 2 * * *` validated manually at [crontab.guru](https://crontab.guru/#0_2_*_*_*)

---

## File Inventory (15 files total)

```
orchestration/
├── network/
│   └── network.yml                                         [1]
├── docker_compose/
│   ├── storage.yml                                         [2]
│   ├── ingestion.yml                                       [3]
│   ├── processing.yml                                      [4]
│   └── serving.yml                                         [5]
├── healthchecks/
│   ├── namenode.healthcheck.sh                             [6]
│   ├── datanode.healthcheck.sh                             [7]
│   ├── postgres.healthcheck.sh                             [8]
│   ├── api.healthcheck.sh                                  [9]
│   ├── ingestion.healthcheck.sh                            [10]
│   ├── processing.healthcheck.sh                           [11]
│   └── loader.healthcheck.sh                               [12]
└── scheduler/
    ├── cron/
    │   └── crontab                                         [13]
    └── scripts/
        ├── initial_load/
        │   └── run_initial_load.sh                         [14]
        └── daily_pipeline/
            └── run_daily_pipeline.sh                       [15]

docker-compose.yml  ← project root                         [+1]
```
