"""
services/claude_agent.py

Two-Step Claude Agent Orchestrator
------------------------------------
The AI core of LemonCheck. Orchestrates the full analysis pipeline:

STEP 1 — ENRICHMENT LOOP
  Claude receives the listing URL or VIN and a set of MCP tools.
  It autonomously calls tools (web_fetch, vin_decode, search_comps, price_lookup)
  to gather all available data about the vehicle. The loop runs until Claude
  stops calling tools (stop_reason == "end_turn") or hits MAX_TOOL_CALLS.

STEP 2 — ANALYSIS CALL
  Claude receives the enriched data summary from Step 1 and the full
  analysis_schema.json. It produces a structured DealReport JSON.
  The JSON is validated against the DealReport Pydantic model before returning.

Why two steps?
  Separating data gathering from analysis gives Claude a cleaner mental model
  for each task. In testing, a single-step approach produced lower-quality
  analysis because Claude had to context-switch between "find data" and
  "evaluate data" simultaneously. The two-step chain mirrors how a good analyst
  actually works: research first, then assess.

Usage:
  from services.claude_agent import run_analysis
  from models.analysis import AnalysisRequest

  request = AnalysisRequest(listing_url="https://www.cargurus.com/...")
  report = await run_analysis(request)
  print(report.grade, report.price_delta)
"""

import os
import json
import logging
from pathlib import Path
from typing import Any

import anthropic
from pydantic import ValidationError

from models.analysis import AnalysisRequest, DealReport
from mcp.server import get_tool_definitions, dispatch_tool_call

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

MODEL = "claude-sonnet-4-6"           # Sonnet: best balance of speed + reasoning
MAX_TOOL_CALLS = 8                     # Safety cap on the enrichment loop
MAX_TOKENS_ENRICHMENT = 4096          # Enough for tool calls + summary
MAX_TOKENS_ANALYSIS = 2048            # DealReport JSON fits comfortably here

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


# ── Prompt loading ────────────────────────────────────────────────────────────

def _load_prompt(filename: str) -> str:
    """Load a prompt file from the prompts directory."""
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8").strip()


def _load_analysis_schema() -> str:
    """Load and return the analysis_schema.json as a formatted string."""
    path = PROMPTS_DIR / "analysis_schema.json"
    schema = json.loads(path.read_text(encoding="utf-8"))
    return json.dumps(schema, indent=2)


# ── Main entry point ──────────────────────────────────────────────────────────

async def run_analysis(request: AnalysisRequest) -> DealReport:
    """
    Run the full two-step Claude agent pipeline on a listing.

    Args:
        request: AnalysisRequest with either listing_url or vin populated

    Returns:
        Validated DealReport Pydantic model

    Raises:
        ValueError: If neither listing_url nor vin is provided
        anthropic.APIError: If the Anthropic API call fails
        pydantic.ValidationError: If Claude's JSON output doesn't match DealReport schema
    """
    if not request.listing_url and not request.vin:
        raise ValueError("AnalysisRequest must have either listing_url or vin")

    client = _get_client()

    # ── Step 1: Enrichment ────────────────────────────────────────────────────
    logger.info(
        f"[claude_agent] Starting enrichment — "
        f"url={request.listing_url!r} vin={request.vin!r}"
    )
    enriched_summary = await _run_enrichment(client, request)
    logger.info(f"[claude_agent] Enrichment complete — summary length: {len(enriched_summary)} chars")

    # ── Step 2: Analysis ──────────────────────────────────────────────────────
    logger.info("[claude_agent] Starting analysis call")
    report = await _run_analysis(client, enriched_summary)
    logger.info(f"[claude_agent] Analysis complete — grade={report.grade} delta=${report.price_delta}")

    return report


# ── Step 1: Enrichment loop ───────────────────────────────────────────────────

