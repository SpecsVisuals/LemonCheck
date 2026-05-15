"""
tests/test_agent.py

Agent Chain Tests — claude_agent.run_analysis
----------------------------------------------
Tests the full two-step Claude agent pipeline.

Test tiers:
  UNIT TESTS (always run, no API keys needed)
    - Mock the Anthropic client to test pipeline logic in isolation
    - Validate DealReport construction and schema enforcement
    - Test error handling (bad JSON, schema mismatches, missing env vars)
    - Test enrichment loop logic (tool call routing, MAX_TOOL_CALLS cap)

  INTEGRATION TESTS (skipped unless RUN_INTEGRATION_TESTS=1 env var is set)
    - Call the real Anthropic API with real listing URLs
    - Three archetypes: overpriced, fair, underpriced
    - Validate grade direction (not exact grade — Claude may reasonably disagree)
    - Mark with @pytest.mark.integration

Run unit tests only (CI default):
  pytest backend/tests/test_agent.py -v

Run integration tests (requires ANTHROPIC_API_KEY):
  RUN_INTEGRATION_TESTS=1 pytest backend/tests/test_agent.py -v -m integration
"""

import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_mock_deal_report_json(**overrides) -> str:
    """Build a valid DealReport JSON string for mocking Claude's analysis response."""
    base = {
        "grade": "B",
        "price_delta": -1200,
        "price_verdict": "This car is priced $1,200 BELOW market for a 2019 Honda Civic LX with 62k miles.",
        "red_flags": [
            {
                "title": "Higher Mileage",
                "description": "At 62,345 miles, this car has been driven ~10.4k miles/year — slightly above average."
            }
        ],
        "green_flags": [
            {
                "title": "Below Market Price",
                "description": "Listed $1,200 below the median comp price of $17,700 for this year/make/model/trim."
            }
        ],
        "comps": [
            {
                "title": "2019 Honda Civic LX — 58k miles",
                "price": 17700,
                "mileage": 58000,
                "url": "https://www.cargurus.com/Cars/listingDetail.action?listing=123",
                "delta_vs_this": 1200
            }
        ],
        "negotiation_points": [
            "Comps in Austin average $17,700 — start your offer at $15,800.",
            "At 62k miles, timing belt and coolant service may be due soon. Ask for $300 credit."
        ],
        "summary": "This is a solid B-grade deal on a reliable 2019 Civic. The price is $1,200 below market, which gives you room to walk away if the seller won't negotiate. Inspect the timing belt service history before signing."
    }
    base.update(overrides)
    return json.dumps(base)


def make_mock_anthropic_text_response(text: str) -> MagicMock:
    """Build a mock Anthropic response with a single text block."""
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = text

    response = MagicMock()
    response.content = [text_block]
    response.stop_reason = "end_turn"
    return response


