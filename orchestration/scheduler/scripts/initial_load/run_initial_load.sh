#!/usr/bin/env bash
##############################################################################
# Script A – Initial Load (One-Time)
# Dataset : EdNet KT4 (full historical bootstrap)
# Pipeline: ingestion → processing → recommendation_loader
##############################################################################
# Run this ONCE to seed the system with the complete EdNet/KT4 history.
# After completion, switch to the daily pipeline (Script B / cron).
#
# Usage:
#   bash orchestration/scheduler/scripts/initial_load/run_initial_load.sh
#
# All timestamps are UTC.  Exits 1 on any step failure (fail-fast).
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

# ═══════════════════════════════════════════════════════════════════════════
# Start
# ═══════════════════════════════════════════════════════════════════════════

SCRIPT_START=$(date -u +%s)
log "══════════════════════════════════════════════════════"
log "  Initial Load — starting"
log "══════════════════════════════════════════════════════"

# ── Step 1 – Ingestion (full historical mode) ─────────────────────────────

log "Step 1/3: Running ingestion (MODE=initial) …"

sudo docker compose run --rm \
  -e MODE=initial \
  ingestion \
  || fail "Step 1 failed → ingestion exited with a non-zero status."

log "Step 1/3: Ingestion completed successfully."

# ── Step 2 – Processing (full recomputation) ──────────────────────────────

log "Step 2/3: Running processing (MODE=initial_load) …"

sudo docker compose run --rm \
  -e MODE=initial_load \
  processing \
  || fail "Step 2 failed → processing exited with a non-zero status."

log "Step 2/3: Processing completed successfully."

# ── Step 3 – Recommendation Loader (HDFS → PostgreSQL) ────────────────────

log "Step 3/3: Running recommendation_loader (MODE=initial_load) …"

sudo docker compose run --rm \
  -e MODE=initial_load \
  recommendation_loader \
  || fail "Step 3 failed → recommendation_loader exited with a non-zero status."

log "Step 3/3: Recommendation loader completed successfully."

# ═══════════════════════════════════════════════════════════════════════════
# Done
# ═══════════════════════════════════════════════════════════════════════════

SCRIPT_END=$(date -u +%s)
DURATION=$(( SCRIPT_END - SCRIPT_START ))

log "══════════════════════════════════════════════════════"
log "  Initial Load — COMPLETED"
log "  Total duration: ${DURATION}s"
log "══════════════════════════════════════════════════════"

exit 0
