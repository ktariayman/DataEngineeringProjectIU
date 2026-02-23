#!/bin/sh
# Healthcheck: HDFS NameNode Web UI
# Exit 0 = healthy, 1 = unhealthy
# Used by Docker Compose healthcheck for the `namenode` service.

set -e

curl -f --silent --max-time 5 "http://namenode:9870" > /dev/null 2>&1