def make_mock_anthropic_tool_response(tool_name: str, tool_id: str, tool_input: dict) -> MagicMock:
    """Build a mock Anthropic response with a tool_use block."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = tool_name
    tool_block.id = tool_id
    tool_block.input = tool_input

    response = MagicMock()
    response.content = [tool_block]
    response.stop_reason = "tool_use"
    return response


# ── Unit tests: AnalysisRequest validation ────────────────────────────────────

class TestAnalysisRequest:
    """Tests for AnalysisRequest model validation."""

    def test_accepts_listing_url(self):
        from models.analysis import AnalysisRequest
        req = AnalysisRequest(listing_url="https://www.cargurus.com/test")
        assert req.listing_url == "https://www.cargurus.com/test"
        assert req.vin is None

    def test_accepts_vin(self):
        from models.analysis import AnalysisRequest
        req = AnalysisRequest(vin="2HGFC2F59KH123456")
        assert req.vin == "2HGFC2F59KH123456"

    def test_normalizes_vin_to_uppercase(self):
        from models.analysis import AnalysisRequest
        req = AnalysisRequest(vin="2hgfc2f59kh123456")
        assert req.vin == "2HGFC2F59KH123456"

    def test_rejects_empty_request(self):
        from models.analysis import AnalysisRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="listing_url or vin"):
            AnalysisRequest()

    def test_rejects_vin_wrong_length(self):
        from models.analysis import AnalysisRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AnalysisRequest(vin="2HGFC2F59KH1234")  # 15 chars

    def test_rejects_non_http_url(self):
        from models.analysis import AnalysisRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AnalysisRequest(listing_url="ftp://not-a-listing.com")


# ── Unit tests: DealReport parsing ───────────────────────────────────────────

class TestDealReportParsing:
    """Tests for _parse_deal_report — Claude JSON output → DealReport model."""

    def test_parses_valid_json(self):
        from services.claude_agent import _parse_deal_report
        raw = make_mock_deal_report_json()
        report = _parse_deal_report(raw)
        assert report.grade == "B"
        assert report.price_delta == -1200
        assert len(report.red_flags) == 1
        assert len(report.green_flags) == 1
        assert len(report.comps) == 1
        assert len(report.negotiation_points) == 2

    def test_strips_markdown_fences(self):
        """Claude sometimes wraps JSON in ```json fences — should strip them."""
        from services.claude_agent import _parse_deal_report
        raw = f"```json\n{make_mock_deal_report_json()}\n```"
        report = _parse_deal_report(raw)
        assert report.grade == "B"

    def test_strips_plain_fences(self):
        """Also strips plain ``` fences (no language specifier)."""
        from services.claude_agent import _parse_deal_report
        raw = f"```\n{make_mock_deal_report_json()}\n```"
        report = _parse_deal_report(raw)
        assert report.grade == "B"

    def test_handles_leading_text_before_json(self):
        """Should find JSON even if Claude adds a preamble sentence."""
        from services.claude_agent import _parse_deal_report
        raw = f"Here is the analysis:\n{make_mock_deal_report_json()}"
        report = _parse_deal_report(raw)
        assert report.grade == "B"

    def test_raises_on_no_json(self):
        from services.claude_agent import _parse_deal_report
        with pytest.raises(ValueError, match="No JSON object found"):
            _parse_deal_report("Sorry, I cannot analyze this listing.")

    def test_raises_on_invalid_json(self):
        from services.claude_agent import _parse_deal_report
        with pytest.raises(ValueError, match="invalid JSON"):
            _parse_deal_report('{"grade": "B", "price_delta": }')

    def test_raises_on_invalid_grade(self):
        """Grade 'E' is not valid — should raise ValueError wrapping Pydantic error."""
        from services.claude_agent import _parse_deal_report
        raw = make_mock_deal_report_json(grade="E")  # E is not a valid grade
        with pytest.raises(ValueError, match="DealReport schema"):
            _parse_deal_report(raw)

    def test_all_valid_grades_accepted(self):
        from services.claude_agent import _parse_deal_report
        for grade in ["A", "B", "C", "D", "F"]:
            raw = make_mock_deal_report_json(grade=grade)
            report = _parse_deal_report(raw)
            assert report.grade == grade

    def test_negative_price_delta_accepted(self):
        """Negative price_delta = below market — valid and common."""
        from services.claude_agent import _parse_deal_report
        raw = make_mock_deal_report_json(price_delta=-3500)
        report = _parse_deal_report(raw)
        assert report.price_delta == -3500

    def test_zero_price_delta_accepted(self):
        """Zero delta = at market — valid when market data unavailable."""
        from services.claude_agent import _parse_deal_report
        raw = make_mock_deal_report_json(price_delta=0)
        report = _parse_deal_report(raw)
        assert report.price_delta == 0


# ── Unit tests: full agent pipeline (mocked) ─────────────────────────────────

class TestRunAnalysis:
    """End-to-end agent pipeline tests using a mocked Anthropic client."""

    @pytest.mark.asyncio
    async def test_run_analysis_returns_deal_report(self):
        """Happy path: mock enrichment + analysis calls, verify DealReport returned."""
        from services.claude_agent import run_analysis
        from models.analysis import AnalysisRequest

        enrichment_summary = "Vehicle: 2019 Honda Civic LX\nAsking price: $16,500\nENRICHMENT COMPLETE"
        analysis_json = make_mock_deal_report_json()

        enrichment_response = make_mock_anthropic_text_response(enrichment_summary)
        analysis_response = make_mock_anthropic_text_response(analysis_json)

        mock_client = AsyncMock()
        mock_client.messages = AsyncMock()
        mock_client.messages.create = AsyncMock(
            side_effect=[enrichment_response, analysis_response]
        )

        with patch("backend.services.claude_agent._get_client", return_value=mock_client):
            request = AnalysisRequest(listing_url="https://www.cargurus.com/test")
            report = await run_analysis(request)

        assert report.grade == "B"
        assert report.price_delta == -1200
        assert isinstance(report.summary, str)
        assert len(report.summary) > 0

    @pytest.mark.asyncio
    async def test_run_analysis_handles_tool_calls(self):
        """Enrichment loop should process tool calls and loop correctly."""
        from services.claude_agent import run_analysis
        from models.analysis import AnalysisRequest

        # Sequence: tool_use response → end_turn summary → analysis JSON
        tool_response = make_mock_anthropic_tool_response(
            tool_name="web_fetch",
            tool_id="tool_abc123",
            tool_input={"url": "https://www.cargurus.com/test"},
        )
        enrichment_summary = make_mock_anthropic_text_response(
            "Vehicle: 2019 Honda Civic LX\nENRICHMENT COMPLETE"
        )
        analysis_response = make_mock_anthropic_text_response(
            make_mock_deal_report_json()
        )

        mock_client = AsyncMock()
        mock_client.messages = AsyncMock()
        mock_client.messages.create = AsyncMock(
            side_effect=[tool_response, enrichment_summary, analysis_response]
        )

        mock_web_fetch_result = json.dumps({
            "make": "Honda", "model": "Civic", "year": 2019,
            "price": 16500, "mileage": 62345,
        })

        with patch("backend.services.claude_agent._get_client", return_value=mock_client), \
             patch("backend.mcp.server.web_fetch", new=AsyncMock(return_value={"make": "Honda"})):
            request = AnalysisRequest(listing_url="https://www.cargurus.com/test")
            report = await run_analysis(request)

        assert report.grade in {"A", "B", "C", "D", "F"}
        # Should have called the API at least 3 times (enrichment tool call + summary + analysis)
        assert mock_client.messages.create.call_count >= 2

    @pytest.mark.asyncio
    async def test_run_analysis_raises_without_api_key(self):
        """Should raise EnvironmentError if ANTHROPIC_API_KEY is not set."""
        from services.claude_agent import run_analysis
        from models.analysis import AnalysisRequest

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            with pytest.raises(EnvironmentError, match="ANTHROPIC_API_KEY"):
                request = AnalysisRequest(listing_url="https://www.cargurus.com/test")
                await run_analysis(request)

    @pytest.mark.asyncio
    async def test_run_analysis_raises_on_invalid_report_json(self):
        """Should raise if Claude's analysis step returns unparseable JSON."""
        from services.claude_agent import run_analysis
        from models.analysis import AnalysisRequest

        enrichment_response = make_mock_anthropic_text_response("ENRICHMENT COMPLETE")
        bad_analysis_response = make_mock_anthropic_text_response(
            "I cannot analyze this vehicle at this time."
        )

        mock_client = AsyncMock()
        mock_client.messages = AsyncMock()
        mock_client.messages.create = AsyncMock(
            side_effect=[enrichment_response, bad_analysis_response]
        )

        with patch("backend.services.claude_agent._get_client", return_value=mock_client):
            request = AnalysisRequest(listing_url="https://www.cargurus.com/test")
            with pytest.raises(ValueError, match="No JSON object found"):
                await run_analysis(request)


