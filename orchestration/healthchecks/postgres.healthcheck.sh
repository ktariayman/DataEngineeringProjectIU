#!/bin/sh
# Healthcheck: PostgreSQL readiness
# Uses pg_isready which is bundled in the postgres:14 image.
# Exit 0 = healthy, non-zero = unhealthy

set -e

pg_isready -h postgres -p 5432 -U "${POSTGRES_USER:-postgres}"
