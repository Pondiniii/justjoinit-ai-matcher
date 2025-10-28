#!/usr/bin/env python3
"""
3-Phase Pipeline Runner:
  Phase 1: Discovery  (load links from offers.json)
  Phase 2: Fetching   (curl each offer page)
  Phase 3: Analysis   (LLM scoring)

Usage:
  python main.py [limit] [--workers N]

Examples:
  python main.py 10              # Process 10 offers, 1 worker
  python main.py 100 --workers 4 # Process 100 offers, 4 parallel workers
  python main.py --workers 10    # Process all offers, 10 parallel workers
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from pipeline.processor import OfferPipeline

PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_OFFERS_PATH = PACKAGE_ROOT / "data" / "offers.json"


def parse_args():
    """Parse command line arguments"""
    limit = None
    workers = 1
    offers_path = DEFAULT_OFFERS_PATH

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == '--workers' or arg == '-w':
            if i + 1 < len(args):
                workers = int(args[i + 1])
                i += 2
            else:
                print("Error: --workers requires a number")
                sys.exit(1)
        elif arg.startswith('--workers='):
            workers = int(arg.split('=')[1])
            i += 1
        elif arg.isdigit():
            limit = int(arg)
            i += 1
        else:
            offers_path = Path(arg)
            i += 1

    return limit, workers, offers_path


def main() -> None:
    limit, workers, offers_path = parse_args()

    pipeline = OfferPipeline()

    print("=" * 60)
    print("🤖 JustJoinIT AI Analyzer - 3-Phase Pipeline")
    print("=" * 60)
    print(f"⚙️  Workers: {workers}")

    # Check LLM server
    if not pipeline.scorer.client.health():
        print("⚠️  LLM server not reachable at http://localhost:1234/v1")
        print("   Start lm-studio or adjust config in config.py")
        return
    else:
        print("✓ LLM server reachable")

    # Phase 1: Discovery
    if offers_path.exists():
        print(f"\n🔍 Phase 1: Discovery")
        inserted = pipeline.load_offers_file(offers_path)
        print(f"✓ Loaded {inserted} links from {offers_path.name}")
    else:
        print(f"\n⚠️  {offers_path} not found – skipping discovery")

    # Phase 2 & 3: Fetch + Analyze
    if workers == 1:
        print(f"\n📥🤖 Phase 2+3: Fetch → Analyze (sequential, limit={limit or 'all'})")
        results = pipeline.process_one_by_one(limit=limit)
    else:
        print(f"\n📥🤖 Phase 2+3: Fetch → Analyze (parallel, {workers} workers, limit={limit or 'all'})")
        results = pipeline.process_concurrent(limit=limit, max_workers=workers)

    print(f"✓ Processed: {results['success']}/{results['total']}")

    # Stats
    stats = pipeline.db.get_stats()
    print("\n📈 Database Statistics")
    for key, value in stats.items():
        print(f"  {key.replace('_', ' ').title():<15}: {value}")

    print("\nDone.")


if __name__ == "__main__":
    main()
