#!/bin/sh
##############################################################################
# Healthcheck – HDFS DataNode Registration
# Method : Query NameNode JMX API for NumLiveDataNodes
# Exit   : 0 = healthy (≥ 1 live nodes), 1 = unhealthy
##############################################################################

set -e

# ── Query NameNode JMX ─────────────────────────────────────────────────────
LIVE_NODES=$(curl -f --silent --max-time 5 \
  "http://namenode:9870/jmx?qry=Hadoop:service=NameNode,name=FSNamesystem" \
  | grep -o '"NumLiveDataNodes":[0-9]*' \
  | grep -o '[0-9]*$')

# ── Evaluate ───────────────────────────────────────────────────────────────
if [ -z "$LIVE_NODES" ] || [ "$LIVE_NODES" -lt 1 ]; then
  echo "[healthcheck] DataNode → FAIL (live nodes = ${LIVE_NODES:-unknown})"
  exit 1
fi

echo "[healthcheck] DataNode → OK ($LIVE_NODES live node(s))"
exit 0