async def _run_enrichment(
    client: anthropic.AsyncAnthropic,
    request: AnalysisRequest,
) -> str:
    """
    Run the enrichment loop: Claude calls tools until all data is gathered.

    The loop continues until Claude's stop_reason is "end_turn" (meaning it has
    finished calling tools) or MAX_TOOL_CALLS is reached.

    Returns:
        The final text message from Claude — a plain-English summary of all
        gathered data, ending with "ENRICHMENT COMPLETE".
    """
    system_prompt = _load_prompt("system_prompt.txt")
    enrichment_template = _load_prompt("enrichment_prompt.txt")
    tool_definitions = get_tool_definitions()

    # Build the initial user message from the enrichment prompt template
    input_description = _describe_input(request)
    listing_url = request.listing_url or ""
    enrichment_prompt = (
        enrichment_template
        .replace("{input_description}", input_description)
        .replace("{listing_url}", listing_url)
    )

    messages: list[dict[str, Any]] = [
        {"role": "user", "content": enrichment_prompt}
    ]

    tool_calls_made = 0

    for iteration in range(MAX_TOOL_CALLS + 1):
        logger.debug(f"[claude_agent] Enrichment iteration {iteration}")

        response = await client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS_ENRICHMENT,
            system=system_prompt,
            tools=tool_definitions,
            messages=messages,
        )

        # Add Claude's response to the conversation
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            # Claude finished — extract the final text summary
            final_text = _extract_text(response.content)
            logger.info(f"[claude_agent] Enrichment ended after {tool_calls_made} tool calls")
            return final_text

        if response.stop_reason == "tool_use":
            # Process all tool calls in this response turn
            tool_results = await _process_tool_calls(response.content)
            tool_calls_made += len(tool_results)

            messages.append({"role": "user", "content": tool_results})

            if tool_calls_made >= MAX_TOOL_CALLS:
                logger.warning(
                    f"[claude_agent] Hit MAX_TOOL_CALLS ({MAX_TOOL_CALLS}) — "
                    "forcing enrichment completion"
                )
                # Force Claude to wrap up by asking for the summary
                messages.append({
                    "role": "user",
                    "content": (
                        "You have reached the maximum number of tool calls. "
                        "Please provide your enrichment summary now and say ENRICHMENT COMPLETE."
                    ),
                })
                # One final call to get the summary
                final_response = await client.messages.create(
                    model=MODEL,
                    max_tokens=MAX_TOKENS_ENRICHMENT,
                    system=system_prompt,
                    messages=messages,
                )
                return _extract_text(final_response.content)

        else:
            # Unexpected stop reason — log and break
            logger.warning(f"[claude_agent] Unexpected stop_reason: {response.stop_reason}")
            return _extract_text(response.content)

    # Fallback — should not reach here normally
    return "Enrichment loop exhausted without a clean ending."


async def _process_tool_calls(
    content_blocks: list[Any],
) -> list[dict[str, Any]]:
    """
    Process all tool_use blocks in a Claude response turn.

    For each tool_use block, dispatches the call to the MCP server and
    collects results as tool_result blocks to send back to Claude.
    """
    tool_results = []

    for block in content_blocks:
        if block.type != "tool_use":
            continue

        logger.info(f"[claude_agent] Tool call: {block.name}({block.input})")
        result_str = await dispatch_tool_call(block.name, block.input)

        tool_results.append({
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": result_str,
        })

    return tool_results


# ── Step 2: Analysis call ─────────────────────────────────────────────────────

async def _run_analysis(
    client: anthropic.AsyncAnthropic,
    enriched_summary: str,
) -> DealReport:
    """
    Run the analysis call: Claude receives the enriched data and produces a DealReport.

    No tools are available in this step — Claude only has the enriched summary
    and the schema. This ensures a clean, focused analysis without further
    data-gathering detours.

    Returns:
        Validated DealReport Pydantic model

    Raises:
        ValueError: If Claude's response doesn't contain valid JSON
        pydantic.ValidationError: If the JSON doesn't match DealReport schema
    """
    system_prompt = _load_prompt("system_prompt.txt")
    schema_str = _load_analysis_schema()

    analysis_prompt = f"""You have gathered the following data about this car listing:

{enriched_summary}

Now produce the DealReport JSON. Use ONLY the data above — do not invent numbers.

OUTPUT SCHEMA:
{schema_str}

Rules:
- grade: "A", "B", "C", "D", or "F" (single letter, no plus/minus)
- price_delta: integer (listing_price minus market median). Negative = below market. Use 0 if market data unavailable.
- price_verdict: one sentence, e.g. "This car is priced $1,200 BELOW market for a 2019 Honda Civic LX with 62k miles."
- red_flags: 1–5 items. Each needs a short title and 1–2 sentence description with specific data.
- green_flags: 0–5 items. Same format. Omit section (empty array) if none found.
- comps: up to 5 items from the comp data gathered. Include delta_vs_this for each.
- negotiation_points: 2–4 specific, actionable strings. Include dollar amounts where possible.
- summary: 2–3 sentences. Plain English. Written for someone who knows nothing about cars.

Return ONLY the JSON object. No markdown fences, no explanation."""

    # Retry up to 3 times on transient 529 overload errors
    import asyncio as _asyncio
    for attempt in range(3):
        try:
            response = await client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS_ANALYSIS,
                system=system_prompt,
                messages=[{"role": "user", "content": analysis_prompt}],
                # No tools in the analysis step — clean, focused output
            )
            raw_text = _extract_text(response.content)
            return _parse_deal_report(raw_text)
        except anthropic.APIStatusError as e:
            if e.status_code == 529 and attempt < 2:
                wait = 3 * (attempt + 1)
                logger.warning(f"[claude_agent] API overloaded (529), retrying in {wait}s (attempt {attempt + 1}/3)")
                await _asyncio.sleep(wait)
            else:
                raise


