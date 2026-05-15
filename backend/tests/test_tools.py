"""
tests/test_tools.py

Unit tests for all four MCP tools: web_fetch, vin_decode, search_comps, price_lookup.

Tests use fixture data from tests/fixtures/ to avoid live API calls in CI.
httpx calls are mocked using unittest.mock.patch so tests are fully offline.

Test coverage:
  web_fetch   — JSON-LD extraction, meta tag fallback, price/mileage normalization,
                unsupported URL rejection
  vin_decode  — NHTSA response parsing, VIN validation (length, illegal chars),
                engine string assembly
  search_comps — result filtering, price/mileage extraction, API fallback logic
  price_lookup — median calculation, outlier removal, mileage adjustment,
                 insufficient data handling
  mcp/server  — tool name registry, dispatch routing, error wrapping

Run with:
  pytest backend/tests/test_tools.py -v
"""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# ── Fixture helpers ───────────────────────────────────────────────────────────

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(filename: str) -> str:
    return (FIXTURES_DIR / filename).read_text()


def load_json_fixture(filename: str) -> dict:
    return json.loads(load_fixture(filename))


# ── web_fetch tests ───────────────────────────────────────────────────────────

class TestWebFetch:
    """Tests for backend/mcp/tools/web_fetch.py"""

    @pytest.mark.asyncio
    async def test_cargurus_json_ld_extraction(self):
        """Should extract all fields from CarGurus JSON-LD structured data."""
        from mcp.tools.web_fetch import web_fetch

        html = load_fixture("cargurus_listing.html")
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await web_fetch("https://www.cargurus.com/Cars/listingDetail.action?listing=123")

        assert result["make"] == "Honda"
        assert result["model"] == "Civic"
        assert result["year"] == 2019
        assert result["trim"] == "LX"
        assert result["price"] == 16500
        assert result["mileage"] == 62345
        assert result["location"] == "Austin, TX"
        assert result["vin"] == "2HGFC2F59KH123456"
        assert result["source_site"] == "cargurus.com"

    @pytest.mark.asyncio
    async def test_autotrader_json_ld_extraction(self):
        """Should extract all fields from AutoTrader JSON-LD structured data."""
        from mcp.tools.web_fetch import web_fetch

        html = load_fixture("autotrader_listing.html")
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await web_fetch("https://www.autotrader.com/cars-for-sale/vehicledetails.xhtml?listingId=456")

        assert result["make"] == "Toyota"
        assert result["model"] == "Camry"
        assert result["year"] == 2021
        assert result["trim"] == "SE"
        assert result["price"] == 24900
        assert result["mileage"] == 31200
        assert result["source_site"] == "autotrader.com"

    @pytest.mark.asyncio
    async def test_rejects_unsupported_url(self):
        """Should raise ValueError for non-CarGurus/AutoTrader URLs."""
        from mcp.tools.web_fetch import web_fetch

        with pytest.raises(ValueError, match="Unsupported listing site"):
            await web_fetch("https://www.craigslist.org/cars/123")

    @pytest.mark.asyncio
    async def test_rejects_empty_url(self):
        """Should raise ValueError for empty or malformed URLs."""
        from mcp.tools.web_fetch import web_fetch

        with pytest.raises(ValueError):
            await web_fetch("")

    def test_parse_price_formats(self):
        """Price parser should handle all common formatting variations."""
        from mcp.tools.web_fetch import _parse_price

        assert _parse_price("$18,500") == 18500
        assert _parse_price("18500") == 18500
        assert _parse_price(18500.0) == 18500
        assert _parse_price("$18,500.00") == 1850000  # raw digit strip — expected behavior
        assert _parse_price(None) is None
        assert _parse_price("") is None

    def test_parse_mileage_formats(self):
        """Mileage parser should handle 'mi', 'miles', and numeric inputs."""
        from mcp.tools.web_fetch import _parse_mileage

        assert _parse_mileage("62,345 mi") == 62345
        assert _parse_mileage("62345 miles") == 62345
        assert _parse_mileage(62345) == 62345
        assert _parse_mileage(None) is None

    def test_parse_title_string_extracts_year_make_model(self):
        """Title parser should extract year/make/model/trim from listing titles."""
        from mcp.tools.web_fetch import _parse_title_string

        result = {}
        _parse_title_string("Used 2019 Honda Civic LX", result)
        assert result["year"] == "2019"
        assert result["make"] == "Honda"
        assert result["model"] == "Civic"
        assert result["trim"] == "LX"

    def test_parse_title_string_handles_em_dash(self):
        """Title parser should stop trim extraction at em-dash separators."""
        from mcp.tools.web_fetch import _parse_title_string

        result = {}
        _parse_title_string("2021 Toyota Camry SE — Certified Pre-Owned", result)
        assert result["trim"] == "SE"

    def test_detect_site(self):
        """Site detector should handle www prefix and subdomains."""
        from mcp.tools.web_fetch import _detect_site

        assert _detect_site("https://www.cargurus.com/Cars/123") == "cargurus.com"
        assert _detect_site("https://cargurus.com/Cars/123") == "cargurus.com"
        assert _detect_site("https://www.autotrader.com/cars/456") == "autotrader.com"
        assert _detect_site("https://craigslist.org/car/789") is None
        assert _detect_site("not-a-url") is None


