##############################################################################
# Recommendation Loader – Docker Image
#
# Base       : Apache Spark 3.5.1 + Python 3
# Entrypoint : spark-submit that loads curated HDFS Parquet → PostgreSQL
# Security   : Runs as non-root user (sparkuser, UID 1000)
##############################################################################

FROM apache/spark:3.5.1-python3

LABEL maintainer="ednet-team"
LABEL service="recommendation-loader"
LABEL version="1.0.0"

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3-pip curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN id -u sparkuser 2>/dev/null || useradd -m -u 1000 sparkuser

WORKDIR /app

# ── PostgreSQL JDBC driver ────────────────────────────────────────────────
RUN curl -fSL -o /opt/spark/jars/postgresql-42.7.1.jar \
    https://jdbc.postgresql.org/download/postgresql-42.7.1.jar

# ── Python dependencies ──────────────────────────────────────────────────
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

# ── Application code ─────────────────────────────────────────────────────
COPY config/    /app/microservices/serving/recommendation_loader/config/
COPY src/       /app/microservices/serving/recommendation_loader/src/
COPY pipelines/ /app/microservices/serving/recommendation_loader/pipelines/

# ── Create __init__.py along the package hierarchy for Python imports ────
RUN touch /app/microservices/__init__.py \
    /app/microservices/serving/__init__.py \
    /app/microservices/serving/recommendation_loader/__init__.py

# ── Health check ─────────────────────────────────────────────────────────
COPY docker/healthcheck.py /app/healthcheck.py
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD ["python3", "/app/healthcheck.py"]

# ── Permissions ──────────────────────────────────────────────────────────
RUN chown -R sparkuser:sparkuser /app

USER sparkuser

ENV LOG_FORMAT=json \
    LOG_LEVEL=INFO \
    PYTHONUNBUFFERED=1

# ── Entrypoint ───────────────────────────────────────────────────────────
ENTRYPOINT spark-submit \
    --master local[*] \
    --jars /opt/spark/jars/postgresql-42.7.1.jar \
    --driver-class-path /opt/spark/jars/postgresql-42.7.1.jar \
    /app/microservices/serving/recommendation_loader/pipelines/load_to_postgres.py \
    --config /app/microservices/serving/recommendation_loader/config/loader_config.yaml
