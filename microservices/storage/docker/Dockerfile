FROM bde2020/hadoop-namenode:2.0.0-hadoop3.2.1-java8

# ── Image metadata (Maintainability: versioned Docker images) ──────────
ARG IMAGE_VERSION=1.0.0
LABEL maintainer="data-engineering-team" \
      version="${IMAGE_VERSION}" \
      description="EdNet storage microservice - HDFS zone manager" \
      org.opencontainers.image.source="microservices/storage"

USER root

# ── System deps ────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python deps (cached layer) ────────────────────────────────────────
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# ── Application code (selective copy) ──────────────────────────────────
COPY config/  /app/microservices/storage/config/
COPY src/     /app/microservices/storage/src/
COPY hdfs/    /app/microservices/storage/hdfs/

# ── Zone initialisation script ─────────────────────────────────────────
COPY docker/init-zones.sh /app/init-zones.sh
RUN chmod +x /app/init-zones.sh

# ── Health check ───────────────────────────────────────────────────────
COPY docker/healthcheck.py /app/healthcheck.py
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD ["python3", "/app/healthcheck.py"]

# ── Security: the base hadoop image runs as root for HDFS.
#    We keep root for HDFS operations but restrict with RBAC on data dirs.

# ── Environment ───────────────────────────────────────────────────────
ENV LOG_FORMAT=json \
    LOG_LEVEL=INFO \
    PYTHONUNBUFFERED=1 \
    HDFS_NAMENODE_HOST=namenode \
    HDFS_NAMENODE_PORT=9000 \
    HDFS_NAMENODE_WEB_PORT=9870

# ── Entrypoint: start NameNode, then bootstrap zones ──────────────────
# The base image starts HDFS services; we add zone init as a post-start hook.
# In production, init-zones.sh is called by the orchestration scheduler.
