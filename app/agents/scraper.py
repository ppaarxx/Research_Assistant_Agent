from __future__ import annotations

import asyncio
from typing import Any

import requests
from bs4 import BeautifulSoup

from app.core.config import get_settings
from app.db.repository import repository
from app.graph.state import ResearchState, ScrapedContent


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

NOISE_TAGS = [
    "script",
    "style",
    "nav",
    "footer",
    "header",
    "aside",
    "form",
    "noscript",
    "iframe",
]


def scrape_url(url: str, fallback_title: str = "") -> ScrapedContent:
    settings = get_settings()
    try:
        response = requests.get(url, headers=HEADERS, timeout=settings.request_timeout)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        for tag in soup(NOISE_TAGS):
            tag.decompose()

        main = (
            soup.find("article")
            or soup.find("main")
            or soup.find(id="content")
            or soup.find(class_="content")
            or soup.body
        )

        text = main.get_text(separator="\n", strip=True) if main else ""
        words = text.split()
        truncated = " ".join(words[:8000])

        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()

        return {
            "url": url,
            "title": title or fallback_title,
            "raw_text": truncated,
            "scrape_success": bool(truncated),
            "word_count": len(words),
        }
    except Exception:
        return {
            "url": url,
            "title": fallback_title,
            "raw_text": "",
            "scrape_success": False,
            "word_count": 0,
        }


async def scraper_node(state: ResearchState) -> dict[str, Any]:
    await repository.set_stage_and_iteration(
        job_id=state["job_id"],
        current_stage="scraper",
        iteration=int(state["iteration"]),
    )

    existing = {item["url"]: item for item in state.get("scraped_content", []) if item.get("url")}
    updated = list(existing.values())

    for result in state.get("search_results", []):
        url = result.get("url", "")
        if not url or url in existing:
            continue

        content = await asyncio.to_thread(scrape_url, url, result.get("title", ""))
        existing[url] = content
        updated.append(content)

    await repository.upsert_scraped_content(job_id=state["job_id"], scraped_items=updated)

    return {
        "scraped_content": updated,
        "status": "running",
    }