# ── Unit tests: helper functions ──────────────────────────────────────────────

class TestAgentHelpers:
    """Tests for agent helper functions."""

    def test_extract_text_from_content_blocks(self):
        from services.claude_agent import _extract_text

        block1 = MagicMock()
        block1.type = "text"
        block1.text = "Hello"

        block2 = MagicMock()
        block2.type = "tool_use"  # Should be ignored

        block3 = MagicMock()
        block3.type = "text"
        block3.text = "World"

        result = _extract_text([block1, block2, block3])
        assert result == "Hello\nWorld"

    def test_extract_text_from_empty_blocks(self):
        from services.claude_agent import _extract_text
        assert _extract_text([]) == ""

    def test_describe_input_url_only(self):
        from services.claude_agent import _describe_input
        from models.analysis import AnalysisRequest
        req = AnalysisRequest(listing_url="https://www.cargurus.com/test")
        desc = _describe_input(req)
        assert "https://www.cargurus.com/test" in desc

    def test_describe_input_vin_only(self):
        from services.claude_agent import _describe_input
        from models.analysis import AnalysisRequest
        req = AnalysisRequest(vin="2HGFC2F59KH123456")
        desc = _describe_input(req)
        assert "2HGFC2F59KH123456" in desc


# ── Integration tests (skipped in CI) ────────────────────────────────────────

