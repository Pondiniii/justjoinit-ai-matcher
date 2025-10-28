"""3-phase pipeline: Discovery → Fetching → Analysis"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Any, List

from db.manager import DBManager
from llm.unified_scorer import UnifiedScorer
from parsing.offer_parser import (
    extract_content_for_llm,
    fetch_offer_html,
    parse_offer_detail,
)


@dataclass
class OfferPipeline:
    db: DBManager = field(default_factory=DBManager)
    scorer: UnifiedScorer = field(default_factory=UnifiedScorer)
    rate_limit_seconds: float = field(
        default_factory=lambda: float(os.getenv("PIPELINE_RATE_LIMIT", "2.0"))
    )

    # ========================================
    # PHASE 1: Link Discovery
    # ========================================

    def load_offers_file(self, offers_path: Path) -> int:
        """Phase 1: Load links from offers.json → job_links"""
        if not offers_path.exists():
            raise FileNotFoundError(f"Offers file not found: {offers_path}")

        with offers_path.open("r", encoding="utf-8") as fh:
            offers = json.load(fh)

        inserted = 0
        for offer in offers:
            link = offer.get("link")
            if link:
                self.db.insert_link(link)
                inserted += 1

        return inserted

    # ========================================
    # PHASE 2: Detail Fetching
    # ========================================

    def fetch_details(self, limit: Optional[int] = None) -> Dict[str, int]:
        """Phase 2: Fetch details for 'discovered' links → job_details"""
        links = self.db.get_links_by_status("discovered", limit=limit)
        total = len(links)
        if not total:
            return {"success": 0, "failed": 0, "total": 0}

        success = 0
        failed = 0

        for idx, row in enumerate(links, start=1):
            link_id = row["id"]
            link = row["link"]

            try:
                print(f"[{idx}/{total}] Fetching {link}", flush=True)
                html = fetch_offer_html(link)
                if not html or len(html) < 1000:
                    raise ValueError("Invalid HTML (too short)")

                parsed = parse_offer_detail(html)

                # VALIDATION: Sanity checks to prevent garbage data
                description = parsed.get("description", "")
                title = parsed.get("title")
                company = parsed.get("company")

                # Check 1: Must have description (core field, min 500 chars for quality)
                if not description or len(description) < 500:
                    raise ValueError(f"Invalid parsing: description too short ({len(description)} chars, need ≥500)")

                # Check 2: Rate limit / error pages detection
                desc_lower = description.lower()
                if any(marker in desc_lower for marker in ["rate limit", "error 429", "too many requests", "access denied", "forbidden"]):
                    raise ValueError("Rate limit or error page detected")

                # Check 3: Core fields check (at least title OR company must exist)
                if not title and not company:
                    raise ValueError("Invalid parsing: missing both title and company")

                # Check 4: Too many NULLs check - count critical nulls
                critical_fields = [title, company, description]
                null_count = sum(1 for field in critical_fields if not field)
                if null_count >= 2:  # If 2+ critical fields are null, reject
                    raise ValueError(f"Too many NULL critical fields: {null_count}/3")

                # Extract details (parser now returns all fields directly)
                details = {
                    "title": title,
                    "company": company,
                    "location": parsed.get("location"),
                    "remote_type": parsed.get("remote_mode"),
                    "contract_type": parsed.get("contract_type"),
                    "exp_level": parsed.get("exp_level"),
                    "employment_type": parsed.get("employment_type"),
                    "salary_min": parsed.get("salary_min"),
                    "salary_max": parsed.get("salary_max"),
                    "salary_currency": parsed.get("salary_currency"),
                    "salary_rate": parsed.get("salary_rate"),
                    "salary_type": parsed.get("salary_type"),
                    "description": description,
                    "tech_stack": parsed.get("tech_stack", {}),
                }

                self.db.save_details(link_id, details)
                self.db.update_link_status(link_id, "fetched")

                print(f"[{idx}/{total}] ✓ Fetched (desc: {len(description)} chars)", flush=True)
                success += 1

            except Exception as exc:
                print(f"[{idx}/{total}] ✗ Failed: {exc}", flush=True)
                failed += 1

            finally:
                if self.rate_limit_seconds > 0:
                    time.sleep(self.rate_limit_seconds)

        return {"success": success, "failed": failed, "total": success + failed}

    # ========================================
    # PHASE 3: LLM Analysis
    # ========================================

    def analyze_offers(self, limit: Optional[int] = None) -> Dict[str, int]:
        """Phase 3: Run LLM analysis on 'fetched' offers → job_analysis"""
        links = self.db.get_links_by_status("fetched", limit=limit)
        total = len(links)
        if not total:
            return {"success": 0, "failed": 0, "total": 0}

        success = 0
        failed = 0

        for idx, row in enumerate(links, start=1):
            link_id = row["id"]
            link = row["link"]

            try:
                print(f"[{idx}/{total}] Analyzing {link}", flush=True)

                # Get details
                details = self.db.get_details_by_link_id(link_id)
                if not details:
                    raise ValueError("No details found")

                # Prepare LLM content (string, not dict!)
                description = details.get("description", "")
                tech_stack = details.get("tech_stack", [])
                llm_content = f"{description}\n\nTech stack: {', '.join(tech_stack) if tech_stack else 'N/A'}"

                metadata = {
                    "company": details.get("company"),
                    "title": details.get("title"),
                    "location": details.get("location"),
                    "remote_type": details.get("remote_type"),
                    "contract_type": details.get("contract_type"),
                    "salary_min": details.get("salary_min"),
                    "salary_max": details.get("salary_max"),
                    "salary_currency": details.get("salary_currency"),
                }

                # Run LLM
                analysis = self.scorer.score_offer(
                    content=llm_content,
                    metadata=metadata,
                )

                # CRITICAL: Save analysis FIRST, update status ONLY if save succeeds
                # This ensures failed LLM runs (bad JSON, missing fields) can be retried
                self.db.save_analysis(link_id, analysis)

                # Only mark as analyzed if save succeeded (no exception thrown)
                self.db.update_link_status(link_id, "analyzed")

                decision = analysis.get("decision", "WATCH")
                fit = analysis.get("fit_score", 0)
                print(f"[{idx}/{total}] ✓ {decision} (fit={fit:.0f})", flush=True)
                success += 1

            except Exception as exc:
                print(f"[{idx}/{total}] ✗ Failed: {exc}", flush=True)
                failed += 1

            finally:
                if self.rate_limit_seconds > 0:
                    time.sleep(self.rate_limit_seconds)

        return {"success": success, "failed": failed, "total": success + failed}

    # ========================================
    # COMBINED: Run all 3 phases
    # ========================================

    def process_all(self, limit: Optional[int] = None) -> None:
        """Run all 3 phases sequentially (OLD APPROACH: batch fetch then batch analyze)"""
        print("\n🔍 Phase 1: Discovery")
        # Discovery is done via load_offers_file()

        print("\n📥 Phase 2: Fetching details")
        fetch_results = self.fetch_details(limit=limit)
        print(f"✓ Fetched: {fetch_results['success']}/{fetch_results['total']}")

        print("\n🤖 Phase 3: LLM Analysis")
        analyze_results = self.analyze_offers(limit=limit)
        print(f"✓ Analyzed: {analyze_results['success']}/{analyze_results['total']}")

    def process_one_by_one(self, limit: Optional[int] = None) -> Dict[str, int]:
        """Process offers one by one: fetch → analyze → next

        NEW APPROACH: For each offer, fetch it then immediately analyze it.
        This is faster and more efficient - no need to wait for all fetches to complete.
        """
        links = self.db.get_links_by_status("discovered", limit=limit)
        total = len(links)
        if not total:
            return {"success": 0, "failed": 0, "total": 0}

        success = 0
        failed = 0

        for idx, row in enumerate(links, start=1):
            link_id = row["id"]
            link = row["link"]

            try:
                # STEP 1: Fetch
                print(f"[{idx}/{total}] Fetching {link}", flush=True)
                html = fetch_offer_html(link)
                if not html:
                    raise ValueError("Empty HTML response")

                # Parse
                parsed = parse_offer_detail(html)

                # VALIDATION: Sanity checks to prevent garbage data
                description = parsed.get("description", "")
                title = parsed.get("title")
                company = parsed.get("company")

                # Check 1: Must have description (core field, min 500 chars for quality)
                if not description or len(description) < 500:
                    raise ValueError(f"Invalid parsing: description too short ({len(description)} chars, need ≥500)")

                # Check 2: Rate limit / error pages detection
                desc_lower = description.lower()
                if any(marker in desc_lower for marker in ["rate limit", "error 429", "too many requests", "access denied", "forbidden"]):
                    raise ValueError("Rate limit or error page detected")

                # Check 3: Core fields check (at least title OR company must exist)
                if not title and not company:
                    raise ValueError("Invalid parsing: missing both title and company")

                # Check 4: Too many NULLs check - count critical nulls
                critical_fields = [title, company, description]
                null_count = sum(1 for field in critical_fields if not field)
                if null_count >= 2:  # If 2+ critical fields are null, reject
                    raise ValueError(f"Too many NULL critical fields: {null_count}/3")

                # Save details
                details = {
                    "title": title,
                    "company": company,
                    "location": parsed.get("location"),
                    "remote_type": parsed.get("remote_mode"),
                    "contract_type": parsed.get("contract_type"),
                    "exp_level": parsed.get("exp_level"),
                    "employment_type": parsed.get("employment_type"),
                    "salary_min": parsed.get("salary_min"),
                    "salary_max": parsed.get("salary_max"),
                    "salary_currency": parsed.get("salary_currency"),
                    "salary_rate": parsed.get("salary_rate"),
                    "salary_type": parsed.get("salary_type"),
                    "description": description,
                    "tech_stack": parsed.get("tech_stack", {}),
                }

                self.db.save_details(link_id, details)
                self.db.update_link_status(link_id, "fetched")

                print(f"[{idx}/{total}] ✓ Fetched (desc: {len(description)} chars)", flush=True)

                # STEP 2: Analyze immediately
                print(f"[{idx}/{total}] Analyzing...", flush=True)

                # Prepare LLM content
                tech_stack = details.get("tech_stack", [])
                llm_content = f"{description}\n\nTech stack: {', '.join(tech_stack) if tech_stack else 'N/A'}"

                metadata = {
                    "company": details.get("company"),
                    "title": details.get("title"),
                    "location": details.get("location"),
                    "remote_type": details.get("remote_type"),
                    "contract_type": details.get("contract_type"),
                    "exp_level": details.get("exp_level"),
                    "employment_type": details.get("employment_type"),
                    "salary_min": details.get("salary_min"),
                    "salary_max": details.get("salary_max"),
                    "salary_currency": details.get("salary_currency"),
                    "salary_rate": details.get("salary_rate"),
                    "salary_type": details.get("salary_type"),
                }

                # Run LLM
                analysis = self.scorer.score_offer(
                    content=llm_content,
                    metadata=metadata,
                )

                # CRITICAL: Save analysis FIRST, update status ONLY if save succeeds
                self.db.save_analysis(link_id, analysis)
                self.db.update_link_status(link_id, "analyzed")

                decision = analysis.get("decision", "WATCH")
                fit = analysis.get("fit_score", 0)
                print(f"[{idx}/{total}] ✓ {decision} (fit={fit:.0f})", flush=True)
                success += 1

            except Exception as exc:
                print(f"[{idx}/{total}] ✗ Failed: {exc}", flush=True)
                failed += 1

            finally:
                if self.rate_limit_seconds > 0:
                    time.sleep(self.rate_limit_seconds)

        return {"success": success, "failed": failed, "total": success + failed}

    def process_concurrent(self, limit: Optional[int] = None, max_workers: int = 4) -> Dict[str, int]:
        """Process offers concurrently: fetch → analyze (parallel workers)

        CONCURRENT APPROACH: Process multiple offers in parallel using ThreadPoolExecutor.
        Good for API-bound tasks (waiting for Grok API responses).

        Args:
            limit: Maximum number of offers to process
            max_workers: Number of parallel workers (default: 4, recommended: 4-10)
        """
        links = self.db.get_links_by_status("discovered", limit=limit)
        total = len(links)
        if not total:
            return {"success": 0, "failed": 0, "total": 0}

        success = 0
        failed = 0
        processed = 0

        def process_single_offer(row: Dict[str, Any]) -> tuple:
            """Process one offer (fetch + analyze). Returns (link_id, link, success, error_msg)"""
            link_id = row["id"]
            link = row["link"]

            try:
                # STEP 1: Fetch
                html = fetch_offer_html(link)
                if not html:
                    raise ValueError("Empty HTML response")

                # Parse
                parsed = parse_offer_detail(html)

                # VALIDATION
                description = parsed.get("description", "")
                title = parsed.get("title")
                company = parsed.get("company")

                if not description or len(description) < 500:
                    raise ValueError(f"description too short ({len(description)} chars)")

                if any(m in description.lower() for m in ["rate limit", "error 429"]):
                    raise ValueError("Rate limit detected")

                if not title and not company:
                    raise ValueError("Missing title and company")

                # Save details
                details = {
                    "title": title,
                    "company": company,
                    "location": parsed.get("location"),
                    "remote_type": parsed.get("remote_mode"),
                    "contract_type": parsed.get("contract_type"),
                    "exp_level": parsed.get("exp_level"),
                    "employment_type": parsed.get("employment_type"),
                    "salary_min": parsed.get("salary_min"),
                    "salary_max": parsed.get("salary_max"),
                    "salary_currency": parsed.get("salary_currency"),
                    "salary_rate": parsed.get("salary_rate"),
                    "salary_type": parsed.get("salary_type"),
                    "description": description,
                    "tech_stack": parsed.get("tech_stack", {}),
                }

                self.db.save_details(link_id, details)
                self.db.update_link_status(link_id, "fetched")

                # STEP 2: Analyze
                tech_stack = details.get("tech_stack", [])
                llm_content = f"{description}\n\nTech stack: {', '.join(tech_stack) if tech_stack else 'N/A'}"

                metadata = {
                    "company": details.get("company"),
                    "title": details.get("title"),
                    "location": details.get("location"),
                    "remote_type": details.get("remote_type"),
                    "contract_type": details.get("contract_type"),
                    "exp_level": details.get("exp_level"),
                    "employment_type": details.get("employment_type"),
                    "salary_min": details.get("salary_min"),
                    "salary_max": details.get("salary_max"),
                    "salary_currency": details.get("salary_currency"),
                    "salary_rate": details.get("salary_rate"),
                    "salary_type": details.get("salary_type"),
                }

                analysis = self.scorer.score_offer(content=llm_content, metadata=metadata)
                self.db.save_analysis(link_id, analysis)
                self.db.update_link_status(link_id, "analyzed")

                decision = analysis.get("decision", "WATCH")
                fit = analysis.get("fit_score", 0)

                return (link_id, link, True, f"{decision} (fit={fit:.0f})")

            except Exception as exc:
                return (link_id, link, False, str(exc))

        # Process concurrently
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_link = {executor.submit(process_single_offer, row): row for row in links}

            for future in as_completed(future_to_link):
                processed += 1
                link_id, link, is_success, msg = future.result()

                if is_success:
                    print(f"[{processed}/{total}] ✓ {msg}", flush=True)
                    success += 1
                else:
                    print(f"[{processed}/{total}] ✗ {msg}", flush=True)
                    failed += 1

        return {"success": success, "failed": failed, "total": success + failed}
