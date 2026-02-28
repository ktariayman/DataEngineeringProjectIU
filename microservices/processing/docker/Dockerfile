##############################################################################
# Processing Microservice – Docker Image
#
# Base       : Apache Spark 3.5.1 + Python 3
# Entrypoint : spark-submit for the processing orchestrator
# Security   : Runs as non-root user (sparkuser, UID 1000)
##############################################################################

FROM apache/spark:3.5.1-python3

# ── Labels (Maintainability) ─────────────────────────────────────────────
LABEL maintainer="ednet-team"
LABEL service="processing"
LABEL version="1.0.0"

# ── Switch to root to install packages ───────────────────────────────────
USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user if not present
RUN id -u sparkuser 2>/dev/null || useradd -m -u 1000 sparkuser

WORKDIR /app

# ── Install Python dependencies (cached layer) ──────────────────────────
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

# ── Copy application code ────────────────────────────────────────────────
COPY config/      /app/microservices/processing/config/
COPY src/         /app/microservices/processing/src/
COPY pipelines/   /app/microservices/processing/pipelines/
COPY spark_jobs/  /app/microservices/processing/spark_jobs/

# ── Create __init__.py along the package hierarchy for Python imports ────
RUN touch /app/microservices/__init__.py \
    /app/microservices/processing/__init__.py

# ── Health check (Reliability) ───────────────────────────────────────────
COPY docker/healthcheck.py /app/healthcheck.py
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD ["python3", "/app/healthcheck.py"]

# ── Permissions ──────────────────────────────────────────────────────────
RUN chown -R sparkuser:sparkuser /app

# ── Switch to non-root (Security) ───────────────────────────────────────
USER sparkuser

# ── Environment ──────────────────────────────────────────────────────────
ENV LOG_FORMAT=json \
    LOG_LEVEL=INFO \
    PYTHONUNBUFFERED=1

# ── Entrypoint ───────────────────────────────────────────────────────────
# Shell form so $MODE env var is expanded at container start.
ENTRYPOINT spark-submit \
    --master local[*] \
    /app/microservices/processing/pipelines/process_ednet.py \
    --config /app/microservices/processing/config/processing_config.yaml \
    --mode ${MODE:-initial}
