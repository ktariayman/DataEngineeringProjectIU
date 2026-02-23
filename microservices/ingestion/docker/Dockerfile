FROM bitnami/spark:3.5

# ── Image metadata (Maintainability: versioned Docker images) ──────────
ARG IMAGE_VERSION=1.0.0
LABEL maintainer="data-engineering-team" \
      version="${IMAGE_VERSION}" \
      description="EdNet ingestion microservice - PySpark 3.5" \
      org.opencontainers.image.source="microservices/ingestion"

USER root

# ── System deps ────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python deps (cached layer) ────────────────────────────────────────
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# ── Application code (selective copy) ─────────────
COPY config/  /app/microservices/ingestion/config/
COPY src/     /app/microservices/ingestion/src/
COPY pipelines/ /app/microservices/ingestion/pipelines/

# ── Health check (Docker HEALTHCHECK instruction) ─────────────────────
COPY docker/healthcheck.py /app/healthcheck.py
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD ["python3", "/app/healthcheck.py"]

# ── Security: run as non-root user ────────────────────────────────────
RUN groupadd -r sparkuser && useradd -r -g sparkuser -d /app sparkuser \
    && chown -R sparkuser:sparkuser /app
USER sparkuser

# ── Environment ───────────────────────────────────────────────────────
ENV LOG_FORMAT=json \
    LOG_LEVEL=INFO \
    PYTHONUNBUFFERED=1

# Default: run the full ingestion orchestrator
ENTRYPOINT ["spark-submit", \
    "--master", "local[*]", \
    "/app/microservices/ingestion/pipelines/file_intake/ingest_ednet.py", \
    "--config", "/app/microservices/ingestion/config/ingestion_config.yaml"]
