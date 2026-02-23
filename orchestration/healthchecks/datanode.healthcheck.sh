#!/bin/sh
# Healthcheck: HDFS DataNode registration
# Verifies that at least 1 DataNode is registered with the NameNode
# by querying the NameNode REST API for live node count.
# Exit 0 = healthy (>= 1 live nodes), 1 = unhealthy

set -e

LIVE_NODES=$(curl -f --silent --max-time 5 \
  "http://namenode:9870/jmx?qry=Hadoop:service=NameNode,name=FSNamesystem" \
  | grep -o '"NumLiveDataNodes":[0-9]*' \
  | grep -o '[0-9]*$')

if [ -z "$LIVE_NODES" ] || [ "$LIVE_NODES" -lt 1 ]; then
  echo "DataNode healthcheck failed: live nodes = ${LIVE_NODES:-unknown}"
  exit 1
fi

echo "DataNode healthcheck passed: $LIVE_NODES live node(s)"
exit 0
