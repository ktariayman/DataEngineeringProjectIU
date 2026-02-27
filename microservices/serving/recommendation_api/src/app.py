"""
Recommendation API - FastAPI Application Factory.

Endpoints
---------
GET  /health                        → liveness / readiness probe
POST /auth/token                    → issue a JWT for a given user_id
GET  /recommendations/{user_id}     → top-K similar students
GET  /students/{user_id}/features   → aggregated learning features

Security
--------
/auth/token  requires a shared API_KEY env-var (internal service call).
Returned JWT is used on protected routes via  Authorization: Bearer <token>.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from .routes.auth import router as auth_router
from .routes.recommendations import router as rec_router
from .services.database import close_pool

logger = logging.getLogger(__name__)

# ── OpenAPI tag descriptions (appear as sections in Swagger UI) ────────────

TAGS_METADATA = [
    {
        "name": "Health",
        "description": "Liveness and readiness probes used by Docker and load-balancers.",
    },
    {
        "name": "auth",
        "description": (
            "Issue a short-lived JWT. "
            "Send `{user_id, api_key}` → receive `access_token`. "
            "Pass the token as **Authorization: Bearer \\<token\\>** on protected endpoints."
        ),
    },
    {
        "name": "Recommendations",
        "description": (
            "Retrieve pre-computed collaborative-filtering recommendations. "
            "Each result is a ranked list of similar students with a cosine-similarity score."
        ),
    },
    {
        "name": "Students",
        "description": (
            "Retrieve aggregated learning features per student, "
            "such as accuracy rate, active days, and per-part interaction counts."
        ),
    },
]


# ── Lifespan ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle hooks."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    logger.info("Recommendation API starting up …")
    yield
    close_pool()
    logger.info("Recommendation API shut down.")


# ── Application factory ────────────────────────────────────────────────────

app = FastAPI(
    title="EdNet Recommendation API",
    description=(
        "Serves **pre-computed collaborative-filtering recommendations** "
        "derived from the EdNet student interaction dataset.\n\n"
        "### Quick start\n"
        "1. Call `POST /auth/token` with your `api_key` and a `user_id` to get a JWT.\n"
        "2. Pass the JWT as `Authorization: Bearer <token>` on subsequent requests.\n"
        "3. Call `GET /recommendations/{user_id}` to fetch similar students.\n\n"
        "User IDs follow the format `u<number>` (e.g. `u1`, `u42`, `u1000`)."
    ),
    version="1.0.0",
    openapi_tags=TAGS_METADATA,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Auth — POST /auth/token
app.include_router(auth_router)

# Data routes — GET /recommendations/{user_id}, GET /students/{user_id}/features, GET /health
app.include_router(rec_router)
