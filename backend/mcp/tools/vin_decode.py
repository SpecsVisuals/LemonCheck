"""
mcp/tools/vin_decode.py

MCP Tool: vin_decode
---------------------
Decodes a 17-character VIN using the NHTSA free public API.
No API key required — NHTSA is a U.S. government open data service.

API endpoint:
  GET https://vpic.nhtsa.dot.gov/api/vehicles/decodevin/{vin}?format=json

The NHTSA API returns a flat list of {"Variable": "...", "Value": "..."} pairs.
This tool maps the relevant pairs to a clean, typed output dict.

Returns:
  {
    "vin": str,
    "make": str | None,
    "model": str | None,
    "year": int | None,
    "trim": str | None,
    "body_style": str | None,
    "engine": str | None,
    "drivetrain": str | None,
    "fuel_type": str | None,
    "error_code": str | None,   # NHTSA error code ("0" = no error)
    "error_text": str | None,
  }

Usage:
  from mcp.tools.vin_decode import vin_decode
  result = await vin_decode("1HGCM82633A123456")
"""

import re
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

NHTSA_BASE_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/decodevin"
FETCH_TIMEOUT_SECONDS = 10

# VIN characters: alphanumeric excluding I, O, Q (per ISO 3779)
VIN_PATTERN = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$", re.IGNORECASE)

# Map NHTSA variable names → our output field names
NHTSA_FIELD_MAP = {
    "Make":                          "make",
    "Model":                         "model",
    "Model Year":                    "year",
    "Trim":                          "trim",
    "Body Class":                    "body_style",
    "Engine Number of Cylinders":    "_cylinders",
    "Displacement (L)":              "_displacement",
    "Fuel Type - Primary":           "fuel_type",
    "Drive Type":                    "drivetrain",
    "Error Code":                    "error_code",
    "Error Text":                    "error_text",
}


# ── Main entry point ──────────────────────────────────────────────────────────

async def vin_decode(vin: str) -> dict:
    """
    Decode a VIN using the NHTSA free API.

    Args:
        vin: 17-character Vehicle Identification Number

    Returns:
        Normalized dict of vehicle specs. Unknown fields are None.

    Raises:
        ValueError: If VIN format is invalid (wrong length or illegal characters)
        httpx.HTTPError: If the NHTSA API request fails
    """
    vin = vin.strip().upper()
    _validate_vin(vin)

    logger.info(f"[vin_decode] Decoding VIN: {vin}")

    raw_results = await _fetch_nhtsa(vin)
    result = _parse_nhtsa_response(vin, raw_results)

    logger.info(
        f"[vin_decode] Decoded: {result.get('year')} {result.get('make')} "
        f"{result.get('model')} {result.get('trim') or ''} "
        f"(error_code={result.get('error_code')})"
    )
    return result


# ── NHTSA API call ────────────────────────────────────────────────────────────

async def _fetch_nhtsa(vin: str) -> list[dict]:
    """
    Call the NHTSA decodevin API and return the raw Results list.
    NHTSA returns HTTP 200 even for invalid VINs — check error_code in the response.
    """
    url = f"{NHTSA_BASE_URL}/{vin}?format=json"

    async with httpx.AsyncClient(timeout=FETCH_TIMEOUT_SECONDS) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

    results = data.get("Results", [])
    if not results:
        raise ValueError(f"NHTSA returned empty Results for VIN: {vin}")

    return results


# ── Response parsing ──────────────────────────────────────────────────────────

def _parse_nhtsa_response(vin: str, results: list[dict]) -> dict:
    """
    Map the flat NHTSA Results list into our clean output dict.

    NHTSA returns ~100+ variable/value pairs; we pick the useful ones.
    Empty strings from NHTSA are normalized to None.
    """
    # Build a lookup: {"Variable Name": "value", ...}
    nhtsa_map: dict[str, Optional[str]] = {}
    for item in results:
        variable = item.get("Variable", "")
        value = item.get("Value", "") or item.get("ValueId", "")
        nhtsa_map[variable] = value.strip() if value else None

    # Initialize output with all expected fields as None
    output: dict = {
        "vin": vin,
        "make": None,
        "model": None,
        "year": None,
        "trim": None,
        "body_style": None,
        "engine": None,
        "drivetrain": None,
        "fuel_type": None,
        "error_code": None,
        "error_text": None,
    }

    # Map NHTSA fields to our output fields
    for nhtsa_var, our_field in NHTSA_FIELD_MAP.items():
        value = nhtsa_map.get(nhtsa_var)
        if value and our_field.startswith("_"):
            # Private accumulator fields for engine string assembly
            output[our_field] = value
        elif value:
            output[our_field] = value

    # Normalize year to int
    if output["year"]:
        try:
            output["year"] = int(output["year"])
        except (ValueError, TypeError):
            output["year"] = None

    # Assemble a human-readable engine string from cylinders + displacement
    # e.g. "4-cylinder 2.0L"
    cylinders = output.pop("_cylinders", None)
    displacement = output.pop("_displacement", None)
    if cylinders or displacement:
        parts = []
        if cylinders:
            parts.append(f"{cylinders}-cylinder")
        if displacement:
            parts.append(f"{float(displacement):.1f}L")
        output["engine"] = " ".join(parts)

    # Normalize NHTSA error code "0" to a clean flag
    # "0" = no errors, "6" = manufacturer not found in DB, etc.
    if output["error_code"] == "0":
        output["error_text"] = None  # No error — clear the verbose NHTSA message

    return output


# ── Validation ────────────────────────────────────────────────────────────────

def _validate_vin(vin: str) -> None:
    """
    Validate VIN format per ISO 3779.
    - Must be exactly 17 characters
    - No I, O, or Q (to prevent confusion with 1, 0, and 0)
    - Alphanumeric only

    Raises ValueError with a clear message if invalid.
    """
    if len(vin) != 17:
        raise ValueError(
            f"Invalid VIN: must be exactly 17 characters, got {len(vin)}: '{vin}'"
        )
    if not VIN_PATTERN.match(vin):
        raise ValueError(
            f"Invalid VIN: contains illegal characters (I, O, Q not allowed): '{vin}'"
        )
