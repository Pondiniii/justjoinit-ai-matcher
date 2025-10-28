"""Unified 1-stage LLM scorer - system prompt loaded from markdown."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

from config import LLM_BASE_URL, LLM_MODEL, LLM_TIMEOUT, LLM_API_KEY
from llm.client import LLMClient


def load_system_prompt() -> str:
    """Load system prompt from markdown file."""
    prompt_path = Path(__file__).parent.parent / "system_prompt.md"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


@dataclass
class UnifiedScorer:
    """Unified 1-stage scorer - system prompt from markdown."""

    client: LLMClient = field(default_factory=lambda: LLMClient(LLM_BASE_URL, LLM_MODEL, LLM_TIMEOUT, LLM_API_KEY))
    system_prompt: str = field(default_factory=load_system_prompt)

    def score_offer(
        self,
        *,
        content: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Score offer - 1 LLM call."""
        # Support both remote_mode (parser) and remote_type (database)
        remote = metadata.get('remote_type') or metadata.get('remote_mode', '?')

        # Build salary info with rate and type if available
        salary_info = f"{metadata.get('salary_min', '?')}-{metadata.get('salary_max', '?')} {metadata.get('salary_currency', '')}"
        if metadata.get('salary_rate'):
            salary_info += f"/{metadata.get('salary_rate')}"
        if metadata.get('salary_type'):
            salary_info += f" ({metadata.get('salary_type')})"

        user_prompt = f"""OFERTA DO ANALIZY:

Firma: {metadata.get('company', '?')}
Stanowisko: {metadata.get('title', '?')}
Lokalizacja: {metadata.get('location', '?')}
Tryb: {remote}
Umowa: {metadata.get('contract_type', '?')}
Exp level: {metadata.get('exp_level', '?')}
Typ zatrudnienia: {metadata.get('employment_type', '?')}
Kasa: {salary_info}

TREŚĆ:
{content[:3000]}

Zwróć JSON.
"""

        result = self.client.complete_json(
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
        )

        # Helper: clamp scores to 0-100
        def clamp_score(value: Any, default: int = 50) -> float:
            try:
                score = float(value)
                return max(0.0, min(100.0, score))
            except (TypeError, ValueError):
                return float(default)

        # Validate decision
        decision = result.get("decision", "WATCH").upper()
        if decision not in ["APPLY", "WATCH", "IGNORE"]:
            decision = "WATCH"

        return {
            "language": result.get("language", "unknown"),
            "short_summary": result.get("short_summary", "")[:500],
            "cringe_score": clamp_score(result.get("cringe_score"), 50),
            "januszex_score": clamp_score(result.get("januszex_score"), 50),
            "work_culture_score": clamp_score(result.get("work_culture_score"), 50),
            "stability_score": clamp_score(result.get("stability_score"), 50),
            "benefit_score": clamp_score(result.get("benefit_score"), 50),
            "lgbt_score": clamp_score(result.get("lgbt_score"), 50),
            "corpo_score": clamp_score(result.get("corpo_score"), 50),
            "fit_score": clamp_score(result.get("fit_score"), 50),
            "fit_reasoning": result.get("fit_reasoning", "")[:1000],
            "decision": decision,
        }


__all__ = ["UnifiedScorer"]
