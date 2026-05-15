"""
tests/test_api.py

FastAPI Endpoint Tests
-----------------------
Tests for the three main API endpoints using FastAPI's TestClient.
All external dependencies (Claude, Supabase) are mocked so tests run
without any API keys or network access.

Test coverage:
  GET  /health           → 200
  GET  /demo             → 200 with valid DealReport shape
  POST /analyze          → 401 with no auth token
  POST /analyze          → 401 with invalid token
  POST /analyze          → 200 with valid auth + under limit
  POST /analyze          → 402 when usage limit exceeded
  POST /analyze          → 422 when agent returns invalid JSON

Why mock Supabase auth instead of testing real JWTs?
  Testing real JWT flows requires running a Supabase instance.
  Instead, we mock get_current_user() to return a fake user_id —
  this lets us test the router logic without an auth service dependency.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

# ── Fixtures ──────────────────────────────────────────────────────────────────

FAKE_USER_ID = "user-123-abc"

FAKE_REPORT = {
    "grade": "B",
    "price_delta": -500,
    "price_verdict": "This car is $500 below market.",
    "summary": "A solid deal. Priced slightly below market with no major red flags.",
    "red_flags": [
        {"title": "No Service Records", "description": "Seller couldn't provide maintenance history."}
    ],
    "green_flags": [
        {"title": "Below Market Price", "description": "Listed $500 under the regional median."}
    ],
    "comps": [
        {"title": "2019 Civic LX — 60k mi", "price": 18500, "mileage": 60000, "url": "https://cargurus.com", "delta_vs_this": 500}
    ],
    "negotiation_points": [
        "Ask for $300 off citing the missing service records.",
        "Comps average $18,500 — open at $17,800.",
    ],
}


@pytest.fixture
def client():
    """TestClient with Supabase env vars mocked so the app initializes."""
    with patch.dict("os.environ", {
        "ANTHROPIC_API_KEY": "sk-ant-test",
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_ANON_KEY": "test-anon-key",
        "SUPABASE_SERVICE_ROLE_KEY": "test-service-key",
    }):
        from backend.main import app
        return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def authed_client(client):
    """TestClient with get_current_user mocked to return FAKE_USER_ID."""
    from backend.routers.auth import get_current_user
    from backend.main import app

    app.dependency_overrides[get_current_user] = lambda: FAKE_USER_ID
    yield client
    app.dependency_overrides.clear()


# ── Health check ──────────────────────────────────────────────────────────────

class TestHealthCheck:
    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


# ── GET /demo ─────────────────────────────────────────────────────────────────

class TestDemoEndpoint:
    def test_demo_returns_200_with_fallback(self, client):
        """When demo_cache.json doesn't exist, should return hardcoded fallback."""
        with patch("backend.routers.demo.DEMO_CACHE_PATH", Path("/nonexistent/path.json")):
            response = client.get("/demo")
        assert response.status_code == 200
        body = response.json()
        assert "grade" in body
        assert "price_delta" in body
        assert "red_flags" in body
        assert "negotiation_points" in body

    def test_demo_returns_200_from_cache(self, client, tmp_path):
        """When demo_cache.json exists, should return its contents."""
        cache_file = tmp_path / "demo_cache.json"
        cache_file.write_text(json.dumps(FAKE_REPORT))

        with patch("backend.routers.demo.DEMO_CACHE_PATH", cache_file):
            response = client.get("/demo")

        assert response.status_code == 200
        body = response.json()
        assert body["grade"] == "B"
        assert body["price_delta"] == -500

    def test_demo_no_auth_required(self, client):
        """Demo endpoint should work without any Authorization header."""
        with patch("backend.routers.demo.DEMO_CACHE_PATH", Path("/nonexistent/path.json")):
            response = client.get("/demo")  # No auth header
        assert response.status_code == 200


# ── POST /analyze — Auth ──────────────────────────────────────────────────────

