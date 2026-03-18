"""
JWT authentication dependency for the Recommendation API.

Security NFR: every protected route uses this dependency.
- Algorithm: HS256
- Secret:    JWT_SECRET env var (must be changed from default in production)
- Claim:     'sub' — contains the anonymized user_id

No business logic here — only token validation.
"""

from __future__ import annotations

import logging
import os

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import ExpiredSignatureError, JWTError, jwt

logger = logging.getLogger(__name__)

_ALGORITHM = "HS256"
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def _get_secret() -> str:
    secret = os.environ.get("JWT_SECRET", "")
    if not secret:
        raise RuntimeError(
            "JWT_SECRET environment variable is not set. "
            "Generate one with: openssl rand -hex 32"
        )
    return secret


async def get_current_user(token: str = Depends(_oauth2_scheme)) -> str:
    """
    FastAPI dependency — decodes the Bearer JWT and returns the user_id (sub claim).

    Raises HTTP 401 on:
      - Missing or malformed token
      - Expired token
      - Invalid signature (wrong secret)
      - Missing 'sub' claim
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, _get_secret(), algorithms=[_ALGORITHM])
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise credentials_exception
        return user_id
    except ExpiredSignatureError:
        logger.info("Rejected expired JWT.")
        raise credentials_exception
    except JWTError:
        logger.info("Rejected invalid JWT.")
        raise credentials_exception
