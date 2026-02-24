"""
Recommendation API — FastAPI application factory.

Responsibilities:
  - Lifespan: opens / closes the asyncpg connection pool on startup / shutdown
  - Mounts versioned routers: /v1/recommendations, /health
  - CORS: disabled in production (traffic comes from internal network only)

Design rules followed:
  - No business logic here — only wiring
  - One responsibility: app assembly
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from microservices.serving.recommendation_api.src.services.db import close_pool, init_pool
from microservices.serving.recommendation_api.src.routes.auth import router as auth_router
from microservices.serving.recommendation_api.src.routes.health import router as health_router
from microservices.serving.recommendation_api.src.routes.recommendations import router as rec_router


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN001
    """Open the DB pool before accepting requests; close it on shutdown."""
    await init_pool()
    yield
    await close_pool()


def create_app() -> FastAPI:
    """Build and return the FastAPI application."""
    app = FastAPI(
        title="Recommendation API",
        version="1.0.0",
        description="Serves precomputed collaborative-filtering recommendations for university learners.",
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    # Health endpoint — no auth, used by Docker healthcheck
    app.include_router(health_router)

    # Versioned routes — auth + recommendations
    app.include_router(auth_router, prefix="/v1")
    app.include_router(rec_router, prefix="/v1")

    return app


# Entry point used by uvicorn:
#   uvicorn microservices.serving.recommendation_api.src.main:app
app = create_app()
