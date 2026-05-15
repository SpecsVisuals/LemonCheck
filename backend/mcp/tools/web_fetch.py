"""
mcp/tools/web_fetch.py

MCP Tool: web_fetch
--------------------
Fetches a used car listing page from CarGurus or AutoTrader using httpx (async),
then extracts structured listing data using BeautifulSoup + JSON-LD parsing.

Extraction strategy (in priority order):
  1. JSON-LD structured data (schema.org/Car) — most reliable, site-agnostic
  2. Open Graph meta tags — price, title as fallback
  3. Site-specific CSS selectors — CarGurus and AutoTrader have known DOM patterns

Returns a normalized ListingData dict so the Claude agent always sees the same
shape regardless of which site the URL came from.

Usage:
  from mcp.tools.web_fetch import web_fetch
  result = await web_fetch("https://www.cargurus.com/Cars/...")
"""

import re
import json
import logging
from typing import Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ── Types ─────────────────────────────────────────────────────────────────────

# The normalized output shape returned by this tool.
# All fields are Optional — scraping is inherently unreliable.
ListingData = dict  # keys defined in LISTING_DATA_KEYS below

LISTING_DATA_KEYS = [
    "year", "make", "model", "trim", "mileage", "price",
    "location", "days_on_market", "seller_type", "vin",
    "listing_url", "source_site",
]

# ── Constants ─────────────────────────────────────────────────────────────────

SUPPORTED_SITES = ("cargurus.com", "autotrader.com")

# Browser-like headers to reduce the chance of being blocked.
# These mimic a Chrome browser on macOS.
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

FETCH_TIMEOUT_SECONDS = 15


# ── Main entry point ──────────────────────────────────────────────────────────

async def web_fetch(url: str) -> ListingData:
    """
    Fetch and parse a used car listing from CarGurus or AutoTrader.

    Args:
        url: Full listing URL (CarGurus or AutoTrader)

    Returns:
        ListingData dict with normalized fields. Missing fields are None.

    Raises:
        ValueError: If the URL is not from a supported site
        httpx.HTTPError: If the fetch fails after retries
    """
    site = _detect_site(url)
    if not site:
        raise ValueError(
            f"Unsupported listing site. Supported: {SUPPORTED_SITES}. Got: {url}"
        )

    logger.info(f"[web_fetch] Fetching {site} listing: {url}")

    html = await _fetch_html(url)
    soup = BeautifulSoup(html, "lxml")

    # Build result by trying extraction strategies in priority order
    result: ListingData = {key: None for key in LISTING_DATA_KEYS}
    result["listing_url"] = url
    result["source_site"] = site

    # Strategy 1: JSON-LD structured data (schema.org) — most reliable
    _extract_json_ld(soup, result)

    # Strategy 2: Open Graph / meta tags (fills in gaps from JSON-LD)
    _extract_meta_tags(soup, result)

    # Strategy 3: Site-specific CSS selectors (last resort)
    if site == "cargurus.com":
        _extract_cargurus(soup, result)
    elif site == "autotrader.com":
        _extract_autotrader(soup, result)

    # Normalize numeric fields so downstream code always gets ints
    result["price"] = _parse_price(result.get("price"))
    result["mileage"] = _parse_mileage(result.get("mileage"))
    result["year"] = _parse_year(result.get("year"))
    result["days_on_market"] = _parse_int(result.get("days_on_market"))

    logger.info(
        f"[web_fetch] Extracted: {result.get('year')} {result.get('make')} "
        f"{result.get('model')} — ${result.get('price')} / {result.get('mileage')}mi"
    )
    return result


# ── HTML fetching ─────────────────────────────────────────────────────────────

