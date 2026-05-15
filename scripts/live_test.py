"""
scripts/live_test.py

Quick live test runner for the LemonCheck Claude agent.
Runs a real analysis and pretty-prints the full DealReport.

Usage:
  # Test with a listing URL:
  python scripts/live_test.py --url "https://www.cargurus.com/Cars/..."

  # Test with a VIN only:
  python scripts/live_test.py --vin "2HGFC2F59KH504164"

  # Test with both:
  python scripts/live_test.py --url "https://..." --vin "2HGFC2F59KH504164"
"""

import asyncio
import argparse
import json
import sys
import os
from pathlib import Path

# Load .env before importing anything else
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.claude_agent import run_analysis
from backend.models.analysis import AnalysisRequest

GRADE_COLORS = {
    "A": "\033[92m",   # green
    "B": "\033[94m",   # blue
    "C": "\033[93m",   # yellow
    "D": "\033[91m",   # red-orange
    "F": "\033[91m",   # red
}
RESET = "\033[0m"
BOLD  = "\033[1m"


def print_report(report, elapsed: float):
    g = report.grade
    color = GRADE_COLORS.get(g, "")

    print("\n" + "═" * 60)
    print(f"{BOLD}🍋 LEMONCHECK DEAL REPORT{RESET}  ({elapsed:.1f}s)")
    print("═" * 60)

    print(f"\n{BOLD}GRADE:{RESET}  {color}{BOLD} {g} {RESET}")
    print(f"{BOLD}PRICE:{RESET}  {report.price_verdict}")
    delta = report.price_delta
    delta_str = f"${abs(delta):,} {'BELOW' if delta < 0 else 'ABOVE'} market"
    print(f"        (${abs(delta):,} {'↓ below' if delta < 0 else '↑ above'} median)")

    print(f"\n{BOLD}SUMMARY{RESET}")
    print(f"  {report.summary}")

    if report.red_flags:
        print(f"\n{BOLD}🚩 RED FLAGS ({len(report.red_flags)}){RESET}")
        for flag in report.red_flags:
            print(f"  • {flag.title}")
            print(f"    {flag.description}")

    if report.green_flags:
        print(f"\n{BOLD}✅ GREEN FLAGS ({len(report.green_flags)}){RESET}")
        for flag in report.green_flags:
            print(f"  • {flag.title}")
            print(f"    {flag.description}")

    if report.comps:
        print(f"\n{BOLD}📊 COMPARABLE LISTINGS ({len(report.comps)}){RESET}")
        for comp in report.comps:
            delta_sign = "+" if comp.delta_vs_this > 0 else ""
            mileage_str = f"{comp.mileage:,}mi" if comp.mileage else "?mi"
            print(f"  • {comp.title[:55]}")
            print(f"    ${comp.price:,}  {mileage_str}  [{delta_sign}${comp.delta_vs_this:,} vs this car]")

    if report.negotiation_points:
        print(f"\n{BOLD}💬 NEGOTIATION POINTS{RESET}")
        for i, point in enumerate(report.negotiation_points, 1):
            print(f"  {i}. {point}")

    print("\n" + "═" * 60)
    print(f"{BOLD}Raw JSON:{RESET}")
    print(json.dumps(report.model_dump(), indent=2))
    print("═" * 60 + "\n")


async def main():
    parser = argparse.ArgumentParser(description="LemonCheck live test runner")
    parser.add_argument("--url", help="CarGurus or AutoTrader listing URL")
    parser.add_argument("--vin", help="17-character VIN")
    args = parser.parse_args()

    if not args.url and not args.vin:
        print("❌ Please provide --url or --vin (or both)")
        parser.print_help()
        sys.exit(1)

    request = AnalysisRequest(
        listing_url=args.url or None,
        vin=args.vin or None,
    )

    print(f"\n🍋 LemonCheck Live Test")
    if args.url:
        print(f"   URL: {args.url}")
    if args.vin:
        print(f"   VIN: {args.vin}")
    print(f"\n⏳ Running analysis... (this takes 15–30 seconds)\n")

    import time
    start = time.time()

    try:
        report = await run_analysis(request)
        elapsed = time.time() - start
        print_report(report, elapsed)
    except Exception as e:
        elapsed = time.time() - start
        print(f"\n❌ Analysis failed after {elapsed:.1f}s: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
