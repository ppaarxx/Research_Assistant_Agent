from __future__ import annotations

import json
from typing import Any

from google.genai import types

from app.agents.gemini_client import generate_content_async
from app.core.config import get_settings
from app.db.repository import repository
from app.graph.state import ResearchState


def _seed_queries(topic: str, depth: str) -> list[str]:
    base = [
        f"{topic} overview",
        f"{topic} latest research",
        f"{topic} case studies",
    ]
    if depth == "deep":
        base.extend(
            [
                f"{topic} systematic review",
                f"{topic} challenges and limitations",
            ]
        )
    return base[:5]


def _refined_queries(topic: str, summaries: list[dict[str, Any]]) -> list[str]:
    keywords: list[str] = []
    for summary in summaries[:5]:
        for finding in summary.get("key_findings", []):
            cleaned = str(finding).strip()
            if cleaned:
                keywords.append(cleaned)
            if len(keywords) >= 3:
                break
        if len(keywords) >= 3:
            break

    if not keywords:
        return [
            f"{topic} primary research 2024 2025",
            f"{topic} benchmark data",
            f"{topic} expert analysis",
        ]

    return [
        f"{topic} {keywords[0]}",
        f"{topic} {keywords[1] if len(keywords) > 1 else 'evidence'}",
        f"{topic} {keywords[2] if len(keywords) > 2 else 'outcomes'}",
    ]


def _metrics(state: ResearchState) -> tuple[int, float, int]:
    summaries = state.get("summaries", [])
    count = len(summaries)
    if count == 0:
        return 0, 0.0, 0

    scores = [float(s.get("relevance_score", 0.0) or 0.0) for s in summaries]
    avg = sum(scores) / len(scores)
    high_rel = len([s for s in scores if s >= 0.6])
    return count, avg, high_rel


def _build_supervisor_prompt(state: ResearchState) -> str:
    summary_count, avg_relevance, high_rel = _metrics(state)
    return (
        "You are a research supervisor managing a multi-agent pipeline.\n"
        "Decide the next best step.\n\n"
        f"Topic: {state['topic']}\n"
        f"Depth: {state['depth']}\n"
        f"Iteration: {state['iteration']} / {state['max_iterations']}\n"
        f"Search queries so far: {state['search_queries']}\n"
        f"Search results count: {len(state.get('search_results', []))}\n"
        f"Scraped sources count: {len(state.get('scraped_content', []))}\n"
        f"Summaries count: {summary_count}\n"
        f"Average relevance: {avg_relevance:.2f}\n"
        f"High relevance count (>=0.6): {high_rel}\n"
        "\nRouting rules:\n"
        "1) If this is the first cycle, route to web_search with 3-5 targeted queries.\n"
        "2) If summaries are insufficient (<3 high-relevance or avg<0.6), route to web_search with refined queries.\n"
        "3) If enough evidence exists or max iterations reached, route to compiler.\n"
        "4) scraper/summarizer are allowed for recovery only when prior step data exists but step not run.\n"
        "\nUse only route_to_agent function and keep reasoning concise."
    )


def _parse_function_call(response: Any) -> dict[str, Any] | None:
    if response is None:
        return None

    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            function_call = getattr(part, "function_call", None)
            if function_call is None:
                continue

            args = getattr(function_call, "args", {})
            if isinstance(args, dict):
                return args

            try:
                return dict(args)
            except Exception:
                pass

            try:
                return json.loads(str(args))
            except Exception:
                return None
    return None


def _heuristic_decision(state: ResearchState) -> dict[str, Any]:
    summary_count, avg_relevance, high_rel = _metrics(state)

    if state.get("final_report"):
        return {"next_agent": "END", "reasoning": "Report already generated."}

    if state["iteration"] >= state["max_iterations"]:
        return {
            "next_agent": "compiler",
            "reasoning": "Max iterations reached; compile best available evidence.",
        }

    if not state.get("search_queries"):
        return {
            "next_agent": "web_search",
            "reasoning": "Initial cycle requires web search.",
            "refined_queries": _seed_queries(state["topic"], state["depth"]),
        }

    if state.get("search_results") and not state.get("scraped_content"):
        return {
            "next_agent": "scraper",
            "reasoning": "Search results exist but no scraped content yet.",
        }

    if state.get("scraped_content") and not state.get("summaries"):
        return {
            "next_agent": "summarizer",
            "reasoning": "Scraped content exists but summaries are missing.",
        }

    enough = summary_count >= 3 and avg_relevance >= 0.6 and high_rel >= 3
    if enough:
        return {
            "next_agent": "compiler",
            "reasoning": "Quality and quantity thresholds reached.",
        }

    return {
        "next_agent": "web_search",
        "reasoning": "Need better or more sources; running refined search.",
        "refined_queries": _refined_queries(state["topic"], state.get("summaries", [])),
    }


async def supervisor_node(state: ResearchState) -> dict[str, Any]:
    settings = get_settings()
    fallback = _heuristic_decision(state)
    decision = fallback

    try:
        route_to_agent_fn = types.FunctionDeclaration(
            name="route_to_agent",
            description="Route the workflow to the next agent and optionally provide refined queries.",
            parameters={
                "type": "object",
                "properties": {
                    "next_agent": {
                        "type": "string",
                        "enum": ["web_search", "scraper", "summarizer", "compiler", "END"],
                    },
                    "reasoning": {"type": "string"},
                    "refined_queries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "3-5 refined web search queries when routing to web_search",
                    },
                },
                "required": ["next_agent", "reasoning"],
            },
        )

        config = types.GenerateContentConfig(
            tools=[types.Tool(function_declarations=[route_to_agent_fn])],
            thinking_config=types.ThinkingConfig(thinking_budget=settings.thinking_budget),
            temperature=1.0,
        )

        prompt = _build_supervisor_prompt(state)
        response = await generate_content_async(
            model=settings.supervisor_model,
            contents=prompt,
            config=config,
        )

        decision = _parse_function_call(response) or fallback
    except Exception:
        decision = fallback

    next_agent = str(decision.get("next_agent", fallback["next_agent"]))
    if next_agent not in {"web_search", "scraper", "summarizer", "compiler", "END"}:
        next_agent = fallback["next_agent"]

    reasoning = str(decision.get("reasoning", fallback.get("reasoning", "")))

    updates: dict[str, Any] = {
        "next_agent": next_agent,
        "supervisor_notes": reasoning,
        "status": "running",
    }

    if next_agent == "web_search":
        refined_queries = decision.get("refined_queries") or fallback.get("refined_queries")
        if not isinstance(refined_queries, list) or not refined_queries:
            refined_queries = _seed_queries(state["topic"], state["depth"])

        clean_queries = [str(q).strip() for q in refined_queries if str(q).strip()]
        updates["search_queries"] = clean_queries[:5]
        updates["iteration"] = min(state["iteration"] + 1, state["max_iterations"])
        await repository.upsert_search_queries(
            job_id=state["job_id"],
            iteration=int(updates["iteration"]),
            queries=updates["search_queries"],
        )

    db_stage = next_agent if next_agent in {"web_search", "scraper", "summarizer", "compiler"} else "supervisor"
    await repository.set_stage_and_iteration(
        job_id=state["job_id"],
        current_stage=db_stage,
        iteration=int(updates.get("iteration", state["iteration"])),
    )

    return updates
