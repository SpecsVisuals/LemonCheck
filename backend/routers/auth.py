"""
routers/auth.py

Auth Validation & Dependency Injection
----------------------------------------
Validates Supabase JWTs from the Authorization: Bearer <token> header.
Provides FastAPI dependency functions for protecting routes.

How it works:
  1. The frontend gets a JWT from Supabase after magic-link sign-in
  2. The frontend sends that JWT in the Authorization header on every /analyze call
  3. get_current_user() calls supabase.auth.get_user(token) to validate the JWT
     — Supabase handles signature verification, expiry, and revocation checks
  4. On success, it returns the user's UUID for downstream usage tracking
  5. On failure, it raises 401 Unauthorized

Why not decode the JWT locally?
  Decoding locally (with PyJWT) is faster but requires keeping the JWT secret
  in sync and won't catch revoked tokens. Using get_user() adds ~50ms per request
  but gives us real-time revocation support without managing secrets.

Usage:
  from backend.routers.auth import get_current_user

  @router.post("/analyze")
  async def analyze(user_id: str = Depends(get_current_user)):
      ...
"""

import os
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client

logger = logging.getLogger(__name__)

router = APIRouter()

# HTTPBearer extracts "Bearer <token>" from the Authorization header
_bearer_scheme = HTTPBearer(auto_error=False)


def _get_anon_client():
    """
    Initialize Supabase client with the anon key.
    Used only for auth.get_user() — the anon key is sufficient for JWT validation.
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        raise EnvironmentError(
            "SUPABASE_URL and SUPABASE_ANON_KEY must be set in .env "
            "for JWT validation to work."
        )
    return create_client(url, key)


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
    ] = None,
) -> str:
    """
    FastAPI dependency: validate Supabase JWT and return the user's UUID.

    Raises:
        HTTP 401: If no token is present, token is invalid, or token is expired

    Returns:
        str: The Supabase user UUID (used as user_id throughout the backend)
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in to analyze listings.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # Check Supabase is configured — if not, auth can't work
    supabase_url = os.getenv("SUPABASE_URL")
    if not supabase_url:
        logger.error("[auth] SUPABASE_URL not set — cannot validate JWT")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth service is not configured. Contact support.",
        )

    try:
        db = _get_anon_client()
        response = db.auth.get_user(token)

        if not response or not response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session. Please sign in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_id = str(response.user.id)
        logger.debug(f"[auth] Validated token for user {user_id}")
        return user_id

    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"[auth] JWT validation failed: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_optional_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
    ] = None,
) -> str | None:
    """
    FastAPI dependency: like get_current_user but returns None instead of 401
    when no token is present. Used for endpoints that support both authed and
    anonymous access (e.g. future public endpoints).
    """
    if not credentials:
        return None
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None
