"""
scripts/seed_demo.py

Demo Cache Seeder
------------------
Runs a real LemonCheck analysis on a listing and saves the result to
backend/demo_cache.json for use by the GET /demo endpoint.

Why a seed script instead of a live call on every /demo request?
  - The demo endpoint needs to be instant (no 20-30s wait for recruiters)
  - We want to curate the result — pick a listing with a compelling story
  - Seeding once lets us review and approve before it goes live

The demo listing should be:
  - A real, publicly accessible listing (CarGurus or AutoTrader)
  - Interesting grade — B or C is most relatable (not boring A or scary F)
  - Has real red/green flags and good comp data

Usage:
  # Seed from a listing URL (recommended — gets full data):
  python scripts/seed_demo.py --url "https://www.cargurus.com/Cars/..."

  # Seed from VIN only:
  python scripts/seed_demo.py --vin "2HGFC2F59KH504164"

  # Override the output path:
  python scripts/seed_demo.py --url "..." --output backend/demo_cache.json
"""

import asyncio
import argparse
import json
import sys
from pathlib import Path

# Load .env before importing anything else
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.claude_agent import run_analysis
from backend.models.analysis import AnalysisRequest

DEFAULT_OUTPUT = Path(__file__).parent.parent / "backend" / "demo_cache.json"


def print_report_preview(report) -> None:
    """Print a compact preview of the report before saving."""
    print(f"\n{'─' * 50}")
    print(f"  Grade:       {report.grade}")
    print(f"  Delta:       ${report.price_delta:+,}")
    print(f"  Verdict:     {report.price_verdict}")
    print(f"  Summary:     {report.summary[:120]}...")
    print(f"  Red flags:   {len(report.red_flags)}")
    print(f"  Green flags: {len(report.green_flags)}")
    print(f"  Comps:       {len(report.comps)}")
    print(f"{'─' * 50}\n")


async def seed() -> None:
    parser = argparse.ArgumentParser(
        description="Generate and cache a demo DealReport for GET /demo"
    )
    parser.add_argument("--url", help="CarGurus or AutoTrader listing URL")
    parser.add_argument("--vin", help="17-character VIN")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help=f"Output path for demo_cache.json (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    if not args.url and not args.vin:
        print("❌ Please provide --url or --vin (or both)")
        parser.print_help()
        sys.exit(1)

    output_path = Path(args.output)
    request = AnalysisRequest(
        listing_url=args.url or None,
        vin=args.vin or None,
    )

    print(f"\n🍋 LemonCheck Demo Seeder")
    if args.url:
        print(f"   URL: {args.url}")
    if args.vin:
        print(f"   VIN: {args.vin}")
    print(f"   Output: {output_path}")
    print(f"\n⏳ Running analysis... (15–30 seconds)\n")

    import time
    start = time.time()

    try:
        report = await run_analysis(request)
        elapsed = time.time() - start

        print(f"✅ Analysis complete ({elapsed:.1f}s)")
        print_report_preview(report)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report.model_dump(), indent=2),
            encoding="utf-8",
        )

        print(f"💾 Saved to {output_path}")
        print(f"\nThe /demo endpoint will now serve this result.")
        print(f"Review it above — if it looks good, commit demo_cache.json to git.\n")

    except Exception as e:
        elapsed = time.time() - start
        print(f"\n❌ Seed failed after {elapsed:.1f}s: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(seed())
