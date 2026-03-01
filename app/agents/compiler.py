from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.agents.gemini_client import extract_response_text, generate_content_async
from app.core.config import get_settings
from app.db.repository import repository
from app.graph.state import ResearchState


def _local_compile_markdown(topic: str, summaries: list[dict[str, Any]]) -> str:
    lines: list[str] = [
        f"# Research Report: {topic}",
        "",
        "## Executive Summary",
    ]

    if not summaries:
        lines.extend(
            [
                "Insufficient sources were gathered to produce a complete report.",
                "",
                "## Key Themes & Trends",
                "No reliable themes could be established.",
                "",
                "## Detailed Findings",
                "No source summaries available.",
                "",
                "## Knowledge Gaps & Future Research Directions",
                "More primary sources are required.",
                "",
                "## Sources",
                "None",
            ]
        )
        return "\n".join(lines)

    lines.append(
        "This report synthesizes the highest-relevance web sources collected by the research pipeline."
    )
    lines.extend(["", "## Key Themes & Trends"])

    top_findings: list[str] = []
    for summary in summaries[:5]:
        top_findings.extend(summary.get("key_findings", [])[:1])
    if not top_findings:
        top_findings = ["No common themes extracted from available content."]

    for finding in top_findings[:5]:
        lines.append(f"- {finding}")

    lines.extend(["", "## Detailed Findings"])
    for idx, summary in enumerate(summaries, start=1):
        lines.append(
            f"### [{idx}] {summary.get('title', 'Untitled')} (Relevance: {summary.get('relevance_score', 0):.2f})"
        )
        for finding in summary.get("key_findings", [])[:5]:
            lines.append(f"- {finding}")
        methodology = summary.get("methodology")
        if methodology:
            lines.append(f"- Methodology: {methodology}")
        pub_date = summary.get("publication_date")
        if pub_date:
            lines.append(f"- Publication Date: {pub_date}")
        lines.append(f"- URL: {summary.get('url', '')}")
        lines.append("")

    lines.extend(
        [
            "## Knowledge Gaps & Future Research Directions",
            "- Collect additional peer-reviewed sources for stronger evidence quality.",
            "- Validate contradictory findings through longitudinal or comparative studies.",
            "",
            "## Sources",
        ]
    )
    for idx, summary in enumerate(summaries, start=1):
        lines.append(f"[{idx}] {summary.get('title', 'Untitled')} - {summary.get('url', '')}")

    return "\n".join(lines)


def _local_compile_json(topic: str, summaries: list[dict[str, Any]]) -> str:
    payload = {
        "topic": topic,
        "executive_summary": (
            "Insufficient sources gathered." if not summaries else "Report compiled from collected summaries."
        ),
        "key_themes": [
            finding
            for summary in summaries[:5]
            for finding in summary.get("key_findings", [])[:1]
        ],
        "detailed_findings": summaries,
        "knowledge_gaps": [
            "Need more primary/peer-reviewed material" if not summaries else "Cross-validation across more sources is recommended"
        ],
        "sources": [
            {
                "title": s.get("title", "Untitled"),
                "url": s.get("url", ""),
                "relevance_score": s.get("relevance_score", 0.0),
            }
            for s in summaries
        ],
    }
    return json.dumps(payload, indent=2)


async def _compile_with_gemini(state: ResearchState, summaries: list[dict[str, Any]]) -> str | None:
    settings = get_settings()
    prompt = (
        "You are a senior research analyst. Compile a comprehensive report.\n"
        f"Topic: {state['topic']}\n"
        f"Output format: {state['output_format']}\n"
        "Use source citations [1], [2], etc.\n"
        "Sections required:\n"
        "1. Executive Summary\n"
        "2. Key Themes & Trends\n"
        "3. Detailed Findings\n"
        "4. Knowledge Gaps & Future Research Directions\n"
        "5. Sources\n\n"
        f"Summaries:\n{json.dumps(summaries, ensure_ascii=True, indent=2)}"
    )

    response = await generate_content_async(
        model=settings.worker_model,
        contents=prompt,
        config={"temperature": 1.0},
    )

    if response is None:
        return None

    text = extract_response_text(response)
    return text.strip() if text else None


def _build_report_storage_payload(*, topic: str, output_format: str, report: str) -> str:
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "topic": topic,
        "output_format": output_format,
        "content_type": "text/markdown" if output_format == "markdown" else "application/json",
        "content": report,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    if output_format == "json":
        try:
            payload["content_json"] = json.loads(report)
        except json.JSONDecodeError:
            payload["content_json"] = None

    return json.dumps(payload, ensure_ascii=True)


async def compiler_node(state: ResearchState) -> dict[str, Any]:
    await repository.set_stage_and_iteration(
        job_id=state["job_id"],
        current_stage="compiler",
        iteration=int(state["iteration"]),
    )

    summaries = sorted(
        state.get("summaries", []),
        key=lambda item: float(item.get("relevance_score", 0.0) or 0.0),
        reverse=True,
    )

    report = await _compile_with_gemini(state, summaries)

    if report is None:
        if state["output_format"] == "json":
            report = _local_compile_json(state["topic"], summaries)
        else:
            report = _local_compile_markdown(state["topic"], summaries)

    report_payload = _build_report_storage_payload(
        topic=state["topic"],
        output_format=state["output_format"],
        report=report,
    )

    await repository.upsert_report(
        job_id=state["job_id"],
        report_content=report_payload,
        sources_used=len(summaries),
        iterations_taken=int(state.get("iteration", 0) or 0),
    )
    await repository.set_job_complete(job_id=state["job_id"], current_stage="compiler")

    return {
        "final_report": report,
        "status": "complete",
        "next_agent": "END",
    }
