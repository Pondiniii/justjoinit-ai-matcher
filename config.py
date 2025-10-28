"""Shared configuration for JustJoinIT pipeline"""

import os

# LLM API Configuration (xAI, OpenAI, or any OpenAI-compatible endpoint)
# Load from environment variables (see .env.example)
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.x.ai/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "grok-4-fast-non-reasoning")
LLM_TIMEOUT = int(os.environ.get("LLM_TIMEOUT", "180"))
LLM_API_KEY = os.environ.get("LLM_API_KEY")  # REQUIRED: Set in .env file

if not LLM_API_KEY:
    raise ValueError(
        "LLM_API_KEY environment variable is required! "
        "Copy .env.example to .env and set your API key."
    )
