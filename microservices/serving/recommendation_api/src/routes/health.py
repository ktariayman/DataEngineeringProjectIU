"""
GET /health — liveness and readiness probe.

Reliability NFR:
  - Never returns HTTP 5xx — always HTTP 200 regardless of DB state.
  - If DB is unavailable the status is "degraded" (not "error") so
    the load balancer / Docker healthcheck can still distinguish
    startup from a genuine outage.
  - No JWT required — must be reachable before auth is set up.

Used by:
  - Docker HEALTHCHECK in the Dockerfile
  - Orchestration layer compose depends_on healthcheck
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from microservices.serving.recommendation_api.src.services import db as db_module

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="Liveness and readiness check",
    response_description="Service status",
)
async def health() -> JSONResponse:
    """
    Returns service health. Always HTTP 200.

    - status: "ok"       → API + DB are both reachable
    - status: "degraded" → API is up but DB is unavailable (graceful degradation)
    """
    db_status = "unavailable"
    try:
        pool = db_module._pool  # access at call-time, not import-time
        if pool:
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            db_status = "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Health check DB probe failed: %s", exc)

    overall = "ok" if db_status == "ok" else "degraded"
    return JSONResponse(
        status_code=200,  # always 200 — Reliability NFR
        content={"status": overall, "db": db_status},
    )
