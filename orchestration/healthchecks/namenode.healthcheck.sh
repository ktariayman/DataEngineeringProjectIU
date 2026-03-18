#!/bin/sh
##############################################################################
# Healthcheck – HDFS NameNode
# Method : HTTP GET http://namenode:9870 (Web UI)
# Exit   : 0 = healthy, 1 = unhealthy
##############################################################################

set -e

# ── Check ──────────────────────────────────────────────────────────────────
curl -f --silent --max-time 5 "http://namenode:9870" > /dev/null 2>&1
