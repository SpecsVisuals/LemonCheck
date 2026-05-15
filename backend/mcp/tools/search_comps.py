"""
mcp/tools/search_comps.py

MCP Tool: search_comps
-----------------------
Searches for comparable used car listings to establish a market price baseline.

Primary:  SerpAPI (Google Shopping / organic search results)
Fallback: Brave Search API (if SERPAPI_KEY is not set or SerpAPI fails)

Query pattern:
  "{year} {make} {model} {trim} for sale near {location}"

Returns up to 5 comparable listings, each with:
  {
    "title": str,
    "price": int | None,       # asking price in USD
    "mileage": int | None,     # odometer in miles
    "url": str,
    "source": str,             # "cargurus", "autotrader", "cars.com", etc.
  }

These comps are the core data that lets Claude assess whether the analyzed
vehicle is overpriced, underpriced, or at market rate.

Usage:
  from backend.mcp.tools.search_comps import search_comps
  comps = await search_comps(2019, "Honda", "Civic", "LX", "Austin, TX")
"""

import os
import re
import logging
from typing import Optional
from urllib.parse import urlparse, urlencode

import httpx

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

SERPAPI_BASE_URL = "https://serpapi.com/search"
BRAVE_SEARCH_BASE_URL = "https://api.search.brave.com/res/v1/web/search"
FETCH_TIMEOUT_SECONDS = 10
MAX_RESULTS = 5

# Sites we trust for car listing data — used to filter search results
TRUSTED_LISTING_SITES = (
    "cargurus.com",
    "autotrader.com",
    "cars.com",
    "carmax.com",
    "truecar.com",
    "ebay.com/itm",
    "facebook.com/marketplace",
)


# ── Main entry point ──────────────────────────────────────────────────────────

async def search_comps(
    year: int,
    make: str,
    model: str,
    trim: str,
    location: str,
    max_results: int = MAX_RESULTS,
) -> list[dict]:
    """
    Search for comparable listings for a given vehicle.

    Args:
        year: Model year (e.g., 2019)
        make: Manufacturer (e.g., "Honda")
        model: Model name (e.g., "Civic")
        trim: Trim level (e.g., "LX") — can be empty string if unknown
        location: City/state string (e.g., "Austin, TX")
        max_results: Max number of comps to return (default 5)

    Returns:
        List of comp dicts. May be empty if no results found.
    """
    query = _build_query(year, make, model, trim, location)
    logger.info(f"[search_comps] Query: '{query}'")

    serpapi_key = os.getenv("SERPAPI_KEY")
    brave_key = os.getenv("BRAVE_SEARCH_KEY")

    # Try SerpAPI first, fall back to Brave Search
    raw_results: list[dict] = []

    if serpapi_key:
        try:
            raw_results = await _search_serpapi(query, serpapi_key)
            logger.info(f"[search_comps] SerpAPI returned {len(raw_results)} results")
        except Exception as e:
            logger.warning(f"[search_comps] SerpAPI failed: {e}, trying Brave...")

    if not raw_results and brave_key:
        try:
            raw_results = await _search_brave(query, brave_key)
            logger.info(f"[search_comps] Brave returned {len(raw_results)} results")
        except Exception as e:
            logger.warning(f"[search_comps] Brave Search failed: {e}")

    if not raw_results:
        logger.warning("[search_comps] Both search APIs failed or returned no results")
        return []

    # Parse and normalize results
    comps = _parse_results(raw_results, max_results)
    logger.info(f"[search_comps] Returning {len(comps)} comps")
    return comps


# ── Query building ────────────────────────────────────────────────────────────

def _build_query(year: int, make: str, model: str, trim: str, location: str) -> str:
    """
    Build a search query optimized for finding used car listings.

    Including site: operators for major listing sites improves result relevance.
    """
    vehicle = f"{year} {make} {model}"
    if trim:
        vehicle += f" {trim}"

    # Site-scope the search to the most reliable listing sources
    site_filter = " OR ".join(
        f"site:{s}" for s in ["cargurus.com", "autotrader.com", "cars.com"]
    )

    return f"{vehicle} for sale near {location} ({site_filter})"


# ── SerpAPI ───────────────────────────────────────────────────────────────────

