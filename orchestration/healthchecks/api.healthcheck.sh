#!/bin/sh
# Healthcheck: Recommendation API (/health endpoint)
# The FastAPI app must expose GET /health → 200 OK.
# Exit 0 = healthy, 1 = unhealthy

set -e

curl -f --silent --max-time 5 "http://localhost:8000/health" > /dev/null 2>&1
