#!/bin/sh
##############################################################################
# Healthcheck – Recommendation Loader (batch service)
# Method : Verify Python ETL process PID, or treat clean exit as healthy
# Exit   : 0 = healthy / clean exit, 1 = process died unexpectedly
##############################################################################
# The loader is a Python ETL job — not a long-running daemon.
# A clean exit (exit 0) from the container is treated as healthy.

set -e

# ── Verify loader PID ──────────────────────────────────────────────────────
LOADER_PID_FILE="/tmp/loader.pid"

if [ -f "$LOADER_PID_FILE" ]; then
  PID=$(cat "$LOADER_PID_FILE")
  if kill -0 "$PID" 2>/dev/null; then
    echo "[healthcheck] Recommendation loader → alive (PID $PID)"
    exit 0
  else
    echo "[healthcheck] Recommendation loader → DEAD (PID $PID)"
    exit 1
  fi
fi

# No PID file → job completed or has not started yet.
echo "[healthcheck] Loader → no active process (completed / not started)"
exit 0
