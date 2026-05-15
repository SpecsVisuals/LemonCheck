# LemonCheck — MCP Tools Reference

> Complete API reference for the four tools used by the Claude agent during the enrichment step.
> Updated: Day 1 build.

---

## Overview

LemonCheck uses Claude's tool use feature (Model Context Protocol) to give the AI agent structured access to real-world data. During the enrichment phase, Claude calls these tools autonomously — choosing which tools to call and in what order based on what data it needs.

The tool loop (implemented in `backend/services/claude_agent.py`) runs for up to 8 iterations, accumulating data until Claude has enough to produce a DealReport.

Tool definitions are registered in `backend/mcp/server.py`. Adding a new tool requires: (1) implement the function in `backend/mcp/tools/`, (2) add it to `TOOL_DEFINITIONS` and `dispatch_tool_call` in `server.py`.

---

## Tool: `web_fetch`

**File:** `backend/mcp/tools/web_fetch.py`

Fetches a used car listing page and extracts structured data. This is always the first tool called when a URL is provided.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | string | ✅ | Full listing URL from CarGurus or AutoTrader |

### Returns

```json
{
  "year": 2019,
  "make": "Honda",
  "model": "Civic",
  "trim": "LX",
  "mileage": 62345,
  "price": 16500,
  "location": "Austin, TX",
  "days_on_market": 12,
  "seller_type": "private",
  "vin": "2HGFC2F59KH123456",
  "listing_url": "https://www.cargurus.com/...",
  "source_site": "cargurus.com"
}
```

All fields are nullable — scraping is inherently unreliable. Missing fields are `null`.

### Supported sites
- `cargurus.com`
- `autotrader.com`

### Extraction strategy

1. **JSON-LD** (`<script type="application/ld+json">`) — schema.org/Car data. Most reliable.
2. **Open Graph meta tags** — fallback for price and title.
3. **Site-specific CSS selectors** — last resort, per-site DOM patterns.

### Errors

| Error | When |
|-------|------|
| `ValueError: Unsupported listing site` | URL is not from CarGurus or AutoTrader |
| `httpx.HTTPStatusError` | HTTP 4xx/5xx from the listing site |
| `httpx.TimeoutException` | Listing page didn't respond within 15 seconds |

---

## Tool: `vin_decode`

**File:** `backend/mcp/tools/vin_decode.py`

Decodes a VIN using the NHTSA (National Highway Traffic Safety Administration) free public API. No API key required.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `vin` | string | ✅ | 17-character Vehicle Identification Number |

### Returns

```json
{
  "vin": "2HGFC2F59KH123456",
  "make": "HONDA",
  "model": "Civic",
  "year": 2019,
  "trim": "LX",
  "body_style": "Sedan/Saloon",
  "engine": "4-cylinder 2.0L",
  "drivetrain": "FWD/Front-Wheel Drive",
  "fuel_type": "Gasoline",
  "error_code": "0",
  "error_text": null
}
```

`error_code: "0"` means a clean decode. Non-zero codes indicate partial matches.

### VIN validation (ISO 3779)
- Must be exactly 17 characters
- Characters I, O, Q are not permitted (visually ambiguous with 1, 0, 0)
- Alphanumeric only

### API endpoint
```
GET https://vpic.nhtsa.dot.gov/api/vehicles/decodevin/{vin}?format=json
```

### Errors

| Error | When |
|-------|------|
| `ValueError: Invalid VIN: must be exactly 17 characters` | Wrong length |
| `ValueError: Invalid VIN: contains illegal characters` | I, O, or Q found |
| `httpx.HTTPStatusError` | NHTSA API unavailable |

---

## Tool: `search_comps`

**File:** `backend/mcp/tools/search_comps.py`

Searches for comparable used car listings to establish a market price baseline.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `year` | integer | ✅ | Model year (e.g., `2019`) |
| `make` | string | ✅ | Manufacturer (e.g., `"Honda"`) |
| `model` | string | ✅ | Model name (e.g., `"Civic"`) |
| `trim` | string | ✅ | Trim level (e.g., `"LX"`). Pass `""` if unknown. |
| `location` | string | ✅ | City and state (e.g., `"Austin, TX"`) |

### Returns

```json
[
  {
    "title": "2019 Honda Civic LX — $15,995 — 58,000 miles",
    "price": 15995,
    "mileage": 58000,
    "url": "https://www.cargurus.com/Cars/listingDetail.action?listing=123",
    "source": "cargurus"
  }
]
```

Up to 5 results. `price` and `mileage` are nullable (extracted via regex from snippets).

### API priority

1. **SerpAPI** (primary) — requires `SERPAPI_KEY` env var
2. **Brave Search** (fallback) — requires `BRAVE_SEARCH_KEY` env var
3. **Empty list** — returned gracefully if neither key is set

### Result filtering

Results are filtered to trusted listing sites only:
`cargurus.com`, `autotrader.com`, `cars.com`, `carmax.com`, `truecar.com`, `ebay.com/itm`, `facebook.com/marketplace`

News articles, forum posts, and review sites are excluded.

### Errors

This tool does not raise on API failures — it returns an empty list and logs a warning. This allows the Claude agent to continue even when search is unavailable.

---

## Tool: `price_lookup`

**File:** `backend/mcp/tools/price_lookup.py`

Aggregates market price data to produce a price range for a specific vehicle. Used by Claude to calculate `price_delta` in the DealReport.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `year` | integer | ✅ | Model year |
| `make` | string | ✅ | Manufacturer |
| `model` | string | ✅ | Model name |
| `trim` | string | ✅ | Trim level. Pass `""` if unknown. |
| `mileage` | integer | ✅ | Odometer reading of the analyzed vehicle (for adjustment) |

### Returns

```json
{
  "low": 14500,
  "median": 16200,
  "high": 18100,
  "mean": 16100,
  "sample_size": 5,
  "mileage_adjusted": true
}
```

Or, if insufficient data:

```json
{
  "low": null,
  "median": null,
  "high": null,
  "mean": null,
  "sample_size": 1,
  "mileage_adjusted": false,
  "error": "Insufficient comp data (1 priced results found)"
}
```

### Calculation methodology

1. Calls `search_comps` with `max_results=10` and broad location
2. Extracts prices from results that have price data
3. If ≥50% of comps have mileage, applies **mileage adjustment** (`$0.06/mile` depreciation delta)
4. Removes **outliers** (prices >2 standard deviations from mean)
5. Returns 10th/50th/90th percentile as low/median/high

### Claude usage note

Claude should calculate `price_delta` as:
```
price_delta = listing_price - median
```
Positive = overpriced, negative = underpriced.

---

## Tool Registration: `mcp/server.py`

The `server.py` module is the single integration point between Claude and the tools.

```python
from backend.mcp.server import get_tool_definitions, dispatch_tool_call

# Pass to Claude API
tools = get_tool_definitions()  # → list of 4 Anthropic-format tool schemas

# In the tool call loop
result_json = await dispatch_tool_call(tool_name, tool_input)
```

All tool errors are caught by `dispatch_tool_call` and returned as a JSON string with an `"error"` key. The Claude agent can read this and decide how to proceed (retry, skip, or note the failure in its analysis).

---

## Adding a New Tool

1. Create `backend/mcp/tools/your_tool.py` with an async function
2. Add the tool schema to `TOOL_DEFINITIONS` in `server.py`
3. Add a routing case to `dispatch_tool_call` in `server.py`
4. Write unit tests in `backend/tests/test_tools.py`
5. Update this doc

---

*Last updated: Day 1 build — tools: web_fetch, vin_decode, search_comps, price_lookup*
