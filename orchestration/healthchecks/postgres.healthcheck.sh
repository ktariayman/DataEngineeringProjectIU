#!/bin/sh
##############################################################################
# Healthcheck – PostgreSQL Readiness
# Method : pg_isready (bundled in the postgres:14 image)
# Exit   : 0 = healthy, non-zero = unhealthy
##############################################################################

set -e

# ── Check ──────────────────────────────────────────────────────────────────
pg_isready -h postgres -p 5432 -U "${POSTGRES_USER:-postgres}"
