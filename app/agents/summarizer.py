from __future__ import annotations

import json
from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError

from app.agents.gemini_client import extract_response_text, generate_content_async
from app.core.config import get_settings
from app.db.repository import repository
from app.graph.state import ResearchState


class SourceSummarySchema(BaseModel):
    title: str = Field(description="Title of the article or paper")
    url: str = Field(description="Source URL")
    key_findings: list[str] = Field(description="3 to 5 key findings or insights")
    methodology: Optional[str] = Field(default=None)
    relevance_score: float = Field(description="Score from 0.0 to 1.0")
    publication_date: Optional[str] = Field(default=None)
    source_type: str = Field(
        description="Type: research_paper | news_article | blog | documentation | other"
    )


def _clamp_score(value: float) -> float:
    return max(0.0, min(1.0, value))


def _local_fallback_summary(topic: str, item: dict[str, Any]) -> dict[str, Any]:
    raw = item.get("raw_text", "")
    findings: list[str] = []

    if raw:
        sentences = [s.strip() for s in raw.split(".") if s.strip()]
        findings = [f"{s}." for s in sentences[:3]]

    if not findings:
        findings = ["Could not extract enough content from this source."]

    relevance = 0.4
    if topic.lower() in raw.lower():
        relevance = 0.65

    return {
        "title": item.get("title", "Untitled source"),
        "url": item.get("url", ""),
        "key_findings": findings,
        "methodology": None,
        "relevance_score": relevance,
        "publication_date": None,
        "source_type": "other",
    }


async def _summarize_with_gemini(topic: str, item: dict[str, Any]) -> dict[str, Any] | None:
    settings = get_settings()

    prompt = (
        "You are a research analyst. Read the web content and return a strict JSON object.\n"
        f"Topic: {topic}\n"
        f"Source URL: {item.get('url', '')}\n"
        "Rules:\n"
        "- Keep key_findings concise and factual\n"
        "- Score relevance from 0.0 to 1.0\n"
        "- Use source_type from allowed values\n\n"
        "Content:\n"
        f"{item.get('raw_text', '')}\n"
    )

    config = {
        "response_mime_type": "application/json",
        "response_json_schema": SourceSummarySchema.model_json_schema(),
        "temperature": 0.1,
    }

    response = await generate_content_async(
        model=settings.worker_model,
        contents=prompt,
        config=config,
    )

    if response is None:
        return None

    text = extract_response_text(response)
    if not text:
        return None

    try:
        parsed = SourceSummarySchema.model_validate_json(text)
        payload = parsed.model_dump()
        payload["relevance_score"] = _clamp_score(float(payload.get("relevance_score", 0.0)))
        if not payload.get("url"):
            payload["url"] = item.get("url", "")
        if not payload.get("title"):
            payload["title"] = item.get("title", "Untitled source")
        if not payload.get("key_findings"):
            payload["key_findings"] = ["No key findings extracted."]
        return payload
    except (ValidationError, json.JSONDecodeError, ValueError):
        return None


async def summarizer_node(state: ResearchState) -> dict[str, Any]:
    await repository.set_stage_and_iteration(
        job_id=state["job_id"],
        current_stage="summarizer",
        iteration=int(state["iteration"]),
    )

    existing = {summary["url"]: summary for summary in state.get("summaries", []) if summary.get("url")}
    updated = list(existing.values())

    for item in state.get("scraped_content", []):
        if not item.get("scrape_success"):
            continue

        url = item.get("url", "")
        if not url or url in existing:
            continue

        if not item.get("raw_text"):
            continue

        summary = await _summarize_with_gemini(state["topic"], item)
        if summary is None:
            summary = _local_fallback_summary(state["topic"], item)

        summary["relevance_score"] = _clamp_score(float(summary.get("relevance_score", 0.0)))

        existing[url] = summary
        updated.append(summary)

    await repository.upsert_source_summaries(job_id=state["job_id"], summaries=updated)

    return {
        "summaries": updated,
        "status": "running",
    }
