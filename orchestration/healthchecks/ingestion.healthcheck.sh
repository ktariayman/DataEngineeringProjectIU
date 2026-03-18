#!/bin/sh
##############################################################################
# Healthcheck – Ingestion Spark Job (batch service)
# Method : Verify Spark driver PID, or treat clean exit as healthy
# Exit   : 0 = healthy / clean exit, 1 = driver died unexpectedly
##############################################################################
# The ingestion service is a batch job, not a long-running daemon.
# A clean exit (exit 0) from the container is treated as healthy.

set -e

# ── Verify Spark driver PID ────────────────────────────────────────────────
SPARK_PID_FILE="/tmp/spark-driver.pid"

if [ -f "$SPARK_PID_FILE" ]; then
  PID=$(cat "$SPARK_PID_FILE")
  if kill -0 "$PID" 2>/dev/null; then
    echo "[healthcheck] Ingestion Spark driver → alive (PID $PID)"
    exit 0
  else
    echo "[healthcheck] Ingestion Spark driver → DEAD (PID $PID)"
    exit 1
  fi
fi

# No PID file → job completed or has not started yet.
echo "[healthcheck] Ingestion → no active Spark driver (completed / not started)"
exit 0
