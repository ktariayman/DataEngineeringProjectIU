#!/usr/bin/env bash
##############################################################################
# run_all.sh — Full Bootstrap Script
# Runs the entire system from scratch to a live API in one command.
#
# Pipeline:
#   1. Pre-flight checks
#   2. Create Docker network (uni_net)
#   3. Build all Docker images
#   4. Start HDFS (Storage Layer)
#   5. Start PostgreSQL (Serving Store)
#   6. Run Ingestion (initial load → HDFS raw zone)
#   7. Run Processing (feature engineering + similarity → HDFS curated zone)
#   8. Run Recommendation Loader (HDFS curated → PostgreSQL)
#   9. Start Recommendation API
#  10. Verify & print summary
#
# Usage:
#   bash run_all.sh
#
# Requirements:
#   - Docker Desktop running
#   - Docker Compose v2.20+
#   - .env file present (copy from .env.example)
#   - data/EdNet-KT4/ and data/EdNet-Contents/ populated
#     (see docs/DATA_SETUP.md)
#
# All timestamps are UTC. Exits on any step failure.
##############################################################################

set -euo pipefail

# ── Colors ─────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# ── Helpers ─────────────────────────────────────────────────────────────────

log()     { echo -e "${CYAN}[$(date -u +"%Y-%m-%dT%H:%M:%SZ")]${NC} $*"; }
success() { echo -e "${GREEN}[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] ✔  $*${NC}"; }
warn()    { echo -e "${YELLOW}[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] ⚠  $*${NC}"; }
fail()    { echo -e "${RED}[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] ✘  ERROR: $*${NC}"; exit 1; }

header() {
  echo ""
  echo -e "${BOLD}══════════════════════════════════════════════════════${NC}"
  echo -e "${BOLD}  $*${NC}"
  echo -e "${BOLD}══════════════════════════════════════════════════════${NC}"
}

wait_for_healthy() {
  local service="$1"
  local max_wait="${2:-120}"
  local elapsed=0
  log "Waiting for '${service}' to become healthy (max ${max_wait}s) …"
  while [ "$elapsed" -lt "$max_wait" ]; do
    local status
    status=$(sudo docker inspect --format='{{.State.Health.Status}}' "$service" 2>/dev/null || echo "missing")
    if [ "$status" = "healthy" ]; then
      success "'${service}' is healthy."
      return 0
    fi
    sleep 5
    elapsed=$(( elapsed + 5 ))
    log "  … still waiting for '${service}' (${elapsed}s / ${max_wait}s, status: ${status})"
  done
  fail "'${service}' did not become healthy within ${max_wait}s."
}

# ═══════════════════════════════════════════════════════════════════════════
# Start
# ═══════════════════════════════════════════════════════════════════════════

TOTAL_START=$(date -u +%s)

header "University Recommendation System — Full Bootstrap"
log "Start time: $(date -u)"

# ── Step 1 — Pre-flight Checks ────────────────────────────────────────────

header "Step 1 / 9 — Pre-flight Checks"

# .env file
if [ ! -f ".env" ]; then
  fail ".env file not found. Copy .env.example → .env and fill in secrets."
fi
success ".env file found."

# Docker
if ! sudo docker info > /dev/null 2>&1; then
  fail "Docker is not running. Start Docker Desktop and retry."
fi
success "Docker is running."

# Docker Compose version (need v2.20+ for include:)
COMPOSE_VERSION=$(sudo docker compose version --short 2>/dev/null || echo "0.0.0")
COMPOSE_MAJOR=$(echo "$COMPOSE_VERSION" | cut -d. -f1)
COMPOSE_MINOR=$(echo "$COMPOSE_VERSION" | cut -d. -f2)
if [ "$COMPOSE_MAJOR" -lt 2 ] || { [ "$COMPOSE_MAJOR" -eq 2 ] && [ "$COMPOSE_MINOR" -lt 20 ]; }; then
  warn "Docker Compose ${COMPOSE_VERSION} detected. v2.20+ is recommended for the include: directive."
  warn "Upgrade: https://docs.docker.com/compose/install/"
