"""
services/usage_tracker.py

Supabase Usage Counting Service
---------------------------------
Tracks how many analyses each authenticated user has run in a given calendar
month. Enforces the free-tier limit (FREE_TIER_LIMIT analyses/month).

Design decisions:
  - Uses UPSERT (INSERT ... ON CONFLICT DO UPDATE) so the first analysis of a
    new month auto-creates the row — no separate "initialize" step needed.
  - Uses the Supabase SERVICE ROLE key so the backend can write usage data even
    though RLS prevents the user from doing so directly.
  - month key format: 'YYYY-MM' (e.g. '2025-06') — simple text, easy to query.
  - All functions are async to match the FastAPI/asyncio stack.

Usage:
  from backend.services.usage_tracker import get_usage_count, increment_usage, FREE_TIER_LIMIT

  count = await get_usage_count(user_id)
  if count >= FREE_TIER_LIMIT:
      raise HTTPException(402, ...)
  await increment_usage(user_id)
"""

import os
import logging
from datetime import datetime, timezone

from supabase import create_client, Client

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

FREE_TIER_LIMIT = 5  # analyses per calendar month


def _get_service_client() -> Client:
    """
    Initialize a Supabase client using the SERVICE ROLE key.
    This key bypasses Row Level Security — only use server-side.
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise EnvironmentError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env. "
            "These are required for usage tracking."
        )
    return create_client(url, key)


def _current_month() -> str:
    """Return the current month in 'YYYY-MM' format (UTC)."""
    return datetime.now(timezone.utc).strftime("%Y-%m")


# ── Public API ────────────────────────────────────────────────────────────────

async def get_usage_count(user_id: str) -> int:
    """
    Return how many analyses this user has run in the current calendar month.

    Returns 0 if no row exists yet (first analysis of the month).

    Args:
        user_id: Supabase auth user UUID string

    Returns:
        Integer count of analyses this month (0 if none yet)
    """
    month = _current_month()
    db = _get_service_client()

    try:
        response = (
            db.table("user_usage")
            .select("analysis_count")
            .eq("user_id", user_id)
            .eq("month", month)
            .maybe_single()
            .execute()
        )
        if response.data:
            return response.data["analysis_count"]
        return 0
    except Exception as e:
        logger.error(f"[usage_tracker] Failed to get usage for {user_id}: {e}")
        # Fail open — don't block the user if Supabase is unavailable
        return 0


async def increment_usage(user_id: str) -> int:
    """
    Increment this user's analysis count for the current month by 1.
    Creates the row if it doesn't exist yet (upsert pattern).

    Because supabase-py doesn't support raw SQL increment in upsert,
    we do a read-then-write with the service role client:
      1. Read current count (default 0)
      2. Write count + 1 with upsert

    This is safe because /analyze is not a high-concurrency hot path —
    one user can only run one analysis at a time (frontend blocks on result).

    Args:
        user_id: Supabase auth user UUID string

    Returns:
        New analysis_count after increment

    Raises:
        Exception: If the Supabase write fails (caller should handle)
    """
    month = _current_month()
    db = _get_service_client()

    try:
        current = await get_usage_count(user_id)
        new_count = current + 1

        db.table("user_usage").upsert(
            {
                "user_id": user_id,
                "month": month,
                "analysis_count": new_count,
            },
            on_conflict="user_id,month",
        ).execute()

        logger.info(
            f"[usage_tracker] User {user_id} — month {month} — count now {new_count}"
        )
        return new_count

    except Exception as e:
        logger.error(f"[usage_tracker] Failed to increment usage for {user_id}: {e}")
        raise


async def get_usage(user_id: str, month: str) -> dict | None:
    """
    Return the full usage row for a user/month combination.
    Kept for backwards compatibility with original placeholder signature.

    Returns:
        Dict with analysis_count, or None if no row exists
    """
    db = _get_service_client()
    try:
        response = (
            db.table("user_usage")
            .select("*")
            .eq("user_id", user_id)
            .eq("month", month)
            .maybe_single()
            .execute()
        )
        return response.data
    except Exception as e:
        logger.error(f"[usage_tracker] get_usage failed: {e}")
        return None


async def is_over_limit(user_id: str, month: str, limit: int = FREE_TIER_LIMIT) -> bool:
    """
    Check if a user has hit or exceeded their monthly analysis limit.

    Args:
        user_id: Supabase auth user UUID string
        month: 'YYYY-MM' format month string
        limit: Monthly limit (default FREE_TIER_LIMIT = 5)

    Returns:
        True if user is at or over limit
    """
    count = await get_usage_count(user_id)
    return count >= limit


async def save_analysis(
    user_id: str | None,
    result_json: dict,
    listing_url: str | None = None,
    vin: str | None = None,
) -> str:
    """
    Archive a completed DealReport to the analyses table.

    Args:
        user_id: Supabase auth user UUID (None for anonymous/demo analyses)
        result_json: The full DealReport dict (from model.model_dump())
        listing_url: Optional listing URL used for the analysis
        vin: Optional VIN used for the analysis

    Returns:
        The UUID of the newly created analyses row, or "" on failure
    """
    db = _get_service_client()

    try:
        row: dict = {
            "result_json": result_json,
            "listing_url": listing_url,
            "vin": vin,
        }
        if user_id:
            row["user_id"] = user_id

        response = db.table("analyses").insert(row).execute()
        analysis_id = response.data[0]["id"]
        logger.info(
            f"[usage_tracker] Saved analysis {analysis_id} for user {user_id}"
        )
        return analysis_id
    except Exception as e:
        # Don't fail the whole request if archiving fails — log and continue
        logger.error(f"[usage_tracker] Failed to save analysis: {e}")
        return ""