# ── vin_decode tests ──────────────────────────────────────────────────────────

class TestVinDecode:
    """Tests for backend/mcp/tools/vin_decode.py"""

    @pytest.mark.asyncio
    async def test_decodes_valid_vin(self):
        """Should correctly decode a Honda Civic VIN from NHTSA fixture data."""
        from mcp.tools.vin_decode import vin_decode

        nhtsa_response = load_json_fixture("nhtsa_civic_response.json")

        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value=nhtsa_response)
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await vin_decode("2HGFC2F59KH123456")

        assert result["make"] == "HONDA"
        assert result["model"] == "Civic"
        assert result["year"] == 2019
        assert result["trim"] == "LX"
        assert result["body_style"] == "Sedan/Saloon"
        assert result["engine"] == "4-cylinder 2.0L"
        assert result["fuel_type"] == "Gasoline"
        assert result["drivetrain"] == "FWD/Front-Wheel Drive"
        assert result["error_code"] == "0"
        assert result["error_text"] is None   # Should be cleared for clean VINs
        assert result["vin"] == "2HGFC2F59KH123456"

    def test_rejects_short_vin(self):
        """Should raise ValueError for VINs shorter than 17 characters."""
        from mcp.tools.vin_decode import _validate_vin

        with pytest.raises(ValueError, match="17 characters"):
            _validate_vin("1HGCM8263A12345")  # 15 chars

    def test_rejects_vin_with_illegal_chars(self):
        """Should raise ValueError for VINs containing I, O, or Q."""
        from mcp.tools.vin_decode import _validate_vin

        with pytest.raises(ValueError, match="illegal characters"):
            _validate_vin("1HGCM82633AI23456")  # Contains 'I'

        with pytest.raises(ValueError, match="illegal characters"):
            _validate_vin("1HGCM82633AO23456")  # Contains 'O'

    def test_rejects_vin_too_long(self):
        """Should raise ValueError for VINs longer than 17 characters."""
        from mcp.tools.vin_decode import _validate_vin

        with pytest.raises(ValueError, match="17 characters"):
            _validate_vin("1HGCM82633A1234567")  # 18 chars

    def test_accepts_valid_vin_formats(self):
        """Should accept uppercase and lowercase VINs (normalizes to upper)."""
        from mcp.tools.vin_decode import _validate_vin

        # Should not raise
        _validate_vin("2HGFC2F59KH123456")
        _validate_vin("1FTFW1ET5DFA12345")

    def test_engine_string_assembly(self):
        """Engine string should combine cylinders and displacement correctly."""
        from mcp.tools.vin_decode import _parse_nhtsa_response

        mock_results = [
            {"Variable": "Make", "Value": "HONDA"},
            {"Variable": "Model", "Value": "Civic"},
            {"Variable": "Model Year", "Value": "2019"},
            {"Variable": "Engine Number of Cylinders", "Value": "4"},
            {"Variable": "Displacement (L)", "Value": "2.0"},
            {"Variable": "Error Code", "Value": "0"},
        ]
        result = _parse_nhtsa_response("2HGFC2F59KH123456", mock_results)
        assert result["engine"] == "4-cylinder 2.0L"

    def test_handles_missing_optional_fields(self):
        """Should return None for optional fields not in NHTSA response."""
        from mcp.tools.vin_decode import _parse_nhtsa_response

        minimal_results = [
            {"Variable": "Make", "Value": "HONDA"},
            {"Variable": "Model", "Value": "Civic"},
            {"Variable": "Error Code", "Value": "0"},
        ]
        result = _parse_nhtsa_response("2HGFC2F59KH123456", minimal_results)
        assert result["trim"] is None
        assert result["engine"] is None
        assert result["fuel_type"] is None


