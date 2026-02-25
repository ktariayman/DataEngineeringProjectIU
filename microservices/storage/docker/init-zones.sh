#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# init-zones.sh
# ─────────────────────────────────────────────────────────────────────────
# Bootstrap HDFS zone directories at first cluster start.
# Idempotent: uses `hdfs dfs -mkdir -p` (no-op if dirs exist).
#
# Governance guarantees:
#   - Creates the canonical raw vs curated zone layout.
#   - Applies RBAC permissions per zone.
#   - Logs every action for audit trail.
#
# This script runs inside the NameNode container after HDFS is ready.
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

NAMENODE_HOST="${HDFS_NAMENODE_HOST:-namenode}"
NAMENODE_WEB="${HDFS_NAMENODE_WEB_PORT:-9870}"
MAX_WAIT=120
INTERVAL=5

echo "[init-zones] Waiting for NameNode to leave safe mode..."
elapsed=0
while true; do
    # Check if NameNode web UI is reachable
    if curl -sf "http://${NAMENODE_HOST}:${NAMENODE_WEB}/" > /dev/null 2>&1; then
        # Check safe mode status
        safe_mode=$(hdfs dfsadmin -safemode get 2>/dev/null || echo "unknown")
        if echo "$safe_mode" | grep -q "OFF"; then
            echo "[init-zones] NameNode is ready (safe mode OFF)."
            break
        fi
    fi

    elapsed=$((elapsed + INTERVAL))
    if [ "$elapsed" -ge "$MAX_WAIT" ]; then
        echo "[init-zones] ERROR: NameNode not ready after ${MAX_WAIT}s. Aborting."
        exit 1
    fi
    echo "[init-zones] Waiting... (${elapsed}s / ${MAX_WAIT}s)"
    sleep "$INTERVAL"
done

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  HDFS Zone Initialization                                   ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ── Create zone directory structure ────────────────────────────────────
echo "[init-zones] Creating zone directories..."

# Raw zone - immutable, append-only
hdfs dfs -mkdir -p /data/raw/kt4/partitions_by_event_date
hdfs dfs -mkdir -p /data/raw/content/lectures
hdfs dfs -mkdir -p /data/raw/content/questions

# Curated zone - derived / aggregated
hdfs dfs -mkdir -p /data/curated/aggregated_student_features
hdfs dfs -mkdir -p /data/curated/user_vectors
hdfs dfs -mkdir -p /data/curated/recommendations_batch

echo "[init-zones] ✓ All zone directories created."

# ── Apply RBAC permissions ─────────────────────────────────────────────
echo "[init-zones] Applying RBAC permissions..."

# Raw zone: 755 (owner rwx, group+other r-x) — world-readable
hdfs dfs -chmod -R 755 /data/raw
hdfs dfs -chown -R hdfs:hadoop /data/raw

# Curated zone: 750 (owner rwx, group r-x, other ---) — restricted
hdfs dfs -chmod -R 750 /data/curated
hdfs dfs -chown -R hdfs:hadoop /data/curated

echo "[init-zones] ✓ RBAC permissions applied."

# ── Verify ─────────────────────────────────────────────────────────────
echo ""
echo "[init-zones] Verifying zone layout:"
hdfs dfs -ls -R /data/ 2>/dev/null | head -30

echo ""
echo "[init-zones] Replication factor check:"
hdfs dfs -stat "%r" /data/raw 2>/dev/null || echo "  (empty dirs — replication applies on write)"

echo ""
echo "[init-zones] ✓ Zone initialization complete."
