FROM python:3.11-slim

# ── Image metadata ────────────────────────────────────────────────────
ARG IMAGE_VERSION=1.0.0
LABEL maintainer="data-engineering-team" \
      version="${IMAGE_VERSION}" \
      description="Recommendation API — FastAPI + asyncpg" \
      org.opencontainers.image.source="microservices/serving/recommendation_api"

USER root

# ── System deps ───────────────────────────────────────────────────────
# curl: needed by the Docker HEALTHCHECK instruction
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python deps (cached layer — only re-runs when requirements change) ─
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code ──────────────────────────────────────────────────
COPY src/ /app/microservices/serving/recommendation_api/src/

# Need an __init__.py chain for the imports to resolve correctly
RUN mkdir -p /app/microservices/serving/recommendation_api \
    && touch /app/microservices/__init__.py \
    && touch /app/microservices/serving/__init__.py \
    && touch /app/microservices/serving/recommendation_api/__init__.py \
    && touch /app/microservices/serving/recommendation_api/src/__init__.py \
    && touch /app/microservices/serving/recommendation_api/src/routes/__init__.py \
    && touch /app/microservices/serving/recommendation_api/src/services/__init__.py \
    && touch /app/microservices/serving/recommendation_api/src/schemas/__init__.py

# ── Security: non-root user (UID 1000 matches compose user: "1000:1000") ─
RUN groupadd -r -g 1000 apiuser && useradd -r -u 1000 -g apiuser -d /app apiuser \
    && chown -R apiuser:apiuser /app
USER apiuser

# ── Health check (used by Docker and depends_on) ──────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# ── Runtime ───────────────────────────────────────────────────────────
EXPOSE 8000
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    LOG_LEVEL=INFO

# Uvicorn with 2 workers — single node, no cluster needed at the moment
CMD ["uvicorn", \
     "microservices.serving.recommendation_api.src.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--log-level", "info"]