async def _fetch_html(url: str) -> str:
    """Fetch page HTML with browser-like headers and a reasonable timeout."""
    async with httpx.AsyncClient(
        headers=REQUEST_HEADERS,
        timeout=FETCH_TIMEOUT_SECONDS,
        follow_redirects=True,
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


# ── Extraction: JSON-LD ───────────────────────────────────────────────────────

def _extract_json_ld(soup: BeautifulSoup, result: ListingData) -> None:
    """
    Parse <script type="application/ld+json"> blocks for schema.org/Car data.
    This is the most structured and reliable extraction method when present.
    Both CarGurus and AutoTrader embed JSON-LD, though the fields vary.
    """
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        # Handle both single objects and @graph arrays
        items = data if isinstance(data, list) else [data]
        for item in items:
            schema_type = item.get("@type", "")
            if schema_type in ("Car", "Vehicle"):
                _map_json_ld_fields(item, result)
                return

            # Some sites nest the car inside a broader page object
            if "offers" in item and isinstance(item.get("offers"), dict):
                _map_json_ld_fields(item, result)


def _map_json_ld_fields(data: dict, result: ListingData) -> None:
    """Map schema.org Car/Vehicle fields to our normalized ListingData output."""
    if not result["make"]:
        brand = data.get("brand", {})
        result["make"] = (brand.get("name") if isinstance(brand, dict) else brand) or data.get("manufacturer")
    if not result["model"]:
        result["model"] = data.get("model")
    if not result["year"]:
        raw_year = data.get("modelYear") or str(data.get("productionDate", ""))[:4]
        result["year"] = raw_year or None
    if not result["vin"]:
        result["vin"] = data.get("vehicleIdentificationNumber")
    if not result["mileage"]:
        mileage_spec = data.get("mileageFromOdometer", {})
        result["mileage"] = (
            mileage_spec.get("value") if isinstance(mileage_spec, dict) else mileage_spec
        )
    if not result["price"]:
        offers = data.get("offers", {})
        result["price"] = (
            offers.get("price") if isinstance(offers, dict) else data.get("price")
        )
    if not result["trim"]:
        result["trim"] = data.get("vehicleConfiguration") or data.get("version")
    if not result["location"]:
        available = data.get("availableAtOrFrom", {})
        address = available.get("address", {}) if isinstance(available, dict) else {}
        if address:
            city = address.get("addressLocality", "")
            state = address.get("addressRegion", "")
            combined = f"{city}, {state}".strip(", ")
            result["location"] = combined or None


# ── Extraction: Meta tags ─────────────────────────────────────────────────────

def _extract_meta_tags(soup: BeautifulSoup, result: ListingData) -> None:
    """Extract Open Graph and standard meta tags as a secondary data source."""

    def meta(prop: str) -> Optional[str]:
        tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        return tag.get("content", "").strip() if tag else None

    og_title = meta("og:title") or ""

    # og:title often contains "2019 Honda Civic LX — $15,900"
    if og_title and not result.get("make"):
        _parse_title_string(og_title, result)

    if not result["price"]:
        result["price"] = meta("og:price:amount") or meta("product:price:amount")


# ── Extraction: CarGurus specific ─────────────────────────────────────────────

def _extract_cargurus(soup: BeautifulSoup, result: ListingData) -> None:
    """
    CarGurus-specific CSS selector fallbacks.
    CarGurus heavily JS-renders, but key fields often appear in static HTML too.
    """
    if not result["price"]:
        price_el = (
            soup.find("span", attrs={"data-testid": "listing-price"})
            or soup.find("span", class_=re.compile(r"price", re.I))
            or soup.find("div", class_=re.compile(r"priceSection", re.I))
        )
        if price_el:
            result["price"] = price_el.get_text(strip=True)

    if not result["mileage"]:
        mileage_text = soup.find(string=re.compile(r"\d[\d,]+\s*mi(?:les)?", re.I))
        if mileage_text:
            result["mileage"] = mileage_text.strip()

    if not result["days_on_market"]:
        listed_text = soup.find(string=re.compile(r"listed\s+(\d+)\s+day", re.I))
        if listed_text:
            match = re.search(r"(\d+)\s+day", str(listed_text), re.I)
            if match:
                result["days_on_market"] = match.group(1)

    if not result["seller_type"]:
        seller_text = soup.find(string=re.compile(r"private\s+seller|dealership|dealer", re.I))
        if seller_text:
            result["seller_type"] = "private" if "private" in str(seller_text).lower() else "dealer"

    if not result["make"]:
        h1 = soup.find("h1")
        if h1:
            _parse_title_string(h1.get_text(strip=True), result)


# ── Extraction: AutoTrader specific ──────────────────────────────────────────

def _extract_autotrader(soup: BeautifulSoup, result: ListingData) -> None:
    """AutoTrader-specific CSS selector fallbacks."""
    if not result["price"]:
        price_el = (
            soup.find("span", attrs={"data-cmp": "firstPrice"})
            or soup.find("div", class_=re.compile(r"price-section|listing-price", re.I))
        )
        if price_el:
            result["price"] = price_el.get_text(strip=True)

    if not result["mileage"]:
        mileage_text = soup.find(string=re.compile(r"\d[\d,]+\s*mi(?:les)?", re.I))
        if mileage_text:
            result["mileage"] = mileage_text.strip()

    if not result["seller_type"]:
        seller_text = soup.find(string=re.compile(r"private\s+seller|dealership", re.I))
        if seller_text:
            result["seller_type"] = "private" if "private" in str(seller_text).lower() else "dealer"

    if not result["make"]:
        h1 = soup.find("h1")
        if h1:
            _parse_title_string(h1.get_text(strip=True), result)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _detect_site(url: str) -> Optional[str]:
    """Return the normalized site name for a supported listing URL, or None."""
    try:
        host = urlparse(url).netloc.lower().lstrip("www.")
        for site in SUPPORTED_SITES:
            if host == site or host.endswith(f".{site}"):
                return site
    except Exception:
        pass
    return None


def _parse_title_string(title: str, result: ListingData) -> None:
    """
    Attempt to extract year/make/model/trim from a listing title string.
    Handles: "Used 2019 Honda Civic LX" or "2021 Toyota Camry SE — Certified"
    """
    title = re.sub(r"^(used|certified|new|pre-owned)\s+", "", title, flags=re.I).strip()

    year_match = re.search(r"\b(19|20)\d{2}\b", title)
    if year_match and not result.get("year"):
        result["year"] = year_match.group(0)
        title = title[year_match.end():].strip()

    parts = title.split()
    if parts and not result.get("make"):
        result["make"] = parts[0]
    if len(parts) > 1 and not result.get("model"):
        result["model"] = parts[1]
    if len(parts) > 2 and not result.get("trim"):
        # Trim is everything after model, up to a dash or em-dash separator
        result["trim"] = re.split(r"[—\-]", " ".join(parts[2:]))[0].strip()


def _parse_price(raw: Optional[str | int | float]) -> Optional[int]:
    """Parse '$18,500' or 18500.0 → 18500."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return int(raw)
    digits = re.sub(r"[^\d]", "", str(raw))
    return int(digits) if digits else None


def _parse_mileage(raw: Optional[str | int | float]) -> Optional[int]:
    """Parse '62,345 mi' or 62345 → 62345."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return int(raw)
    digits = re.sub(r"[^\d]", "", str(raw).split("mi")[0])
    return int(digits) if digits else None


def _parse_year(raw: Optional[str | int]) -> Optional[int]:
    """Parse '2019' or 2019 → 2019."""
    if raw is None:
        return None
    try:
        return int(str(raw)[:4])
    except (ValueError, TypeError):
        return None


def _parse_int(raw: Optional[str | int]) -> Optional[int]:
    """Generic string → int, stripping non-digit characters."""
    if raw is None:
        return None
    try:
        return int(re.sub(r"[^\d]", "", str(raw)))
    except (ValueError, TypeError):
        return None
