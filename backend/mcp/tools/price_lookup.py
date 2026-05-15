"""
mcp/tools/price_lookup.py

MCP Tool: price_lookup
-----------------------
Aggregates market price data for a specific vehicle to produce a price range.
Used by Claude to calculate price_delta: how far above or below market the
analyzed listing is.

Strategy:
  1. Run search_comps to get real listing prices from the web
  2. Filter out outliers (prices > 2 std deviations from mean)
  3. Return: low / median / high / sample_size

This is intentionally simple — it uses the same search_comps data rather than
a paid data API (e.g., Edmunds, KBB). The tradeoff is lower precision but zero
additional API cost. A future version could integrate a paid market data API.

Returns:
  {
    "low": int,           # 10th percentile price of comps
    "median": int,        # median price of comps
    "high": int,          # 90th percentile price of comps
    "mean": int,          # mean price (for reference)
    "sample_size": int,   # number of comps used in calculation
    "mileage_adjusted": bool,  # True if mileage adjustment was applied
  }

Usage:
  from mcp.tools.price_lookup import price_lookup
  range_data = await price_lookup(2019, "Honda", "Civic", "LX", 62000)
"""

import logging
import statistics
from typing import Optional

from mcp.tools.search_comps import search_comps

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

# Mileage depreciation: roughly $0.06/mile above or below 12k/year average
# Used to normalize comp prices to the analyzed vehicle's mileage
DEPRECIATION_PER_MILE = 0.06

# Minimum comps needed to produce a reliable price range
MIN_SAMPLE_SIZE = 2


# ── Main entry point ──────────────────────────────────────────────────────────

async def price_lookup(
    year: int,
    make: str,
    model: str,
    trim: str,
    mileage: int,
) -> dict:
    """
    Get the market price range for a vehicle by aggregating live comp prices.

    Args:
        year: Model year
        make: Manufacturer (e.g., "Honda")
        model: Model name (e.g., "Civic")
        trim: Trim level (e.g., "LX") — empty string if unknown
        mileage: Odometer reading of the analyzed vehicle (used for adjustment)

    Returns:
        Price range dict with low/median/high/mean/sample_size.
        Returns a dict with error key if insufficient data.
    """
    logger.info(f"[price_lookup] Looking up: {year} {make} {model} {trim} @ {mileage:,}mi")

    # Use a broad location to maximize comp results
    comps = await search_comps(
        year=year,
        make=make,
        model=model,
        trim=trim,
        location="United States",
        max_results=10,   # Fetch more comps for better statistics
    )

    # Extract prices, filtering out comps with no price data
    prices = [c["price"] for c in comps if c.get("price") is not None]

    if len(prices) < MIN_SAMPLE_SIZE:
        logger.warning(
            f"[price_lookup] Insufficient data: only {len(prices)} priced comps found"
        )
        return {
            "low": None,
            "median": None,
            "high": None,
            "mean": None,
            "sample_size": len(prices),
            "mileage_adjusted": False,
            "error": f"Insufficient comp data ({len(prices)} priced results found)",
        }

    # Optionally mileage-adjust comp prices to normalize for odometer differences
    adjusted_prices = _mileage_adjust_prices(comps, mileage)
    if adjusted_prices:
        prices = adjusted_prices
        mileage_adjusted = True
    else:
        mileage_adjusted = False

    # Remove outliers (prices more than 2 std deviations from mean)
    prices = _remove_outliers(prices)

    prices_sorted = sorted(prices)
    n = len(prices_sorted)

    result = {
        "low": _percentile(prices_sorted, 10),
        "median": int(statistics.median(prices_sorted)),
        "high": _percentile(prices_sorted, 90),
        "mean": int(statistics.mean(prices_sorted)),
        "sample_size": n,
        "mileage_adjusted": mileage_adjusted,
    }

    logger.info(
        f"[price_lookup] Range: ${result['low']:,} – ${result['median']:,} – "
        f"${result['high']:,} (n={n}, adjusted={mileage_adjusted})"
    )
    return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mileage_adjust_prices(comps: list[dict], target_mileage: int) -> list[int]:
    """
    Adjust comp prices to account for mileage differences vs. the analyzed vehicle.

    Logic: if a comp has 10,000 more miles than the analyzed car, its price
    should be ~$600 higher (10,000 × $0.06) to be comparable.

    Only adjusts comps that have mileage data. Returns empty list if
    fewer than half the comps have mileage — fall back to raw prices.
    """
    adjusted: list[int] = []
    comps_with_mileage = [c for c in comps if c.get("price") and c.get("mileage")]

    if len(comps_with_mileage) < len(comps) / 2:
        return []  # Too few comps have mileage — don't adjust

    for comp in comps_with_mileage:
        comp_price = comp["price"]
        comp_mileage = comp["mileage"]
        mileage_delta = comp_mileage - target_mileage
        adjustment = int(mileage_delta * DEPRECIATION_PER_MILE)
        adjusted.append(comp_price + adjustment)

    return adjusted


def _remove_outliers(prices: list[int]) -> list[int]:
    """
    Remove prices more than 2 standard deviations from the mean.
    Prevents a single $80k listing from skewing the median on a $20k car.
    Requires at least 3 data points to apply (otherwise returns unchanged).
    """
    if len(prices) < 3:
        return prices

    mean = statistics.mean(prices)
    stdev = statistics.stdev(prices)
    threshold = 2 * stdev

    filtered = [p for p in prices if abs(p - mean) <= threshold]

    # If outlier removal eliminated too many, return original
    return filtered if len(filtered) >= MIN_SAMPLE_SIZE else prices


def _percentile(sorted_prices: list[int], pct: int) -> Optional[int]:
    """Calculate the Nth percentile of a sorted price list."""
    if not sorted_prices:
        return None
    n = len(sorted_prices)
    idx = max(0, min(n - 1, int(round(pct / 100 * n))))
    return sorted_prices[idx]
