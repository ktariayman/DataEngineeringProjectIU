"""
POST /v1/auth/token — Issues a JWT for a given user_id.

Design (MVP Data Engineering project):
  - No user table or password hashing — that is out of scope.
  - Auth is protected by a shared API_KEY env var (internal system use).
  - Caller sends: {"user_id": "u123", "api_key": "the-secret"}
  - If api_key matches API_KEY env var → issue JWT with sub=user_id
  - Returned token is then used on all protected routes (Bearer scheme)

This is the standard internal service token pattern for data platform APIs
where the callers are other services or authorized analysts, not end users
with passwords.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, status
from jose import jwt
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

_ALGORITHM = "HS256"
_TOKEN_EXPIRE_SECONDS = 86400


# ── Request / Response models ────────────────────────────────────────────────

class TokenRequest(BaseModel):
    user_id: str = Field(
        description="The anonymized EdNet user ID to issue a token for.",
        examples=["u12345"],
    )
    api_key: str = Field(
        description="Shared API key — must match the API_KEY environment variable.",
        examples=["your-api-key-here"],
    )


class TokenResponse(BaseModel):
    access_token: str = Field(description="Signed JWT — use as 'Authorization: Bearer <token>'")
    token_type: str = Field(default="bearer")
    expires_in_seconds: int = Field(description="Token lifetime in seconds.")
    user_id: str = Field(description="The user_id encoded in the token.")


# ── Endpoint ─────────────────────────────────────────────────────────────────

@router.post(
    "/auth/token",
    response_model=TokenResponse,
    summary="Issue a JWT for a user",
    description=(
        "Validates the provided API key and issues a signed JWT. "
        "Use the returned `access_token` as `Authorization: Bearer <token>` "
        "on all protected endpoints."
    ),
)
async def issue_token(body: TokenRequest) -> TokenResponse:
    """
    Issue a JWT for the given user_id after validating the API key.

    Raises HTTP 401 if the api_key does not match.
    """
    expected_key = os.environ.get("API_KEY", "")
    if not expected_key:
        logger.error("API_KEY environment variable is not set.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfiguration — API_KEY not set.",
        )

    if body.api_key != expected_key:
        logger.warning("Rejected token request for user_id=%s — wrong API key.", body.user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )

    now = datetime.now(timezone.utc)
    expire = now + timedelta(seconds=_TOKEN_EXPIRE_SECONDS)
    expire_seconds = _TOKEN_EXPIRE_SECONDS

    jwt_secret = os.environ.get("JWT_SECRET", "")
    if not jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfiguration — JWT_SECRET not set.",
        )
    token = jwt.encode(
        {"sub": body.user_id, "iat": now, "exp": expire},
        key=jwt_secret,
        algorithm=_ALGORITHM,
    )

    logger.info("Issued JWT for user_id=%s expires=%s", body.user_id, expire.isoformat())

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_seconds=expire_seconds,
        user_id=body.user_id,
    )
