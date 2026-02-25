"""
Recommendation API – FastAPI Application.

A lightweight REST API that serves pre-computed recommendations and
student features from the PostgreSQL serving store.

Endpoints
---------
GET /health                        → health check
GET /recommendations/{user_id}     → top-K similar users
GET /students/{user_id}/features   → aggregated student features
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .routes.recommendations import router
from .services.database import close_pool

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    )
    logger.info("Recommendation API starting up.")
    yield
    close_pool()
    logger.info("Recommendation API shut down.")


app = FastAPI(
    title="EdNet Recommendation API",
    description="Serves pre-computed student recommendations from the serving store.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)
