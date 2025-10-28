#!/usr/bin/env python3
"""Model Context Protocol server exposing the JustJoinIT pipeline."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from db.manager import DBManager
from llm.client import LLMError
from pipeline.processor import OfferPipeline
from parsing.offer_parser import (
    extract_content_for_llm,
    fetch_offer_html,
    parse_offer_detail,
)

server = Server("justjoinit")
pipeline = OfferPipeline()
db = pipeline.db
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OFFERS_PATH = PACKAGE_ROOT / "data" / "offers.json"

def _json_response(payload: Dict[str, Any]) -> List[TextContent]:
    return [
        TextContent(
            type="text",
            text=json.dumps(payload, indent=2, ensure_ascii=False),
        )
    ]


@server.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="analyze_job_offer",
            description="Unified 1-stage LLM analysis (120B model): comprehensive scoring with tags, risks, fit, and decision in single call",
            inputSchema={
                "type": "object",
                "properties": {
                    "link": {"type": "string"},
                    "content": {"type": "string"},
                    "metadata": {"type": "object"},
                },
                "anyOf": [
                    {"required": ["content"]},
                    {"required": ["link"]},
                ],
            },
        ),
        Tool(
            name="fetch_job_offers",
            description="Fetch, parse, and stage specific offer links (without scoring)",
            inputSchema={
                "type": "object",
                "properties": {
                    "links": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                    }
                },
                "required": ["links"],
            },
        ),
        Tool(
            name="process_new_offers",
            description="Run the full pipeline for offers in 'discovered' state",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "number"},
                },
            },
        ),
        Tool(
            name="upload_offers_json",
            description="Load offers.json into the database",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                },
            },
        ),
        Tool(
            name="get_top_matches",
            description="Return APPLY offers ordered by final score",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "number"},
                },
            },
        ),
        Tool(
            name="get_stats",
            description="Return aggregated database statistics",
            inputSchema={"type": "object"},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    if name == "analyze_job_offer":
        return await _analyze_job_offer(arguments)
    if name == "fetch_job_offers":
        return await _fetch_job_offers(arguments)
    if name == "process_new_offers":
        return await _process_new_offers(arguments)
    if name == "upload_offers_json":
        return await _upload_offers_json(arguments)
    if name == "get_top_matches":
        return await _get_top_matches(arguments)
    if name == "get_stats":
        return await _get_stats(arguments)
    raise ValueError(f"Unknown tool: {name}")


async def _analyze_job_offer(args: Dict[str, Any]) -> List[TextContent]:
    """Unified 1-stage analysis for 120B model: all-in-one comprehensive scoring."""
    link = args.get("link")
    content = args.get("content")
    metadata = args.get("metadata", {})

    if not content:
        html = await _ensure_html(link)
        parsed = parse_offer_detail(html)
        db.save_parsed_data(link, parsed)
        content = extract_content_for_llm(parsed, html)
        metadata = _merge_metadata(link, metadata)

    try:
        scores = pipeline.scorer.score_offer(
            content=content,
            metadata=metadata,
        )
    except LLMError as exc:
        return _json_response({"error": str(exc)})

    if link:
        db.save_scores(link, scores)

    return _json_response(scores)


async def _fetch_job_offers(args: Dict[str, Any]) -> List[TextContent]:
    links: List[str] = args.get("links") or []
    results: List[Dict[str, Any]] = []
    for link in links:
        try:
            html = fetch_offer_html(link)
            if not html:
                raise RuntimeError("Empty response")
            parsed = parse_offer_detail(html)
            db.save_parsed_data(link, parsed)
            results.append({"link": link, "status": "parsed"})
        except Exception as exc:  # noqa: BLE001 - record failure
            results.append({"link": link, "status": "error", "message": str(exc)})
    return _json_response({"results": results})


async def _process_new_offers(args: Dict[str, Any]) -> List[TextContent]:
    limit = args.get("limit")
    summary = pipeline.process_new_offers(limit=int(limit) if limit else None)
    return _json_response(summary)


async def _upload_offers_json(args: Dict[str, Any]) -> List[TextContent]:
    override = args.get("file_path")
    file_path = Path(override) if override else DEFAULT_OFFERS_PATH
    try:
        inserted, updated = pipeline.load_offers_file(file_path)
    except FileNotFoundError as exc:
        return _json_response({"error": str(exc)})
    return _json_response({"inserted": inserted, "updated": updated, "file": str(file_path)})


async def _get_top_matches(args: Dict[str, Any]) -> List[TextContent]:
    limit = args.get("limit")
    rows = db.get_top_matches(limit=int(limit) if limit else 20)
    return _json_response({"offers": rows})


async def _get_stats(_: Dict[str, Any]) -> List[TextContent]:
    return _json_response(db.get_stats())


async def _ensure_html(link: Optional[str]) -> str:
    if not link:
        raise ValueError("link is required when content is absent")
    html = fetch_offer_html(link)
    if not html:
        raise RuntimeError(f"Could not fetch HTML for {link}")
    return html


def _merge_metadata(link: Optional[str], metadata: Dict[str, Any]) -> Dict[str, Any]:
    if not link:
        return metadata
    offer = db.get_offer_with_scores(link)
    if not offer:
        return metadata
    # Include all fields from job_details (except id, link_id, fetched_at)
    merged = {
        "company": offer.get("company"),
        "title": offer.get("title"),
        "location": offer.get("location"),
        "remote_type": offer.get("remote_type"),
        "contract_type": offer.get("contract_type"),
        "exp_level": offer.get("exp_level"),
        "employment_type": offer.get("employment_type"),
        "salary_min": offer.get("salary_min"),
        "salary_max": offer.get("salary_max"),
        "salary_currency": offer.get("salary_currency"),
        "salary_rate": offer.get("salary_rate"),
        "salary_type": offer.get("salary_type"),
        "tech_stack": offer.get("tech_stack"),
        "description": offer.get("description"),
    }
    merged.update(metadata)
    return merged


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream)


if __name__ == "__main__":
    asyncio.run(main())
