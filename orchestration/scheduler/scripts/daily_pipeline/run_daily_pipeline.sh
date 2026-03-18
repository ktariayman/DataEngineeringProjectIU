#!/usr/bin/env bash
##############################################################################
# Script B – Daily Incremental Pipeline
# Schedule: 02:00 UTC (cron)
# Pipeline: ingestion → processing → recommendation_loader
##############################################################################
# Processes the previous day's data (EVENT_DATE = yesterday in UTC).
#
# Pipeline steps (in order):
#   1. Ingestion  – ingest yesterday's new interactions from source
#   2. Processing – recompute features + recommendations (last N days)
#   3. Loader     – push new recommendations HDFS → PostgreSQL
#
# Usage (manual trigger):
#   bash orchestration/scheduler/scripts/daily_pipeline/run_daily_pipeline.sh
#
# Exit codes:
#   0 – all steps succeeded
#   1 – one or more steps failed (pipeline aborted at failure point)
##############################################################################

set -euo pipefail

# ── Helpers ────────────────────────────────────────────────────────────────

log() {
  echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] $*"
}

fail() {
  log "ERROR: $*"
  exit 1
}

# ── Retry logic (Reliability) ─────────────────────────────────────────────
# Each step is idempotent: jobs write to partitioned paths and overwrite
# on re-run.  Retries with exponential back-off improve batch reliability.
MAX_RETRIES=2
RETRY_SLEEP=60                            # seconds between retry attempts

retry_step() {
  local step_name="$1"
  shift
  local attempt=1
  while [ "$attempt" -le "$MAX_RETRIES" ]; do
    log "${step_name} — attempt ${attempt}/${MAX_RETRIES}"
    if "$@"; then
      return 0
    fi
    log "${step_name} failed on attempt ${attempt}. Retrying in ${RETRY_SLEEP}s …"
    attempt=$(( attempt + 1 ))
    sleep "$RETRY_SLEEP"
  done
  fail "${step_name} failed after ${MAX_RETRIES} attempts. Pipeline aborted."
}

# ── Derive EVENT_DATE ──────────────────────────────────────────────────────
# GNU/Linux coreutils and macOS/BSD date have different flags.

if date -u -d "yesterday" +%Y-%m-%d > /dev/null 2>&1; then
  EVENT_DATE=$(date -u -d "yesterday" +%Y-%m-%d)   # GNU/Linux
else
  EVENT_DATE=$(date -u -v-1d +%Y-%m-%d)            # macOS / BSD
fi

# ═══════════════════════════════════════════════════════════════════════════
# Start
# ═══════════════════════════════════════════════════════════════════════════

SCRIPT_START=$(date -u +%s)
log "══════════════════════════════════════════════════════"
log "  Daily Pipeline — starting"
log "  EVENT_DATE = ${EVENT_DATE}"
log "══════════════════════════════════════════════════════"

# ── Step 1 – Ingestion (incremental — yesterday's data only) ──────────────

log "Step 1/3: Running ingestion (MODE=daily, EVENT_DATE=${EVENT_DATE}) …"

retry_step "Step 1/3 [ingestion]" \
  sudo docker compose run --rm \
    -e MODE=daily \
    -e EVENT_DATE="${EVENT_DATE}" \
    ingestion

log "Step 1/3: Ingestion completed successfully."

# ── Step 2 – Processing (windowed recomputation) ──────────────────────────

PROCESSING_WINDOW_DAYS="${PROCESSING_WINDOW_DAYS:-7}"

log "Step 2/3: Running processing (MODE=incremental, WINDOW=${PROCESSING_WINDOW_DAYS}d) …"

retry_step "Step 2/3 [processing]" \
  sudo docker compose run --rm \
    -e MODE=incremental \
    -e PROCESSING_WINDOW_DAYS="${PROCESSING_WINDOW_DAYS}" \
    processing

log "Step 2/3: Processing completed successfully."

# ── Step 3 – Recommendation Loader (HDFS → PostgreSQL) ────────────────────

log "Step 3/3: Running recommendation_loader …"

retry_step "Step 3/3 [recommendation_loader]" \
  sudo docker compose run --rm \
    -e MODE=incremental \
    recommendation_loader

log "Step 3/3: Recommendation loader completed successfully."

# ═══════════════════════════════════════════════════════════════════════════
# Done
# ═══════════════════════════════════════════════════════════════════════════

SCRIPT_END=$(date -u +%s)
DURATION=$(( SCRIPT_END - SCRIPT_START ))

log "══════════════════════════════════════════════════════"
log "  Daily Pipeline — COMPLETED"
log "  EVENT_DATE    = ${EVENT_DATE}"
log "  Total duration: ${DURATION}s"
log "══════════════════════════════════════════════════════"

exit 0
