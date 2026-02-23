#!/bin/sh
# Healthcheck: Recommendation Loader (batch service)
# The loader is a Python ETL job — not a long-running daemon.
# A clean exit (exit 0) is healthy. We check for an active Python process
# if the job is still in progress.
# Exit 0 = healthy / clean exit, 1 = process died unexpectedly

set -e

LOADER_PID_FILE="/tmp/loader.pid"

if [ -f "$LOADER_PID_FILE" ]; then
  PID=$(cat "$LOADER_PID_FILE")
  if kill -0 "$PID" 2>/dev/null; then
    echo "Recommendation loader is alive (PID $PID)"
    exit 0
  else
    echo "Recommendation loader PID $PID is no longer running"
    exit 1
  fi
fi

echo "Loader: no active process (job completed or not started)"
exit 0
