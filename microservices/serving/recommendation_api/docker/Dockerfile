##############################################################################
# Recommendation API – Docker Image
#
# Base       : Python 3.11 slim
# Entrypoint : uvicorn serving the FastAPI app
# Security   : Runs as non-root user (appuser, UID 1000)
##############################################################################

FROM python:3.11-slim

LABEL maintainer="ednet-team"
LABEL service="recommendation-api"
LABEL version="1.0.0"

RUN --network=host apt-get update && apt-get install -y --no-install-recommends \
        curl libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r -g 1000 appuser && useradd -r -u 1000 -g appuser -m appuser

WORKDIR /app

# ── Python dependencies ──────────────────────────────────────────────────
COPY requirements.txt /tmp/requirements.txt
RUN --network=host pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

# ── Application code ─────────────────────────────────────────────────────
COPY src/ /app/microservices/serving/recommendation_api/src/
COPY config/ /app/microservices/serving/recommendation_api/config/

# ── Create __init__.py along the package hierarchy for uvicorn import ────
RUN touch /app/microservices/__init__.py \
    /app/microservices/serving/__init__.py \
    /app/microservices/serving/recommendation_api/__init__.py

# ── Permissions ──────────────────────────────────────────────────────────
RUN chown -R appuser:appuser /app

USER appuser

ENV PYTHONUNBUFFERED=1 \
    LOG_LEVEL=INFO

EXPOSE 8000

# ── Entrypoint ───────────────────────────────────────────────────────────
CMD ["uvicorn", \
     "microservices.serving.recommendation_api.src.app:app", \
     "--host", "0.0.0.0", \
     "--port", "8000"]
