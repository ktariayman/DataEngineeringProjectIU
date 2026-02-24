FROM python:3.11-slim

# ── Image metadata ────────────────────────────────────────────────────
ARG IMAGE_VERSION=1.0.0
LABEL maintainer="data-engineering-team" \
      version="${IMAGE_VERSION}" \
      description="Recommendation Loader — HDFS Parquet to PostgreSQL batch job" \
      org.opencontainers.image.source="microservices/serving/recommendation_loader"

USER root

# ── System deps ───────────────────────────────────────────────────────
# libpq-dev: required by psycopg2. openjdk-17-jre: required by pyarrow HDFS.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq-dev \
        openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python deps ───────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code ──────────────────────────────────────────────────
COPY src/      /app/microservices/serving/recommendation_loader/src/
COPY pipelines/ /app/microservices/serving/recommendation_loader/pipelines/

# __init__.py chain for package imports
RUN mkdir -p /app/microservices/serving/recommendation_loader \
    && touch /app/microservices/__init__.py \
    && touch /app/microservices/serving/__init__.py \
    && touch /app/microservices/serving/recommendation_loader/__init__.py \
    && touch /app/microservices/serving/recommendation_loader/src/__init__.py \
    && touch /app/microservices/serving/recommendation_loader/pipelines/__init__.py

# ── Security: non-root user (UID 1000 matches compose user: "1000:1000") ─
RUN groupadd -r -g 1000 loaderuser && useradd -r -u 1000 -g loaderuser -d /app loaderuser \
    && chown -R loaderuser:loaderuser /app
USER loaderuser

# ── Runtime ───────────────────────────────────────────────────────────
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

# Shell form so $MODE and $GENERATION_DATE env vars expand at runtime
ENTRYPOINT python /app/microservices/serving/recommendation_loader/pipelines/load_recommendations.py \
    --mode ${MODE:-daily} \
    ${GENERATION_DATE:+--generation-date $GENERATION_DATE}