else
  success "Docker Compose ${COMPOSE_VERSION} — OK."
fi

# Dataset
# Dataset folders — must exist and contain CSV files (not just .gitkeep)
if [ ! -d "data/EdNet-KT4" ]; then
  fail "data/EdNet-KT4/ folder is missing. See docs/DATA_SETUP.md."
fi
if [ ! -d "data/EdNet-Contents" ]; then
  fail "data/EdNet-Contents/ folder is missing. See docs/DATA_SETUP.md."
fi

KT4_CSV_COUNT=$(find "data/EdNet-KT4" -name "*.csv" 2>/dev/null | wc -l)
CONTENTS_CSV_COUNT=$(find "data/EdNet-Contents" -name "*.csv" 2>/dev/null | wc -l)

if [ "$KT4_CSV_COUNT" -eq 0 ] || [ "$CONTENTS_CSV_COUNT" -eq 0 ]; then
  warn "Dataset folders exist but contain no CSV files."
  warn "  data/EdNet-KT4/      → ${KT4_CSV_COUNT} CSV file(s) found"
  warn "  data/EdNet-Contents/ → ${CONTENTS_CSV_COUNT} CSV file(s) found"
  warn "The ingestion step WILL FAIL without real data. See docs/DATA_SETUP.md."
  warn "Continuing so you can verify infrastructure (HDFS, PostgreSQL, API) …"
else
  success "Dataset folders found (KT4: ${KT4_CSV_COUNT} files, Contents: ${CONTENTS_CSV_COUNT} files)."
fi

# ── Step 2 — Docker Network ───────────────────────────────────────────────

header "Step 2 / 9 — Docker Network"

if sudo docker network inspect uni_net > /dev/null 2>&1; then
  success "Network 'uni_net' already exists — skipping creation."
else
  log "Creating Docker network 'uni_net' …"
  sudo docker network create uni_net
  success "Network 'uni_net' created."
fi

# ── Step 2.5 — Tear Down Any Stale Containers ─────────────────────────────
# Force-remove every named container individually.
# Using docker rm -f is more reliable than 'docker compose down' when containers
# are defined across multiple included compose files (project-scope mismatch
# causes compose down to silently miss some of them).

header "Step 2.5 — Cleaning Up Stale Containers"

KNOWN_CONTAINERS=(
  namenode datanode1 datanode2 datanode3
  postgres
  ingestion processing
  recommendation_loader recommendation_api
)

log "Force-removing any leftover containers from a previous run …"
for c in "${KNOWN_CONTAINERS[@]}"; do
  if sudo docker inspect "$c" > /dev/null 2>&1; then
    sudo docker rm -f "$c" > /dev/null 2>&1 && log "  Removed: $c" || warn "  Could not remove: $c"
  fi
done
success "Cleanup done — starting fresh."

# ── Step 3 — Build All Images ─────────────────────────────────────────────

header "Step 3 / 9 — Building Docker Images"

log "Building all microservice images …"
sudo docker compose build \
  ingestion \
  processing \
  recommendation_loader \
  recommendation_api
success "All images built."

# ── Step 4 — Start Storage Layer (HDFS) ──────────────────────────────────

header "Step 4 / 9 — Starting Storage Layer (HDFS)"

log "Starting NameNode and DataNodes …"
sudo docker compose up -d namenode datanode1 datanode2 datanode3

wait_for_healthy namenode 180

success "HDFS cluster is up. Web UI: http://localhost:9870"

# ── Step 5 — Start PostgreSQL ─────────────────────────────────────────────

header "Step 5 / 9 — Starting PostgreSQL (Serving Store)"

log "Starting PostgreSQL …"
sudo docker compose up -d postgres

wait_for_healthy postgres 60

success "PostgreSQL is up on port 5432."

# ── Step 5b — HDFS directory provisioning ────────────────────────────────

