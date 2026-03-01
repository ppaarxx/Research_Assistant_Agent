from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Any

from google import genai

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_genai_client() -> genai.Client | None:
    settings = get_settings()
    if not settings.gemini_api_key:
        return None
    return genai.Client(api_key=settings.gemini_api_key)


async def generate_content_async(*, model: str, contents: str, config: Any) -> Any:
    client = get_genai_client()
    if client is None:
        return None

    try:
        return await asyncio.to_thread(
            client.models.generate_content,
            model=model,
            contents=contents,
            config=config,
        )
    except Exception:
        return None


def extract_response_text(response: Any) -> str:
    if response is None:
        return ""

    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text

    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            value = getattr(part, "text", None)
            if isinstance(value, str) and value.strip():
                return value
    return ""
