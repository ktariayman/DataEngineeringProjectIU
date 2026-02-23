#!/bin/sh
# Healthcheck: Processing Spark job (batch service)
# Same pattern as ingestion — this is a batch job, not a daemon.
# Exit 0 = healthy / clean exit, 1 = driver process dead unexpectedly

set -e

SPARK_PID_FILE="/tmp/spark-driver.pid"

if [ -f "$SPARK_PID_FILE" ]; then
  PID=$(cat "$SPARK_PID_FILE")
  if kill -0 "$PID" 2>/dev/null; then
    echo "Processing Spark driver is alive (PID $PID)"
    exit 0
  else
    echo "Processing Spark driver PID $PID is no longer running"
    exit 1
  fi
fi

echo "Processing: no active Spark driver (job completed or not started)"
exit 0