header "Step 5b / 9 — HDFS Directory Provisioning"

log "Creating HDFS base directories and setting permissions …"
sudo docker exec namenode bash -c "hdfs dfsadmin -safemode wait && hdfs dfs -mkdir -p /data/raw/kt4 && hdfs dfs -mkdir -p /data/raw/content && hdfs dfs -mkdir -p /data/curated && hdfs dfs -chmod -R 777 /data" \
  || fail "HDFS directory provisioning failed."

success "HDFS /data hierarchy created with open permissions."

# ── Step 6 — Ingestion (Initial Load) ────────────────────────────────────

header "Step 6 / 9 — Ingestion (Initial Load → HDFS Raw Zone)"

log "Running ingestion in MODE=initial …"
sudo docker compose run --rm \
  -e MODE=initial \
  ingestion \
  || fail "Ingestion failed. Check logs: sudo docker compose logs ingestion"

success "Ingestion complete. Data written to HDFS /data/raw/"

log "Verifying HDFS kt4 path was written …"
sudo docker exec namenode bash -c "hdfs dfs -ls /data/raw/kt4/partitions_by_event_date" \
  || fail "HDFS kt4 path not found after ingestion. Check ingestion logs for validation errors."
success "HDFS kt4 data confirmed."

# ── Step 7 — Processing ───────────────────────────────────────────────────

header "Step 7 / 9 — Processing (Feature Engineering + Similarity → HDFS Curated)"

log "Running processing in MODE=initial …"
sudo docker compose run --rm \
  -e MODE=initial \
  processing \
  || fail "Processing failed. Check logs: sudo docker compose logs processing"

success "Processing complete. Vectors + recommendations written to HDFS /data/curated/"

# ── Step 8 — Recommendation Loader (HDFS → PostgreSQL) ───────────────────

header "Step 8 / 9 — Recommendation Loader (HDFS Curated → PostgreSQL)"

log "Running recommendation_loader in MODE=initial …"
sudo docker compose run --rm \
  -e MODE=initial \
  recommendation_loader \
  || fail "Recommendation loader failed. Check logs: sudo docker compose logs recommendation_loader"

success "Recommendations loaded into PostgreSQL."

# ── Step 9 — Start Recommendation API ────────────────────────────────────

header "Step 9 / 9 — Starting Recommendation API"

log "Starting recommendation_api …"
sudo docker compose up -d recommendation_api

wait_for_healthy recommendation_api 60

success "API is up."

# ── Done ──────────────────────────────────────────────────────────────────

TOTAL_END=$(date -u +%s)
TOTAL_DURATION=$(( TOTAL_END - TOTAL_START ))
MINUTES=$(( TOTAL_DURATION / 60 ))
SECONDS=$(( TOTAL_DURATION % 60 ))

echo ""
echo -e "${GREEN}${BOLD}"
echo "══════════════════════════════════════════════════════"
echo "  🎉  System is fully operational!"
echo "══════════════════════════════════════════════════════"
echo ""
echo "  HDFS Web UI  → http://localhost:9870"
echo ""
echo "  API endpoints (replace u1 with any valid user ID):"
echo ""
echo "    # Health check"
echo "    GET http://localhost:8000/health"
echo ""
echo "    # Get top-10 recommendations for a user"
echo "    GET http://localhost:8000/recommendations/u1"
echo ""
echo "    # Get top-5 recommendations"
echo "    GET http://localhost:8000/recommendations/u1?top_k=5"
echo ""
echo "    # Get aggregated learning features for a user"
echo "    GET http://localhost:8000/students/u1/features"
echo ""
echo "  Total time: ${MINUTES}m ${SECONDS}s"
echo "══════════════════════════════════════════════════════"
echo -e "${NC}"
echo ""
log "To run the daily incremental pipeline:"
echo "  bash orchestration/scheduler/scripts/daily_pipeline/run_daily_pipeline.sh"
echo ""
log "To stop everything:"
echo "  sudo docker compose down"
echo ""

exit 0
