"""
routers/demo.py

GET /demo — Pre-computed Demo DealReport
------------------------------------------
Returns a cached, pre-computed DealReport for recruiter and demo access.
No authentication required — this is deliberately public so anyone
(recruiters, interviewers, portfolio viewers) can see the full product
experience without signing up.

How the cache works:
  - scripts/seed_demo.py runs a real analysis on a hardcoded listing and
    saves the result to backend/demo_cache.json
  - This endpoint reads that file on each request (it's small, ~2KB)
  - The cache is committed to the repo so it's always available on Railway

Why a cache instead of a live call?
  - Zero latency for demo views (no 20-30 second analysis wait)
  - No API cost per demo request
  - Guaranteed to show a high-quality, pre-reviewed result
  - Works even if the Anthropic API is unavailable
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from backend.models.analysis import DealReport

logger = logging.getLogger(__name__)

router = APIRouter()

# Path to the pre-computed demo cache file
DEMO_CACHE_PATH = Path(__file__).parent.parent / "demo_cache.json"


@router.get(
    "/demo",
    response_model=DealReport,
    summary="Get demo deal analysis",
    description=(
        "Returns a pre-computed DealReport for a real listing. "
        "No authentication required. Used for recruiter demos and portfolio views."
    ),
)
async def get_demo() -> DealReport:
    """
    GET /demo

    Returns a pre-computed DealReport from demo_cache.json.

    If the cache file doesn't exist (e.g. fresh deploy before seed_demo.py was run),
    returns a hardcoded fallback report so the demo endpoint never 404s.

    Returns:
      DealReport JSON — same structure as POST /analyze
    """
    if DEMO_CACHE_PATH.exists():
        try:
            data = json.loads(DEMO_CACHE_PATH.read_text(encoding="utf-8"))
            report = DealReport(**data)
            logger.info("[demo] Served from demo_cache.json")
            return report
        except Exception as e:
            logger.error(f"[demo] Failed to load demo_cache.json: {e}")
            # Fall through to hardcoded fallback

    # ── Hardcoded fallback ────────────────────────────────────────────────────
    # This ensures /demo always works, even before seed_demo.py is run.
    # It's a realistic example of what a real analysis looks like.
    logger.warning("[demo] demo_cache.json missing or invalid — serving fallback")

    fallback = DealReport(
        grade="B",
        price_delta=-800,
        price_verdict=(
            "This 2019 Honda Civic LX is priced $800 BELOW market "
            "for comparable listings with similar mileage in this region."
        ),
        summary=(
            "This is a solid used car deal — slightly below market price with "
            "Honda's well-known reliability backing it up. The mileage is reasonable "
            "for the year, and there are no major red flags from the VIN history. "
            "A pre-purchase inspection is still recommended before buying any used car."
        ),
        red_flags=[
            {
                "title": "No Service History Provided",
                "description": (
                    "The listing doesn't mention any service records. "
                    "Ask the seller for receipts for oil changes and major services "
                    "before committing to buy."
                ),
            },
            {
                "title": "High Demand Area Markup Risk",
                "description": (
                    "Listings in this metro area trend 3-5% above national averages. "
                    "The below-market price here may reflect an undisclosed issue — "
                    "always do a pre-purchase inspection."
                ),
            },
        ],
        green_flags=[
            {
                "title": "Below Market Price",
                "description": (
                    "At $800 below the regional median for this trim and mileage, "
                    "this listing offers good value if the car checks out."
                ),
            },
            {
                "title": "Honda Civic Reliability",
                "description": (
                    "The 10th-gen Civic (2016-2021) is one of the most reliable "
                    "compact cars on the market with low maintenance costs and "
                    "excellent long-term ownership data."
                ),
            },
            {
                "title": "Reasonable Mileage for Year",
                "description": (
                    "At 62,000 miles on a 2019 model, this car is within the "
                    "expected range (~12k miles/year). No above-average wear concerns."
                ),
            },
        ],
        comps=[
            {
                "title": "2019 Honda Civic LX — 58k mi (CarGurus)",
                "price": 19200,
                "mileage": 58000,
                "url": "https://www.cargurus.com",
                "delta_vs_this": 1100,
            },
            {
                "title": "2019 Honda Civic LX — 67k mi (AutoTrader)",
                "price": 17900,
                "mileage": 67000,
                "url": "https://www.autotrader.com",
                "delta_vs_this": -200,
            },
            {
                "title": "2019 Honda Civic LX — 71k mi (Cars.com)",
                "price": 17400,
                "mileage": 71000,
                "url": "https://www.cars.com",
                "delta_vs_this": -700,
            },
        ],
        negotiation_points=[
            "Comps average $18,167 — open at $17,200 and cite the two listings below market.",
            "No service records provided — ask for a $300 concession to cover a pre-purchase inspection.",
            "14 days on market with no price drop suggests motivation — a $500 reduction is reasonable to request.",
        ],
    )
    return fallback