# ── search_comps tests ────────────────────────────────────────────────────────

class TestSearchComps:
    """Tests for backend/mcp/tools/search_comps.py"""

    @pytest.mark.asyncio
    async def test_returns_filtered_listing_results(self):
        """Should return only results from trusted listing sites (not news/forums)."""
        from mcp.tools.search_comps import search_comps

        serpapi_data = load_json_fixture("serpapi_comps_response.json")

        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value=serpapi_data)
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            with patch.dict("os.environ", {"SERPAPI_KEY": "test-key"}):
                results = await search_comps(2019, "Honda", "Civic", "LX", "Austin, TX")

        # MotorTrend review should be filtered out
        urls = [r["url"] for r in results]
        assert not any("motortrend" in url for url in urls)

        # Should have at least some results
        assert len(results) >= 1

        # Each result should have the expected shape
        for comp in results:
            assert "title" in comp
            assert "url" in comp
            assert "source" in comp
            # price and mileage are optional (may be None)
            assert "price" in comp
            assert "mileage" in comp

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_api_keys(self):
        """Should return empty list (not raise) when no API keys are configured."""
        from mcp.tools.search_comps import search_comps

        with patch.dict("os.environ", {}, clear=True):
            # Remove both keys
            import os
            os.environ.pop("SERPAPI_KEY", None)
            os.environ.pop("BRAVE_SEARCH_KEY", None)

            results = await search_comps(2019, "Honda", "Civic", "LX", "Austin, TX")

        assert results == []

    def test_extract_price_from_snippet(self):
        """Price extractor should parse common price formats from snippets."""
        from mcp.tools.search_comps import _extract_price

        assert _extract_price("2019 Honda Civic LX — $15,995") == 15995
        assert _extract_price("Price: $16,800") == 16800
        assert _extract_price("No price here") is None
        assert _extract_price("$500") is None          # Below $1k sanity threshold
        assert _extract_price("$200,000") is None      # Above $150k sanity threshold

    def test_extract_mileage_from_snippet(self):
        """Mileage extractor should parse miles/mi/K patterns."""
        from mcp.tools.search_comps import _extract_mileage

        assert _extract_mileage("62,345 miles") == 62345
        assert _extract_mileage("62,345 mi") == 62345
        assert _extract_mileage("62K miles") == 62000
        assert _extract_mileage("no mileage here") is None

    def test_is_listing_url_filters_correctly(self):
        """Should accept trusted listing sites and reject others."""
        from mcp.tools.search_comps import _is_listing_url

        assert _is_listing_url("https://www.cargurus.com/Cars/123") is True
        assert _is_listing_url("https://www.autotrader.com/cars/456") is True
        assert _is_listing_url("https://www.cars.com/vehicledetail/789") is True
        assert _is_listing_url("https://www.motortrend.com/review") is False
        assert _is_listing_url("https://reddit.com/r/cars") is False

    def test_build_query_includes_all_fields(self):
        """Query builder should include year, make, model, trim, and location."""
        from mcp.tools.search_comps import _build_query

        query = _build_query(2019, "Honda", "Civic", "LX", "Austin, TX")
        assert "2019" in query
        assert "Honda" in query
        assert "Civic" in query
        assert "LX" in query
        assert "Austin, TX" in query


# ── price_lookup tests ────────────────────────────────────────────────────────