async def _search_serpapi(query: str, api_key: str) -> list[dict]:
    """
    Search using SerpAPI (Google results).
    Returns the organic_results list from the SerpAPI response.

    SerpAPI docs: https://serpapi.com/search-api
    """
    params = {
        "q": query,
        "api_key": api_key,
        "engine": "google",
        "num": 10,          # Fetch more than we need; we filter down
        "gl": "us",         # Country: US
        "hl": "en",         # Language: English
    }

    async with httpx.AsyncClient(timeout=FETCH_TIMEOUT_SECONDS) as client:
        response = await client.get(SERPAPI_BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()

    # SerpAPI returns organic_results for web search
    return data.get("organic_results", [])


# ── Brave Search ──────────────────────────────────────────────────────────────

async def _search_brave(query: str, api_key: str) -> list[dict]:
    """
    Search using the Brave Search API.
    Returns results normalized to the same shape as SerpAPI organic_results.

    Brave Search API docs: https://api.search.brave.com/app/documentation/web-search
    """
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    }
    params = {
        "q": query,
        "count": 10,
        "country": "us",
        "search_lang": "en",
    }

    async with httpx.AsyncClient(timeout=FETCH_TIMEOUT_SECONDS) as client:
        response = await client.get(BRAVE_SEARCH_BASE_URL, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

    # Normalize Brave results to the same shape as SerpAPI for unified parsing
    brave_results = data.get("web", {}).get("results", [])
    return [
        {
            "title": r.get("title", ""),
            "link": r.get("url", ""),
            "snippet": r.get("description", ""),
        }
        for r in brave_results
    ]


# ── Result parsing ────────────────────────────────────────────────────────────

def _parse_results(raw_results: list[dict], max_results: int) -> list[dict]:
    """
    Parse raw search results into normalized comp listings.

    Filters to trusted listing sites only, then extracts price and mileage
    from the result title and snippet using regex patterns.
    """
    comps: list[dict] = []

    for item in raw_results:
        if len(comps) >= max_results:
            break

        url = item.get("link", "") or item.get("url", "")
        if not url:
            continue

        # Skip non-listing results (e.g., news articles, forums)
        if not _is_listing_url(url):
            continue

        title = item.get("title", "")
        snippet = item.get("snippet", "") or item.get("description", "")
        combined_text = f"{title} {snippet}"

        price = _extract_price(combined_text)
        mileage = _extract_mileage(combined_text)

        comps.append({
            "title": title,
            "price": price,
            "mileage": mileage,
            "url": url,
            "source": _extract_source(url),
        })

    return comps


def _is_listing_url(url: str) -> bool:
    """Return True if the URL is from a trusted car listing site."""
    try:
        host = urlparse(url).netloc.lower().lstrip("www.")
        return any(site in host for site in TRUSTED_LISTING_SITES)
    except Exception:
        return False


def _extract_source(url: str) -> str:
    """Extract the site name from a URL (e.g., 'cargurus.com' → 'cargurus')."""
    try:
        host = urlparse(url).netloc.lower().lstrip("www.")
        return host.split(".")[0]
    except Exception:
        return "unknown"


def _extract_price(text: str) -> Optional[int]:
    """
    Extract a price from a search result title or snippet.
    Handles: "$18,500", "$18500", "18,500", "Price: $18,500"
    """
    # Match dollar amounts: $XX,XXX or $XXXXX
    match = re.search(r"\$\s*([\d,]+)", text)
    if match:
        digits = re.sub(r"[^\d]", "", match.group(1))
        value = int(digits) if digits else None
        # Sanity check: used cars should be between $1k and $150k
        if value and 1000 <= value <= 150_000:
            return value
    return None


def _extract_mileage(text: str) -> Optional[int]:
    """
    Extract mileage from a search result title or snippet.
    Handles: "62,345 miles", "62K miles", "62,345 mi"
    """
    # Pattern: number + optional comma + K/k or miles/mi
    match = re.search(r"([\d,]+)\s*[Kk]?\s*(?:miles?|mi)\b", text)
    if match:
        raw = match.group(1).replace(",", "")
        # Check for "K" suffix (e.g., "62K miles")
        if "k" in match.group(0).lower() and not raw.endswith("000"):
            try:
                return int(raw) * 1000
            except ValueError:
                return None
        try:
            value = int(raw)
            # Sanity check: 0–300k miles
            if 0 <= value <= 300_000:
                return value
        except ValueError:
            pass
    return None