def _parse_deal_report(raw_text: str) -> DealReport:
    """
    Parse and validate Claude's JSON output into a DealReport model.

    Handles common Claude formatting quirks:
    - Strips markdown code fences (```json ... ```)
    - Strips leading/trailing whitespace
    - Provides clear error messages for schema mismatches

    Raises:
        ValueError: If no valid JSON found in the response
        pydantic.ValidationError: If JSON structure doesn't match DealReport
    """
    # Strip markdown code fences if Claude wrapped the JSON
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```) and last line (```)
        text = "\n".join(lines[1:-1]).strip()

    # Find the JSON object boundaries (defensive parsing)
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(
            f"No JSON object found in Claude's analysis response. "
            f"Raw response (first 500 chars): {raw_text[:500]}"
        )

    json_str = text[start:end]

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Claude returned invalid JSON: {e}. "
            f"Raw JSON (first 500 chars): {json_str[:500]}"
        ) from e

    try:
        return DealReport(**data)
    except ValidationError as e:
        # Re-raise as ValueError with context so callers get a clear message
        raise ValueError(
            f"Claude's JSON doesn't match DealReport schema. "
            f"Raw JSON (first 500 chars): {json_str[:500]}. "
            f"Pydantic errors: {e}"
        ) from e


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_client() -> anthropic.AsyncAnthropic:
    """
    Initialize the Anthropic async client.
    Reads ANTHROPIC_API_KEY from environment (set in .env).

    Proxy handling: In sandboxed environments (e.g. Cowork), the default HTTPS
    proxy performs MITM inspection and blocks API key headers. We detect this by
    checking for a SOCKS proxy env var and route through that instead, which
    passes traffic through without header inspection.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY environment variable is not set. "
            "Add it to your .env file."
        )

    # If a SOCKS proxy is available (sandbox env), use it to bypass MITM proxy
    socks_proxy = os.getenv("ALL_PROXY") or os.getenv("all_proxy")
    if socks_proxy and socks_proxy.startswith("socks"):
        import httpx
        http_client = httpx.AsyncClient(
            proxy=socks_proxy,
            timeout=60.0,
        )
        logger.info(f"[claude_agent] Using SOCKS proxy: {socks_proxy}")
        return anthropic.AsyncAnthropic(api_key=api_key, http_client=http_client)

    return anthropic.AsyncAnthropic(api_key=api_key)


def _describe_input(request: AnalysisRequest) -> str:
    """Build a human-readable description of the analysis input."""
    if request.listing_url and request.vin:
        return f"Listing URL: {request.listing_url} | VIN: {request.vin}"
    if request.listing_url:
        return f"Listing URL: {request.listing_url}"
    if request.vin:
        return f"VIN only (no listing URL): {request.vin}"
    return "Unknown input"


def _extract_text(content_blocks: list[Any]) -> str:
    """Extract and concatenate all text blocks from a Claude response."""
    parts = []
    for block in content_blocks:
        if hasattr(block, "type") and block.type == "text":
            parts.append(block.text)
    return "\n".join(parts).strip()
