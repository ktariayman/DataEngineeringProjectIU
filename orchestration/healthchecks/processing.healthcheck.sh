#!/bin/sh
##############################################################################
# Healthcheck – Processing Spark Job (batch service)
# Method : Verify Spark driver PID, or treat clean exit as healthy
# Exit   : 0 = healthy / clean exit, 1 = driver died unexpectedly
##############################################################################
# Same pattern as ingestion — batch job, not a daemon.

set -e

# ── Verify Spark driver PID ────────────────────────────────────────────────
SPARK_PID_FILE="/tmp/spark-driver.pid"

if [ -f "$SPARK_PID_FILE" ]; then
  PID=$(cat "$SPARK_PID_FILE")
  if kill -0 "$PID" 2>/dev/null; then
    echo "[healthcheck] Processing Spark driver → alive (PID $PID)"
    exit 0
  else
    echo "[healthcheck] Processing Spark driver → DEAD (PID $PID)"
    exit 1
  fi
fi

# No PID file → job completed or has not started yet.
echo "[healthcheck] Processing → no active Spark driver (completed / not started)"
exit 0
