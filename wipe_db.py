#!/usr/bin/env python3
"""Wipe database with options: all tables or just analysis+details"""

from __future__ import annotations

import json
from pathlib import Path

from db.manager import DBManager


def wipe_all(db: DBManager) -> None:
    """Wipe ALL tables (job_links + details + analysis)"""
    try:
        with db.get_conn() as conn:
            cur = conn.cursor()
            print("🗑️  Truncating ALL tables...")
            cur.execute("TRUNCATE TABLE job_links RESTART IDENTITY CASCADE;")
            print("   ✓ job_links, job_details, job_analysis (all wiped)")
    except Exception as exc:
        print(f"❌ Error: {exc}")
        raise


def wipe_analysis_and_details(db: DBManager) -> None:
    """Wipe only job_analysis and job_details, keep job_links and reset status"""
    try:
        with db.get_conn() as conn:
            cur = conn.cursor()
            print("🗑️  Truncating job_analysis and job_details...")
            cur.execute("TRUNCATE TABLE job_analysis RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE TABLE job_details RESTART IDENTITY CASCADE;")
            print("   ✓ job_analysis wiped")
            print("   ✓ job_details wiped")

            print("🔄 Resetting job_links status to 'discovered'...")
            cur.execute("UPDATE job_links SET status = 'discovered';")
            cur.execute("SELECT COUNT(*) FROM job_links;")
            count = cur.fetchone()[0]
            print(f"   ✓ {count} links reset (ready for reprocessing)")
    except Exception as exc:
        print(f"❌ Error: {exc}")
        raise


def load_offers_from_json(db: DBManager) -> None:
    """Load fresh links from offers.json (optional, only after wipe_all)"""
    # Check if offers.json exists
    possible_paths = [
        Path("data/offers.json"),
        Path("scripts/data/offers.json"),
        Path("offers.json"),
    ]

    offers_file = None
    for path in possible_paths:
        if path.exists():
            offers_file = path
            break

    if not offers_file:
        print(f"⚠️  offers.json not found - skipping reload")
        return

    # Load offers
    with open(offers_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Handle both formats: list or dict with "offers" key
    if isinstance(data, list):
        offers = data
    elif isinstance(data, dict):
        offers = data.get("offers", [])
    else:
        offers = []

    if not offers:
        print("⚠️  No offers found in offers.json")
        return

    # Reload links
    print(f"📥 Loading {len(offers)} links from {offers_file.name}...")
    inserted = 0
    for offer in offers:
        link = offer.get("link") or offer.get("offer_url")
        if link:
            try:
                db.insert_link(link)
                inserted += 1
            except Exception as e:
                print(f"   ⚠️  Failed to insert {link}: {e}")

    print(f"✅ Loaded {inserted}/{len(offers)} links")


def main() -> None:
    db = DBManager()

    print("=" * 60)
    print("🗑️  Database Wipe Tool")
    print("=" * 60)
    print()
    print("Choose wipe mode:")
    print("  1) Wipe ALL (job_links + details + analysis)")
    print("     → Deletes everything, then reloads from offers.json")
    print()
    print("  2) Wipe ONLY analysis + details (keep job_links)")
    print("     → Keeps discovered links, resets status to 'discovered'")
    print("     → Use this to re-fetch and re-analyze existing links")
    print()

    choice = input("Enter 1 or 2 (or anything else to abort): ").strip()

    if choice == "1":
        print()
        print("⚠️  This will DELETE ALL DATA (job_links, job_details, job_analysis)")
        confirm = input("Type 'yes' to confirm: ").strip().lower()
        if confirm != "yes":
            print("❌ Aborted")
            return

        wipe_all(db)
        load_offers_from_json(db)
        print()
        print("✅ Done! Ready to run: python main.py <limit>")

    elif choice == "2":
        print()
        print("⚠️  This will DELETE job_analysis and job_details")
        print("    (job_links will be kept and reset to 'discovered')")
        confirm = input("Type 'yes' to confirm: ").strip().lower()
        if confirm != "yes":
            print("❌ Aborted")
            return

        wipe_analysis_and_details(db)
        print()
        print("✅ Done! Ready to run: python main.py <limit>")

    else:
        print("❌ Aborted")


if __name__ == "__main__":
    main()
