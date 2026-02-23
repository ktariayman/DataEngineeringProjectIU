#!/bin/sh
# Healthcheck: Ingestion Spark job (batch service)
# The ingestion service is a batch job, not a long-running daemon.
# A clean exit (exit 0 from the container) is treated as healthy.
# If the process is still running, we verify the Spark driver is alive.
# Exit 0 = healthy / clean exit, 1 = driver process dead unexpectedly

set -e

# If a Spark driver PID file exists, verify the process is still alive.
SPARK_PID_FILE="/tmp/spark-driver.pid"

if [ -f "$SPARK_PID_FILE" ]; then
  PID=$(cat "$SPARK_PID_FILE")
  if kill -0 "$PID" 2>/dev/null; then
    echo "Ingestion Spark driver is alive (PID $PID)"
    exit 0
  else
    echo "Ingestion Spark driver PID $PID is no longer running"
    exit 1
  fi
fi

# No PID file means the job completed or hasn't started yet.
# A completed batch job with clean exit is healthy.
echo "Ingestion: no active Spark driver (job completed or not started)"
exit 0
