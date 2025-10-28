"""HTTP client for interacting with the local LLM server."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict

import requests


class LLMError(RuntimeError):
    """Raised when the LLM call fails or returns invalid JSON."""


@dataclass
class LLMClient:
    base_url: str
    model: str
    timeout: int = 60
    api_key: str = None  # Optional API key for hosted services (Grok, OpenAI, etc.)

    def _request(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.05,  # Very low for stable JSON
            "max_tokens": 4096,
        }

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = requests.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def complete_json(self, *, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """Call the LLM and parse the JSON payload from the response."""
        data = self._request(system_prompt, user_prompt)
        content = data["choices"][0]["message"]["content"].strip()

        if "```" in content:
            # Handle both ```json and ``` fences.
            blocks = content.split("```")
            for block in blocks:
                if not block:
                    continue
                cleaned = block
                if cleaned.startswith("json\n"):
                    cleaned = cleaned[len("json\n"):]
                trimmed = cleaned.strip()
                if trimmed.startswith("{"):
                    content = trimmed
                    break
            else:
                raise LLMError("LLM response did not include JSON block")
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMError(f"Invalid JSON from LLM: {exc}") from exc

    def health(self) -> bool:
        try:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            response = requests.get(f"{self.base_url}/models", timeout=5, headers=headers)
            return response.status_code == 200
        except requests.RequestException:
            return False
