from __future__ import annotations

from typing import List, Optional, TypedDict

from app.core.config import Settings
from app.models.request import ResearchRequest


class SearchResult(TypedDict):
    url: str
    title: str
    snippet: str


class ScrapedContent(TypedDict):
    url: str
    title: str
    raw_text: str
    scrape_success: bool
    word_count: int


class SourceSummary(TypedDict):
    url: str
    title: str
    key_findings: List[str]
    methodology: Optional[str]
    relevance_score: float
    publication_date: Optional[str]
    source_type: str


class ResearchState(TypedDict):
    job_id: str
    topic: str
    depth: str
    max_sources: int
    output_format: str
    max_iterations: int

    search_queries: List[str]
    iteration: int
    supervisor_notes: str
    next_agent: str

    search_results: List[SearchResult]
    scraped_content: List[ScrapedContent]
    summaries: List[SourceSummary]

    final_report: Optional[str]
    status: str
    error_message: Optional[str]


def build_initial_state(request: ResearchRequest, settings: Settings, job_id: str) -> ResearchState:
    return {
        "job_id": job_id,
        "topic": request.topic,
        "depth": request.depth,
        "max_sources": request.max_sources,
        "output_format": request.output_format,
        "max_iterations": settings.max_iterations,
        "search_queries": [],
        "iteration": 0,
        "supervisor_notes": "",
        "next_agent": "web_search",
        "search_results": [],
        "scraped_content": [],
        "summaries": [],
        "final_report": None,
        "status": "running",
        "error_message": None,
    }
