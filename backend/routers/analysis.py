"""
routers/analysis.py

POST /analyze — Main Analysis Endpoint
----------------------------------------
The core endpoint of LemonCheck. Accepts a listing URL or VIN, validates the
user's auth and usage tier, runs the two-step Claude agent chain, and returns
a structured DealReport.

Request flow:
  1. Validate Supabase JWT via get_current_user() dependency
  2. Check user's monthly usage count via usage_tracker
  3. If over FREE_TIER_LIMIT (5/month) → return 402 Payment Required
  4. Run claude_agent.run_analysis() — enrichment loop + analysis call
  5. Increment usage count in Supabase
  6. Archive the result to the analyses table (fire-and-forget)
  7. Return the DealReport as JSON

Error handling:
  - 400: Bad request (no URL or VIN provided)
  - 401: Missing or invalid JWT
  - 402: Monthly usage limit exceeded
  - 422: Claude returned invalid JSON (shouldn't happen, but handled)
  - 503: Claude API unavailable or overloaded after retries
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from backend.models.analysis import AnalysisRequest, DealReport
from backend.routers.auth import get_current_user
from backend.services.claude_agent import run_analysis
from backend.services.usage_tracker import (
    FREE_TIER_LIMIT,
    get_usage_count,
    increment_usage,
    save_analysis,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/analyze",
    response_model=DealReport,
    summary="Analyze a used car listing",
    description=(
        "Runs the full LemonCheck AI analysis on a listing URL or VIN. "
        "Requires authentication. Free tier: 5 analyses per calendar month."
    ),
)
async def analyze(
    request: AnalysisRequest,
    user_id: Annotated[str, Depends(get_current_user)],
) -> DealReport:
    """
    POST /analyze

    Body (JSON):
      listing_url: str | null  — CarGurus or AutoTrader listing URL
      vin: str | null          — 17-character VIN

    At least one of listing_url or vin must be provided.

    Returns:
      DealReport JSON with grade, price analysis, red/green flags, comps,
      negotiation points, and summary.
    """
    logger.info(
        f"[analysis] /analyze called — user={user_id} "
        f"url={request.listing_url!r} vin={request.vin!r}"
    )

    # ── Step 1: Usage gate ────────────────────────────────────────────────────
    usage_count = await get_usage_count(user_id)
    if usage_count >= FREE_TIER_LIMIT:
        logger.info(
            f"[analysis] User {user_id} hit usage limit ({usage_count}/{FREE_TIER_LIMIT})"
        )
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "usage_limit_exceeded",
                "message": (
                    f"You've used all {FREE_TIER_LIMIT} free analyses this month. "
                    "Your limit resets on the 1st of next month."
                ),
                "usage_count": usage_count,
                "limit": FREE_TIER_LIMIT,
            },
        )

    # ── Step 2: Run analysis ──────────────────────────────────────────────────
    try:
        report = await run_analysis(request)
    except ValueError as e:
        # Malformed response from Claude (JSON parse failure, schema mismatch)
        logger.error(f"[analysis] Agent returned invalid output: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "analysis_parse_error",
                "message": "The AI returned an unexpected response. Please try again.",
            },
        )
    except Exception as e:
        # Anthropic API error, network error, etc.
        logger.error(f"[analysis] Agent failed: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "analysis_unavailable",
                "message": (
                    "The analysis service is temporarily unavailable. "
                    "Please try again in a few moments."
                ),
            },
        )

    # ── Step 3: Record usage ──────────────────────────────────────────────────
    try:
        new_count = await increment_usage(user_id)
        logger.info(
            f"[analysis] Incremented usage for {user_id}: "
            f"{new_count}/{FREE_TIER_LIMIT} this month"
        )
    except Exception as e:
        # Don't fail the request if usage tracking fails — user already got their result
        logger.error(f"[analysis] Failed to increment usage for {user_id}: {e}")

    # ── Step 4: Archive result (fire-and-forget) ──────────────────────────────
    try:
        await save_analysis(
            user_id=user_id,
            result_json=report.model_dump(),
            listing_url=request.listing_url,
            vin=request.vin,
        )
    except Exception as e:
        logger.error(f"[analysis] Failed to archive analysis for {user_id}: {e}")

    return report
