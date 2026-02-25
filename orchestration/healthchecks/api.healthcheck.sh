#!/bin/sh
##############################################################################
# Healthcheck – Recommendation API
# Endpoint : GET /health → 200 OK
# Exit     : 0 = healthy, 1 = unhealthy
##############################################################################

set -e

# ── Check ──────────────────────────────────────────────────────────────────
curl -f --silent --max-time 5 "http://localhost:8000/health" > /dev/null 2>&1
