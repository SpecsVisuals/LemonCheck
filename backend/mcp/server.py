"""
mcp/server.py

MCP Tool Registry for LemonCheck
----------------------------------
Defines the tool schemas and dispatcher that power Claude's enrichment step.

How it works:
  1. get_tool_definitions() returns a list of Anthropic-format tool schemas.
     These are passed to the Claude API as the `tools` parameter on every
     enrichment call, telling Claude what tools are available and what args to use.

  2. dispatch_tool_call(name, args) receives a tool_use block from Claude's response
     and routes it to the correct async tool function, returning the result as a string.

  3. claude_agent.py imports both functions and handles the tool call loop.

Why this design:
  - Centralizes all tool definitions in one place (single source of truth)
  - Makes adding a new tool a one-file change: implement the tool, add it here
  - Clean separation between tool definitions (what Claude sees) and implementation
  - Mirrors how production MCP servers work, making the codebase a portfolio signal

Tool schemas follow the Anthropic tool use format:
  https://docs.anthropic.com/en/docs/tool-use

Usage:
  from backend.mcp.server import get_tool_definitions, dispatch_tool_call

  # In claude_agent.py enrichment loop:
  tools = get_tool_definitions()
  response = await anthropic_client.messages.create(..., tools=tools)
  result = await dispatch_tool_call(tool_name, tool_input)
"""

import json
import logging
from typing import Any

from backend.mcp.tools.web_fetch import web_fetch
from backend.mcp.tools.vin_decode import vin_decode
from backend.mcp.tools.search_comps import search_comps
from backend.mcp.tools.price_lookup import price_lookup

logger = logging.getLogger(__name__)


# ── Tool Definitions ──────────────────────────────────────────────────────────
# These are the JSON schemas Claude receives. They tell Claude:
#   - What the tool is called (name)
#   - What it does (description) — Claude reads this to decide when to use it
#   - What arguments it takes (input_schema) — Claude fills these from context

TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "web_fetch",
        "description": (
            "Fetch a used car listing page from CarGurus or AutoTrader and extract "
            "structured data. Use this first whenever you have a listing URL. "
            "Returns: year, make, model, trim, mileage, price, location, "
            "days_on_market, seller_type, vin."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": (
                        "Full listing URL from CarGurus (cargurus.com) or "
                        "AutoTrader (autotrader.com)"
                    ),
                }
            },
            "required": ["url"],
        },
    },
    {
        "name": "vin_decode",
        "description": (
            "Decode a 17-character VIN using the NHTSA free API to get full vehicle specs. "
            "Use this after web_fetch if a VIN was found in the listing. "
            "Returns: make, model, year, trim, body_style, engine, drivetrain, fuel_type. "
            "No API key required."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "vin": {
                    "type": "string",
                    "description": (
                        "17-character Vehicle Identification Number. "
                        "Must not contain I, O, or Q."
                    ),
                }
            },
            "required": ["vin"],
        },
    },
    {
        "name": "search_comps",
        "description": (
            "Search for comparable used car listings to establish a market price baseline. "
            "Use this after web_fetch to find what similar vehicles are selling for. "
            "Returns up to 5 listings with: title, price, mileage, url, source site. "
            "Use trim='' if the trim level is unknown."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {
                    "type": "integer",
                    "description": "Vehicle model year (e.g., 2019)",
                },
                "make": {
                    "type": "string",
                    "description": "Manufacturer name (e.g., 'Honda')",
                },
                "model": {
                    "type": "string",
                    "description": "Model name (e.g., 'Civic')",
                },
                "trim": {
                    "type": "string",
                    "description": "Trim level (e.g., 'LX'). Use empty string if unknown.",
                },
                "location": {
                    "type": "string",
                    "description": "City and state (e.g., 'Austin, TX')",
                },
            },
            "required": ["year", "make", "model", "trim", "location"],
        },
    },
    {
        "name": "price_lookup",
        "description": (
            "Get the market price range for a specific vehicle to determine if the "
            "listing is overpriced or underpriced. Use after search_comps. "
            "Returns: low, median, high price (USD), and sample_size (number of comps used). "
            "The price_delta in your final report should be: listing_price minus median."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {
                    "type": "integer",
                    "description": "Vehicle model year",
                },
                "make": {
                    "type": "string",
                    "description": "Manufacturer name",
                },
                "model": {
                    "type": "string",
                    "description": "Model name",
                },
                "trim": {
                    "type": "string",
                    "description": "Trim level. Use empty string if unknown.",
                },
                "mileage": {
                    "type": "integer",
                    "description": "Odometer reading in miles",
                },
            },
            "required": ["year", "make", "model", "trim", "mileage"],
        },
    },
]


# ── Public API ────────────────────────────────────────────────────────────────

def get_tool_definitions() -> list[dict]:
    """
    Return the list of tool schemas to pass to the Claude API.

    Usage in claude_agent.py:
        tools = get_tool_definitions()
        response = client.messages.create(..., tools=tools)
    """
    return TOOL_DEFINITIONS


async def dispatch_tool_call(name: str, tool_input: dict[str, Any]) -> str:
    """
    Route a Claude tool_use request to the correct tool implementation.

    Claude returns tool_use blocks in its response when it wants to call a tool.
    This function receives the tool name and input args, calls the right function,
    and returns the result serialized as a JSON string (which becomes the
    tool_result content sent back to Claude in the next turn).

    Args:
        name: Tool name as returned by Claude (matches TOOL_DEFINITIONS names)
        tool_input: Dict of arguments Claude chose to pass

    Returns:
        JSON string of the tool result (or error message string)

    Raises:
        ValueError: If the tool name is not recognized
    """
    logger.info(f"[mcp/server] Dispatching tool: {name} with args: {tool_input}")

    try:
        if name == "web_fetch":
            result = await web_fetch(url=tool_input["url"])

        elif name == "vin_decode":
            result = await vin_decode(vin=tool_input["vin"])

        elif name == "search_comps":
            result = await search_comps(
                year=tool_input["year"],
                make=tool_input["make"],
                model=tool_input["model"],
                trim=tool_input.get("trim", ""),
                location=tool_input["location"],
            )

        elif name == "price_lookup":
            result = await price_lookup(
                year=tool_input["year"],
                make=tool_input["make"],
                model=tool_input["model"],
                trim=tool_input.get("trim", ""),
                mileage=tool_input["mileage"],
            )

        else:
            raise ValueError(f"Unknown tool: '{name}'")

        logger.info(f"[mcp/server] Tool '{name}' succeeded")
        return json.dumps(result, default=str)

    except Exception as e:
        # Return errors as a structured string so Claude can handle them gracefully
        # rather than crashing the enrichment loop
        error_msg = f"Tool '{name}' failed: {type(e).__name__}: {str(e)}"
        logger.error(f"[mcp/server] {error_msg}")
        return json.dumps({"error": error_msg, "tool": name, "input": tool_input})


def get_tool_names() -> list[str]:
    """Return just the tool names — useful for validation."""
    return [t["name"] for t in TOOL_DEFINITIONS]
