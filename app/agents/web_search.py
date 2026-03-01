from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import urlparse

import requests
from google.genai import types

from app.agents.gemini_client import extract_response_text, generate_content_async
from app.core.config import get_settings
from app.db.repository import repository
from app.graph.state import ResearchState, SearchResult

logger = logging.getLogger(__name__)

BLOCKED_HOSTS = {
    "x.com",
    "twitter.com",
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "tiktok.com",
    "reddit.com",
    "pinterest.com",
    "snapchat.com",
}
BLOCKED_SUFFIXES = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"}

# Gemini grounding returns redirect URLs under this host.
# We resolve these to their real destination before storing.
REDIRECT_HOST = "vertexaisearch.cloud.google.com"

# Timeout (seconds) for the redirect-resolution HEAD request.
# Kept short — this is a best-effort operation; original URL is used as fallback.
REDIRECT_RESOLVE_TIMEOUT = 5

_RESOLVE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


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


def _is_redirect_url(url: str) -> bool:
    """Return True if this URL is a Gemini grounding redirect that needs resolving."""
    try:
        return urlparse(url).netloc == REDIRECT_HOST
    except Exception:
        return False


def _resolve_redirect(url: str) -> str:
    """
    Follow the redirect chain and return the final real URL.

    Uses a HEAD request with allow_redirects=True so we get the destination
    without downloading the page body. Falls back to the original URL on any error.
    """
    try:
        resp = requests.head(
            url,
            headers=_RESOLVE_HEADERS,
            timeout=REDIRECT_RESOLVE_TIMEOUT,
            allow_redirects=True,
        )
        final_url = resp.url
        # Sanity-check: the resolved URL must still be a valid, non-redirect URL.
        if final_url and final_url != url and _is_allowed_url(final_url):
            return final_url
    except Exception:
        pass
    return url


async def _resolve_redirect_async(url: str) -> str:
    """Async wrapper around _resolve_redirect so it doesn't block the event loop."""
    return await asyncio.to_thread(_resolve_redirect, url)


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
            if not url:
                continue

            title = getattr(web, "title", "") or ""
            snippet = snippets[idx] if idx < len(snippets) else ""

            # Store the raw URL here; redirect resolution happens later
            # in web_search_node where we can run it concurrently.
            items.append({"url": url, "title": title, "snippet": snippet})

    return items


async def _resolve_results(results: list[SearchResult]) -> list[SearchResult]:
    """
    Resolve any Gemini redirect URLs in the results list concurrently.

    For each result whose URL is a Gemini grounding redirect, we fire a HEAD
    request to get the real destination URL. All resolutions run in parallel
    so the total wait is bounded by the slowest single redirect, not the sum.
    """
    redirect_indices = [
        i for i, r in enumerate(results) if _is_redirect_url(r["url"])
    ]

    if not redirect_indices:
        return results

    # Resolve all redirects concurrently
    resolved_urls = await asyncio.gather(
        *[_resolve_redirect_async(results[i]["url"]) for i in redirect_indices],
        return_exceptions=True,
    )

    resolved = list(results)
    for i, new_url in zip(redirect_indices, resolved_urls):
        if isinstance(new_url, str) and new_url != resolved[i]["url"]:
            logger.debug("Resolved redirect: %s → %s", resolved[i]["url"], new_url)
            resolved[i] = {**resolved[i], "url": new_url}

    return resolved


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
            temperature=1.0
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

        raw_results = _extract_grounded_results(response)

        # Fallback: keep model text for debugging when grounding metadata is empty.
        if not raw_results and extract_response_text(response):
            continue

        # Resolve Gemini redirect URLs → real source URLs (runs concurrently)
        resolved_results = await _resolve_results(raw_results)

        for item in resolved_results:
            url = item["url"]

            # Apply URL filters AFTER resolution so we filter on the real URL,
            # not the Gemini redirect wrapper.
            if not _is_allowed_url(url):
                continue

            if url in seen:
                continue

            seen.add(url)
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