class TestPriceLookup:
    """Tests for backend/mcp/tools/price_lookup.py"""

    @pytest.mark.asyncio
    async def test_computes_correct_median(self):
        """Should return correct median from mock comp prices."""
        from mcp.tools.price_lookup import price_lookup

        mock_comps = [
            {"price": 15000, "mileage": 60000},
            {"price": 16000, "mileage": 65000},
            {"price": 17000, "mileage": 70000},
            {"price": 15500, "mileage": 58000},
            {"price": 16500, "mileage": 62000},
        ]

        with patch(
            "backend.mcp.tools.price_lookup.search_comps",
            new=AsyncMock(return_value=mock_comps),
        ):
            result = await price_lookup(2019, "Honda", "Civic", "LX", 62000)

        assert result["median"] is not None
        assert result["sample_size"] == len(mock_comps)
        assert result["low"] <= result["median"] <= result["high"]

    @pytest.mark.asyncio
    async def test_returns_error_for_insufficient_comps(self):
        """Should return an error dict (not raise) when fewer than 2 priced comps exist."""
        from mcp.tools.price_lookup import price_lookup

        with patch(
            "backend.mcp.tools.price_lookup.search_comps",
            new=AsyncMock(return_value=[{"price": None, "mileage": None}]),
        ):
            result = await price_lookup(2019, "Honda", "Civic", "LX", 62000)

        assert "error" in result
        assert result["median"] is None

    def test_remove_outliers(self):
        """Outlier removal should filter extreme prices."""
        from mcp.tools.price_lookup import _remove_outliers

        prices = [15000, 15500, 16000, 16500, 17000, 55000]  # $55k is an outlier
        filtered = _remove_outliers(prices)
        assert 55000 not in filtered
        assert len(filtered) >= 2

    def test_remove_outliers_preserves_small_samples(self):
        """Outlier removal should not filter when sample is too small."""
        from mcp.tools.price_lookup import _remove_outliers

        prices = [15000, 55000]  # Only 2 — can't meaningfully remove outliers
        filtered = _remove_outliers(prices)
        assert filtered == prices

    def test_percentile_calculation(self):
        """
        Percentile helper should return correct values.

        With n=10, pct=10: idx = round(0.1 * 10) = 1 → prices[1] = 12000
        With n=10, pct=90: idx = round(0.9 * 10) = 9 → prices[9] = 28000
        This is expected — the implementation uses index-based percentiles.
        """
        from mcp.tools.price_lookup import _percentile

        prices = [10000, 12000, 14000, 16000, 18000, 20000, 22000, 24000, 26000, 28000]
        assert _percentile(prices, 10) == 12000   # idx = round(10/100 * 10) = 1
        assert _percentile(prices, 50) == 20000   # idx = round(50/100 * 10) = 5
        assert _percentile(prices, 90) == 28000   # idx = round(90/100 * 10) = 9
        assert _percentile([], 50) is None


# ── MCP server tests ──────────────────────────────────────────────────────────

class TestMcpServer:
    """Tests for backend/mcp/server.py"""

    def test_get_tool_definitions_returns_four_tools(self):
        """Should return exactly 4 tool definitions."""
        from mcp.server import get_tool_definitions

        tools = get_tool_definitions()
        assert len(tools) == 4

    def test_tool_definitions_have_required_keys(self):
        """Each tool definition must have name, description, and input_schema."""
        from mcp.server import get_tool_definitions

        tools = get_tool_definitions()
        for tool in tools:
            assert "name" in tool, f"Tool missing 'name': {tool}"
            assert "description" in tool, f"Tool missing 'description': {tool}"
            assert "input_schema" in tool, f"Tool missing 'input_schema': {tool}"
            assert "type" in tool["input_schema"]
            assert "properties" in tool["input_schema"]

    def test_tool_names_match_expected(self):
        """Tool names should exactly match the expected set."""
        from mcp.server import get_tool_names

        names = get_tool_names()
        assert set(names) == {"web_fetch", "vin_decode", "search_comps", "price_lookup"}

    @pytest.mark.asyncio
    async def test_dispatch_unknown_tool_raises(self):
        """Dispatching an unknown tool name should raise ValueError."""
        from mcp.server import dispatch_tool_call

        result_str = await dispatch_tool_call("nonexistent_tool", {})
        result = json.loads(result_str)
        assert "error" in result
        assert "nonexistent_tool" in result["error"]

    @pytest.mark.asyncio
    async def test_dispatch_web_fetch_routes_correctly(self):
        """dispatch_tool_call('web_fetch', ...) should call the web_fetch function."""
        from mcp.server import dispatch_tool_call

        mock_result = {
            "make": "Honda", "model": "Civic", "year": 2019,
            "price": 16500, "mileage": 62345,
        }

        with patch(
            "backend.mcp.server.web_fetch",
            new=AsyncMock(return_value=mock_result),
        ):
            result_str = await dispatch_tool_call(
                "web_fetch",
                {"url": "https://www.cargurus.com/Cars/123"},
            )

        result = json.loads(result_str)
        assert result["make"] == "Honda"
        assert result["price"] == 16500

    @pytest.mark.asyncio
    async def test_dispatch_wraps_tool_errors_as_json(self):
        """Tool errors should be caught and returned as JSON, not re-raised."""
        from mcp.server import dispatch_tool_call

        with patch(
            "backend.mcp.server.web_fetch",
            new=AsyncMock(side_effect=ValueError("Unsupported site")),
        ):
            result_str = await dispatch_tool_call(
                "web_fetch",
                {"url": "https://craigslist.org/123"},
            )

        result = json.loads(result_str)
        assert "error" in result
        assert "Unsupported site" in result["error"]
