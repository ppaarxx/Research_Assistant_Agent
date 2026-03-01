from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from google.genai import types

from app.agents.gemini_client import extract_response_text, generate_content_async
from app.core.config import get_settings
from app.db.repository import repository
from app.graph.state import ResearchState, SearchResult


BLOCKED_HOSTS = {
    "x.com",
    "twitter.com",
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "tiktok.com",
    "reddit.com",
}
BLOCKED_SUFFIXES = {".pdf", ".doc", ".docx", ".ppt", ".pptx"}


def _is_allowed_url(url: str) -> bool:
    if not url:
        return False

    lower = url.lower()
    if any(lower.endswith(suffix) for suffix in BLOCKED_SUFFIXES):
        return False

    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    if host in BLOCKED_HOSTS:
        return False

    return parsed.scheme in {"http", "https"}


def _extract_grounded_results(response: Any) -> list[SearchResult]:
    items: list[SearchResult] = []

    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        grounding_metadata = getattr(candidate, "grounding_metadata", None)
        if grounding_metadata is None:
            continue

        chunks = getattr(grounding_metadata, "grounding_chunks", None) or []
        supports = getattr(grounding_metadata, "grounding_supports", None) or []

        snippets: list[str] = []
        for support in supports:
            segment = getattr(support, "segment", None)
            text = getattr(segment, "text", "") if segment else ""
            if text:
                snippets.append(text)

        for idx, chunk in enumerate(chunks):
            web = getattr(chunk, "web", None)
            if web is None:
                continue

            url = getattr(web, "uri", "") or ""
            if not _is_allowed_url(url):
                continue

            title = getattr(web, "title", "") or ""
            snippet = snippets[idx] if idx < len(snippets) else ""
            items.append({"url": url, "title": title, "snippet": snippet})

    return items


async def web_search_node(state: ResearchState) -> dict[str, Any]:
    settings = get_settings()
    existing = list(state.get("search_results", []))
    seen = {item["url"] for item in existing if item.get("url")}

    await repository.set_stage_and_iteration(
        job_id=state["job_id"],
        current_stage="web_search",
        iteration=int(state["iteration"]),
    )

    try:
        config: Any = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.2,
        )
    except Exception:
        config = {"tools": [{"google_search": {}}], "temperature": 0.2}

    for query in state.get("search_queries", []):
        response = await generate_content_async(
            model=settings.worker_model,
            contents=f"Find high-quality sources for: {query}",
            config=config,
        )

        if response is None:
            break

        grounded = _extract_grounded_results(response)

        # Fallback: keep model text for debugging when grounding metadata is empty.
        if not grounded and extract_response_text(response):
            continue

        for item in grounded:
            if item["url"] in seen:
                continue
            seen.add(item["url"])
            existing.append(item)
            if len(existing) >= state["max_sources"]:
                break

        if len(existing) >= state["max_sources"]:
            break

    final_results = existing[: state["max_sources"]]
    await repository.upsert_search_results(
        job_id=state["job_id"],
        iteration=int(state["iteration"]),
        results=final_results,
    )

    return {
        "search_results": final_results,
        "status": "running",
    }
