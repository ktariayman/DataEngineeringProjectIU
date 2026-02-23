#!/usr/bin/env bash
# =============================================================================
# Script B — Daily Incremental Pipeline
# =============================================================================
# Runs every day at 02:00 UTC (scheduled via cron).
# Processes the previous day's data (EVENT_DATE = yesterday in UTC).
#
# Pipeline steps (in order):
#   1. Ingestion    — ingest yesterday's new interactions from source
#   2. Processing   — recompute features + recommendations (last N days window)
#   3. Loader       — push new recommendations HDFS → PostgreSQL
#
# Usage (manual trigger):
#   bash orchestration/scheduler/scripts/daily_pipeline/run_daily_pipeline.sh
#
# Exit codes:
#   0 — all steps succeeded
#   1 — one or more steps failed (pipeline aborted at failure point)
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log() {
  echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] $*"
}

fail() {
  log "ERROR: $*"
  exit 1
}

# ---------------------------------------------------------------------------
# Derive EVENT_DATE — yesterday in UTC
# ---------------------------------------------------------------------------

# macOS: date -u -v-1d +%Y-%m-%d
# Linux: date -u -d "yesterday" +%Y-%m-%d
if date -u -d "yesterday" +%Y-%m-%d > /dev/null 2>&1; then
  EVENT_DATE=$(date -u -d "yesterday" +%Y-%m-%d)   # GNU/Linux coreutils
else
  EVENT_DATE=$(date -u -v-1d +%Y-%m-%d)            # macOS / BSD date
fi

# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------

SCRIPT_START=$(date -u +%s)
log "======================================================"
log "  Daily Pipeline — starting"
log "  EVENT_DATE = ${EVENT_DATE}"
log "======================================================"

# ---------------------------------------------------------------------------
# Step 1 — Ingestion (incremental — yesterday's data only)
# ---------------------------------------------------------------------------

log "Step 1/3: Running ingestion (MODE=incremental, EVENT_DATE=${EVENT_DATE}) ..."

docker compose run --rm \
  -e MODE=incremental \
  -e EVENT_DATE="${EVENT_DATE}" \
  ingestion \
  || fail "Step 1 failed: ingestion exited with a non-zero status. Pipeline aborted."

log "Step 1/3: Ingestion completed successfully."

# ---------------------------------------------------------------------------
# Step 2 — Processing (windowed recomputation)
# ---------------------------------------------------------------------------

# PROCESSING_WINDOW_DAYS can be overridden by environment; default = 7
PROCESSING_WINDOW_DAYS="${PROCESSING_WINDOW_DAYS:-7}"

log "Step 2/3: Running processing (MODE=incremental, WINDOW=${PROCESSING_WINDOW_DAYS}d) ..."

docker compose run --rm \
  -e MODE=incremental \
  -e PROCESSING_WINDOW_DAYS="${PROCESSING_WINDOW_DAYS}" \
  processing \
  || fail "Step 2 failed: processing exited with a non-zero status. Pipeline aborted."

log "Step 2/3: Processing completed successfully."

# ---------------------------------------------------------------------------
# Step 3 — Recommendation Loader (HDFS → PostgreSQL)
# ---------------------------------------------------------------------------

log "Step 3/3: Running recommendation_loader ..."

docker compose run --rm \
  -e MODE=incremental \
  recommendation_loader \
  || fail "Step 3 failed: recommendation_loader exited with a non-zero status. Pipeline aborted."

log "Step 3/3: Recommendation loader completed successfully."

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------

SCRIPT_END=$(date -u +%s)
DURATION=$(( SCRIPT_END - SCRIPT_START ))

log "======================================================"
log "  Daily Pipeline — COMPLETED"
log "  EVENT_DATE    = ${EVENT_DATE}"
log "  Total duration: ${DURATION}s"
log "======================================================"

exit 0
