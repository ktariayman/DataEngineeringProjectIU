# Setup Guide — University Recommendation System

> Step-by-step instructions to run the full system locally from scratch.

---

## ⚡ Quick Start (run everything in one command)

Once you have the prerequisites and dataset in place:

```bash
bash run_all.sh
```

This single script handles everything: network → build → HDFS → PostgreSQL → ingestion → processing → loader → API.  
When it finishes, the API is live at **http://localhost:8000**.

For manual step-by-step control, continue reading below.

---

## Prerequisites

Install the following before starting:

| Tool | Version | Notes |
|---|---|---|
| **Docker Desktop** | 4.x+ | Must be running. Includes Docker Compose v2. |
| **Docker Compose** | **v2.20+** | Required for the `include:` directive used by the root compose file. Check: `docker compose version` |
| **Git** | Any | For cloning the repository |
| **Bash** | Any | Git Bash (Windows), Terminal (Mac/Linux) for running scheduler scripts |

**Free ports required:**

| Port | Service |
|---|---|
| `9870` | HDFS Web UI |
| `9000` | HDFS RPC |
| `5432` | PostgreSQL |
| `8000` | Recommendation API |

---

## Step 1 — Clone the Repository

```bash
git clone <repository-url>
cd DataEngineeringProjectIU
```

---

## Step 2 — Configure Environment Variables

```bash
# Copy the example env file
cp .env.example .env
```

Open `.env` and update the values:

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=changeme        # change to something secure
POSTGRES_DB=recommendations
JWT_SECRET=changeme               # generate with: openssl rand -hex 32
PROCESSING_WINDOW_DAYS=7
```

> **Note:** The `.env` file is gitignored. Never commit real secrets.

---

## Step 3 — Place the Dataset

The ingestion service expects the EdNet dataset at:

```
data/
├── EdNet-KT4/          ← KT4 interaction CSV files
└── EdNet-Contents/     ← questions.csv + lectures.csv
```

See **[DATA_SETUP.md](./DATA_SETUP.md)** for full instructions on downloading and placing the dataset.

---

## Step 4 — Create the Docker Network

This is a **one-time step**. Run it before anything else:

```bash
docker network create uni_net
```

You can verify it was created:

```bash
docker network ls | grep uni_net
```

---

## Step 5 — Build All Docker Images

Build all microservice images from the project root:

```bash
docker compose build
```

This builds:
- `uni/ingestion:1.0.0` — PySpark ingestion job
- `uni/processing:1.0.0` — PySpark batch processing job
- `uni/recommendation-loader:1.0.0` — HDFS → PostgreSQL ETL
- `uni/recommendation-api:1.0.0` — FastAPI REST API

> **Note:** First build takes ~5–10 minutes depending on internet speed (downloads base images). Subsequent builds are cached and fast.

---

## Step 6 — Start Long-Running Services

Start HDFS, PostgreSQL, and the API (these stay running):

```bash
docker compose up -d namenode datanode1 datanode2 datanode3 postgres recommendation_api
```

### Verify services are healthy

```bash
docker compose ps
```

All services should show `healthy` or `running` status. Allow up to **2 minutes** for HDFS to fully initialize.

### Check the HDFS Web UI

Open in your browser: **http://localhost:9870**

You should see the NameNode UI with 3 DataNodes listed.

### Check the API health

```bash
curl http://localhost:8000/health
```

Expected response: `{"status": "ok"}`

---

## Step 7 — Run the Initial Load (One-Time)

This runs the full historical pipeline: ingestion → processing → recommendation_loader.

**On Linux / macOS:**
```bash
bash orchestration/scheduler/scripts/initial_load/run_initial_load.sh
```

**On Windows (Git Bash):**
```bash
bash orchestration/scheduler/scripts/initial_load/run_initial_load.sh
```

This script:
1. Runs ingestion in `initial` mode (full dataset)
2. Runs processing in `initial_load` mode (full recomputation)
3. Runs recommendation_loader to push results to PostgreSQL

> **Expected duration:** 10–60 minutes depending on dataset size and machine specs.

---

## Step 8 — Verify Recommendations Are Loaded

Connect to PostgreSQL and check the recommendations table:

```bash
docker exec -it postgres psql -U postgres -d recommendations
```

```sql
SELECT COUNT(*) FROM recommendations;
SELECT * FROM recommendations LIMIT 5;
\q
```

---

## Step 9 — Test the API

All API endpoints require a JWT token.

### Generate a test token

```bash
# Using Python (from project root):
python -c "
import jwt, os
token = jwt.encode({'user_id': 1}, os.environ.get('JWT_SECRET', 'changeme'), algorithm='HS256')
print(token)
"
```

### Get recommendations

```bash
curl -H "Authorization: Bearer <your-token>" http://localhost:8000/recommendations/me
```

Expected response:
```json
[
  {"recommended_user_id": 42, "similarity_score": 0.94},
  {"recommended_user_id": 7,  "similarity_score": 0.88}
]
```

---

## Step 10 — (Optional) Run the Daily Pipeline Manually

To simulate the nightly incremental run:

```bash
bash orchestration/scheduler/scripts/daily_pipeline/run_daily_pipeline.sh
```

This processes yesterday's data in incremental mode with auto-retry on failure.

---

## Stopping the System

```bash
# Stop all services (keeps volumes and data)
docker compose down

# Stop and DELETE all data (clean slate)
docker compose down -v
```

---

## Quick Reference

| Action | Command |
|---|---|
| **Run everything (full bootstrap)** | `bash run_all.sh` |
| Build all images | `docker compose build` |
| Start infrastructure | `docker compose up -d namenode datanode1 datanode2 datanode3 postgres recommendation_api` |
| View service status | `docker compose ps` |
| View logs | `docker compose logs -f <service>` |
| Run initial load | `bash orchestration/scheduler/scripts/initial_load/run_initial_load.sh` |
| Run daily pipeline | `bash orchestration/scheduler/scripts/daily_pipeline/run_daily_pipeline.sh` |
| **Run storage layer only** | `docker compose -f orchestration/docker_compose/storage.yml up -d` |
| **Run serving layer only** | `docker compose -f orchestration/docker_compose/serving.yml up -d` |
| HDFS Web UI | http://localhost:9870 |
| API health | http://localhost:8000/health |
| Stop (keep data) | `docker compose down` |
| Stop (wipe data) | `docker compose down -v` |

---

## Troubleshooting

### Docker Compose version error (`include` not supported)
The root `docker-compose.yml` uses the `include:` directive which requires **Docker Compose v2.20+**.
Upgrade: https://docs.docker.com/compose/install/

Alternatively, run each layer directly:
```bash
docker compose -f orchestration/docker_compose/storage.yml up -d
docker compose -f orchestration/docker_compose/serving.yml up -d
```

### HDFS NameNode takes too long to start
HDFS first boot can take 60–120 seconds. Wait and re-run `docker compose ps`.

### Port already in use
Stop any local services on ports 9870, 9000, 5432, or 8000, or change ports in `.env`.

### Ingestion fails with file not found
Make sure dataset folders exist at `data/EdNet-KT4/` and `data/EdNet-Contents/`. See `docs/DATA_SETUP.md`.

### API returns 401 Unauthorized
Check your JWT token was generated with the same `JWT_SECRET` as in your `.env` file.

### Build fails
Ensure Docker Desktop is running and you have internet access for pulling base images.