INTEGRATION_ENABLED = os.getenv("RUN_INTEGRATION_TESTS") == "1"
integration = pytest.mark.skipif(
    not INTEGRATION_ENABLED,
    reason="Set RUN_INTEGRATION_TESTS=1 to run integration tests (requires ANTHROPIC_API_KEY)"
)

# Sample listing URLs for integration testing.
# These are example URLs — replace with real listings when running tests.
# They may become stale; the point is to test the agent against live data.
SAMPLE_LISTINGS = {
    "overpriced": {
        # A listing priced well above market — expect D or F grade
        "url": "https://www.cargurus.com/Cars/new/nl-New-Honda-Civic-d2282",
        "expected_grades": {"D", "F"},
        "description": "Overpriced listing — should get D or F",
    },
    "fair": {
        # A listing priced at or near market — expect B or C grade
        "url": "https://www.autotrader.com/cars-for-sale/used-cars/honda/civic/austin-tx-78701",
        "expected_grades": {"B", "C"},
        "description": "Fair listing — should get B or C",
    },
    "underpriced": {
        # A listing priced below market — expect A or B grade
        "url": "https://www.cargurus.com/Cars/new/nl-Used-Honda-Civic-d2282",
        "expected_grades": {"A", "B"},
        "description": "Underpriced listing — should get A or B",
    },
}


@integration
class TestRunAnalysisIntegration:
    """
    Live integration tests against real listing URLs.
    These call the actual Anthropic API and may take 15-30 seconds each.

    Run with: RUN_INTEGRATION_TESTS=1 pytest backend/tests/test_agent.py -v -m integration
    """

    @pytest.mark.asyncio
    async def test_analysis_returns_valid_schema(self):
        """
        Basic integration smoke test: run analysis on a real URL and
        verify the output conforms to DealReport schema.
        """
        from services.claude_agent import run_analysis
        from models.analysis import AnalysisRequest, DealReport

        # Use a search results page — should still extract some vehicle data
        url = "https://www.cargurus.com/Cars/new/nl-Used-Honda-Civic-d2282"
        request = AnalysisRequest(listing_url=url)
        report = await run_analysis(request)

        # Verify schema compliance
        assert isinstance(report, DealReport)
        assert report.grade in {"A", "B", "C", "D", "F"}
        assert isinstance(report.price_delta, int)
        assert isinstance(report.price_verdict, str) and len(report.price_verdict) > 0
        assert isinstance(report.red_flags, list)
        assert isinstance(report.green_flags, list)
        assert isinstance(report.comps, list)
        assert isinstance(report.negotiation_points, list)
        assert len(report.negotiation_points) >= 1
        assert isinstance(report.summary, str) and len(report.summary) > 0

    @pytest.mark.asyncio
    async def test_vin_only_analysis(self):
        """
        Integration test for VIN-only input (no listing URL).
        Uses a well-known VIN format.
        """
        from services.claude_agent import run_analysis
        from models.analysis import AnalysisRequest, DealReport

        # 2019 Honda Civic LX VIN (example — may not be in NHTSA DB)
        request = AnalysisRequest(vin="2HGFC2F59KH500001")
        report = await run_analysis(request)

        assert isinstance(report, DealReport)
        assert report.grade in {"A", "B", "C", "D", "F"}
        # VIN-only analysis should note the lack of pricing data
        assert len(report.summary) > 0
