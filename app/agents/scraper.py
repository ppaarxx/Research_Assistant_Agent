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
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
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

# Minimum number of words for a page to be considered valid content.
# Pages below this threshold are almost certainly bot-detection walls,
# empty pages, or redirect pages with no research value.
MIN_WORD_COUNT = 50

# Phrases that strongly indicate the page is a bot-detection / CAPTCHA wall.
# If any of these appear in the first 300 characters of extracted text,
# the scrape is marked as failed regardless of word count.
BOT_DETECTION_PHRASES = [
    "verifying you are human",
    "verify you are human",
    "enable javascript and cookies",
    "please enable javascript",
    "checking your browser",
    "ddos protection by cloudflare",
    "one more step",
    "please complete the security check",
    "access denied",
    "403 forbidden",
    "this page requires javascript",
    "loading...",
    "just a moment",
    "please wait while we verify",
]


def _is_bot_wall(text: str) -> bool:
    """Return True if the extracted text looks like a bot-detection page."""
    sample = text[:300].lower()
    return any(phrase in sample for phrase in BOT_DETECTION_PHRASES)


def scrape_url(url: str, fallback_title: str = "") -> ScrapedContent:
    settings = get_settings()
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=settings.request_timeout,
            allow_redirects=True,
        )
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
        word_count = len(words)

        # --- Guard 1: Bot / CAPTCHA wall detection ---
        # Check before truncation so the full leading text is available.
        if _is_bot_wall(text):
            return {
                "url": url,
                "title": fallback_title,
                "raw_text": "",
                "scrape_success": False,
                "word_count": word_count,
            }

        # --- Guard 2: Minimum content threshold ---
        # Pages with fewer than MIN_WORD_COUNT words are empty shells,
        # error pages, or pure JS apps that rendered nothing useful.
        if word_count < MIN_WORD_COUNT:
            return {
                "url": url,
                "title": fallback_title,
                "raw_text": "",
                "scrape_success": False,
                "word_count": word_count,
            }

        truncated = " ".join(words[:8000])

        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()

        return {
            "url": url,
            "title": title or fallback_title,
            "raw_text": truncated,
            "scrape_success": True,
            "word_count": word_count,
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

    existing = {
        item["url"]: item
        for item in state.get("scraped_content", [])
        if item.get("url")
    }
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