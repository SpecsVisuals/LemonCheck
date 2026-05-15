"""
models/analysis.py

Pydantic Models — LemonCheck Analysis Pipeline
------------------------------------------------
These models define the data contracts for the full analysis pipeline:
  input → agent → output.

Models:
  AnalysisRequest  Input from the frontend (listing_url OR vin)
  Flag             A single red or green flag (title + description)
  CompListing      A comparable vehicle listing with price delta
  DealReport       Full structured output from the Claude agent

All fields are strictly typed and validated by Pydantic v2.
DealReport matches analysis_schema.json exactly — if you update one, update the other.

Validation notes:
  - DealReport.grade is validated to be A/B/C/D/F only
  - AnalysisRequest validates that at least one of listing_url or vin is present
  - CompListing.price is required (int) — comps without prices aren't useful
  - All string fields are stripped of leading/trailing whitespace
"""

from typing import Literal, Optional
from pydantic import BaseModel, field_validator, model_validator


# ── Input model ───────────────────────────────────────────────────────────────

class AnalysisRequest(BaseModel):
    """
    Input to the analysis pipeline.
    At least one of listing_url or vin must be provided.

    Examples:
      AnalysisRequest(listing_url="https://www.cargurus.com/...")
      AnalysisRequest(vin="2HGFC2F59KH123456")
      AnalysisRequest(listing_url="https://...", vin="2HGFC2F59KH123456")
    """
    listing_url: Optional[str] = None
    vin: Optional[str] = None

    @model_validator(mode="after")
    def require_url_or_vin(self) -> "AnalysisRequest":
        if not self.listing_url and not self.vin:
            raise ValueError("At least one of listing_url or vin must be provided")
        return self

    @field_validator("listing_url")
    @classmethod
    def validate_listing_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v.startswith("http"):
            raise ValueError("listing_url must be a valid HTTP URL")
        return v

    @field_validator("vin")
    @classmethod
    def validate_vin_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().upper()
        if len(v) != 17:
            raise ValueError(f"VIN must be 17 characters, got {len(v)}")
        return v


# ── Output sub-models ─────────────────────────────────────────────────────────

class Flag(BaseModel):
    """
    A single red or green flag from the deal analysis.

    title:       Short label, e.g. "High Mileage" or "Below Market Price"
    description: 1-2 sentences with specific data, e.g.
                 "At 78,000 miles, this 2019 Civic has been driven ~13k/year —
                  above average. Budget for timing belt service (~$400) soon."
    """
    title: str
    description: str

    @field_validator("title", "description")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class CompListing(BaseModel):
    """
    A comparable vehicle listing used to establish market price context.

    delta_vs_this: how much more (positive) or less (negative) expensive this
                   comp is versus the analyzed car. E.g., if analyzed car is $16,500
                   and this comp is $17,200, delta_vs_this = +700.
    """
    title: str
    price: int                       # Asking price in USD (required — unlisted comps aren't useful)
    mileage: Optional[int] = None    # Odometer reading (may not be in search snippet)
    url: str
    delta_vs_this: int               # comp_price - analyzed_price (positive = comp is pricier)

    @field_validator("price")
    @classmethod
    def validate_price_range(cls, v: int) -> int:
        if not (500 <= v <= 500_000):
            raise ValueError(f"Comp price {v} is outside plausible range ($500–$500k)")
        return v


# ── Primary output model ──────────────────────────────────────────────────────

class DealReport(BaseModel):
    """
    The full structured output from the Claude agent chain.

    This is what gets returned to the frontend and stored in Supabase.
    Every field maps 1:1 to a section of the DealCard UI component.

    Schema is also defined in backend/prompts/analysis_schema.json —
    keep both in sync when making changes.
    """
    grade: Literal["A", "B", "C", "D", "F"]
    """Overall deal grade. A=excellent buy, F=avoid entirely."""

    price_delta: int
    """
    Asking price minus market median, in dollars.
    Negative = below market (good for buyer), positive = above market (bad for buyer).
    Example: -1200 means "priced $1,200 below market"
    """

    price_verdict: str
    """
    One plain-English sentence summarizing the price position.
    Example: "This car is priced $1,200 BELOW market for a 2019 Honda Civic LX with 62k miles."
    """

    red_flags: list[Flag]
    """Risk factors. Empty list if no red flags found (unlikely but possible)."""

    green_flags: list[Flag]
    """Buyer advantages. Empty list if no green flags found."""

    comps: list[CompListing]
    """Up to 5 comparable listings. May be empty if search returned no results."""

    negotiation_points: list[str]
    """2-4 specific, actionable negotiation talking points with dollar amounts where possible."""

    summary: str
    """
    2-3 sentence plain-English bottom line for a non-expert buyer.
    Should be the first thing they read — the TL;DR of the whole analysis.
    """

    @field_validator("grade")
    @classmethod
    def validate_grade(cls, v: str) -> str:
        # Literal type already enforces this, but belt-and-suspenders for Claude output
        valid = {"A", "B", "C", "D", "F"}
        v = v.strip().upper()
        if v not in valid:
            raise ValueError(f"grade must be one of {valid}, got '{v}'")
        return v

    @field_validator("price_verdict", "summary")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()

    @field_validator("negotiation_points")
    @classmethod
    def require_negotiation_points(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("negotiation_points must have at least one item")
        return [point.strip() for point in v]