class TestAnalyzeAuth:
    def test_analyze_without_token_returns_401(self, client):
        """POST /analyze with no auth header → 401."""
        response = client.post(
            "/analyze",
            json={"listing_url": "https://www.cargurus.com/Cars/test", "vin": None},
        )
        assert response.status_code == 401

    def test_analyze_with_invalid_token_returns_401(self, client):
        """POST /analyze with a bad token → 401."""
        with (
            patch.dict("os.environ", {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_ANON_KEY": "test-key"}),
            patch("backend.routers.auth._get_anon_client") as mock_client,
        ):
            mock_supabase = MagicMock()
            mock_supabase.auth.get_user.side_effect = Exception("Invalid JWT")
            mock_client.return_value = mock_supabase

            response = client.post(
                "/analyze",
                headers={"Authorization": "Bearer not-a-real-token"},
                json={"listing_url": "https://www.cargurus.com/Cars/test", "vin": None},
            )
        assert response.status_code == 401


# ── POST /analyze — Usage gate ────────────────────────────────────────────────

class TestAnalyzeUsageGate:
    def test_analyze_over_limit_returns_402(self, authed_client):
        """When user has hit the monthly limit → 402 Payment Required."""
        with patch("backend.routers.analysis.get_usage_count", new=AsyncMock(return_value=5)):
            response = authed_client.post(
                "/analyze",
                json={"listing_url": "https://www.cargurus.com/Cars/test", "vin": None},
            )
        assert response.status_code == 402
        body = response.json()
        assert body["detail"]["error"] == "usage_limit_exceeded"
        assert body["detail"]["limit"] == 5

    def test_analyze_under_limit_calls_agent(self, authed_client):
        """When user is under limit, should call run_analysis and return report."""
        with (
            patch("backend.routers.analysis.get_usage_count", new=AsyncMock(return_value=2)),
            patch("backend.routers.analysis.run_analysis", new=AsyncMock(return_value=MagicMock(**FAKE_REPORT, model_dump=lambda: FAKE_REPORT))),
            patch("backend.routers.analysis.increment_usage", new=AsyncMock(return_value=3)),
            patch("backend.routers.analysis.save_analysis", new=AsyncMock(return_value="uuid-123")),
        ):
            from backend.models.analysis import DealReport
            mock_report = DealReport(**FAKE_REPORT)

            with patch("backend.routers.analysis.run_analysis", new=AsyncMock(return_value=mock_report)):
                response = authed_client.post(
                    "/analyze",
                    json={"listing_url": "https://www.cargurus.com/Cars/test", "vin": None},
                )

        assert response.status_code == 200
        body = response.json()
        assert body["grade"] == "B"
        assert body["price_delta"] == -500

    def test_analyze_at_exactly_zero_usage_is_allowed(self, authed_client):
        """A user with 0 analyses this month should be allowed through."""
        from backend.models.analysis import DealReport
        mock_report = DealReport(**FAKE_REPORT)

        with (
            patch("backend.routers.analysis.get_usage_count", new=AsyncMock(return_value=0)),
            patch("backend.routers.analysis.run_analysis", new=AsyncMock(return_value=mock_report)),
            patch("backend.routers.analysis.increment_usage", new=AsyncMock(return_value=1)),
            patch("backend.routers.analysis.save_analysis", new=AsyncMock(return_value="uuid-abc")),
        ):
            response = authed_client.post(
                "/analyze",
                json={"listing_url": "https://www.cargurus.com/Cars/test", "vin": None},
            )
        assert response.status_code == 200


# ── POST /analyze — Agent error handling ─────────────────────────────────────

class TestAnalyzeErrorHandling:
    def test_analyze_agent_value_error_returns_422(self, authed_client):
        """When agent raises ValueError (bad JSON from Claude) → 422."""
        with (
            patch("backend.routers.analysis.get_usage_count", new=AsyncMock(return_value=1)),
            patch("backend.routers.analysis.run_analysis", new=AsyncMock(side_effect=ValueError("No JSON found"))),
        ):
            response = authed_client.post(
                "/analyze",
                json={"listing_url": "https://www.cargurus.com/Cars/test", "vin": None},
            )
        assert response.status_code == 422
        assert response.json()["detail"]["error"] == "analysis_parse_error"

    def test_analyze_agent_exception_returns_503(self, authed_client):
        """When agent raises a generic exception (API down) → 503."""
        with (
            patch("backend.routers.analysis.get_usage_count", new=AsyncMock(return_value=1)),
            patch("backend.routers.analysis.run_analysis", new=AsyncMock(side_effect=Exception("API overloaded"))),
        ):
            response = authed_client.post(
                "/analyze",
                json={"listing_url": "https://www.cargurus.com/Cars/test", "vin": None},
            )
        assert response.status_code == 503
        assert response.json()["detail"]["error"] == "analysis_unavailable"

    def test_analyze_requires_url_or_vin(self, authed_client):
        """POST /analyze with neither url nor vin → 422 validation error."""
        response = authed_client.post(
            "/analyze",
            json={"listing_url": None, "vin": None},
        )
        assert response.status_code == 422
