from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.graph.nodes import (
    compiler_node,
    scraper_node,
    summarizer_node,
    supervisor_node,
    web_search_node,
)
from app.graph.state import ResearchState


def route_from_supervisor(state: ResearchState) -> str:
    next_agent = state.get("next_agent", "END")
    if next_agent in {"web_search", "scraper", "summarizer", "compiler", "END"}:
        return next_agent
    return "END"


def build_graph():
    graph = StateGraph(ResearchState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("web_search", web_search_node)
    graph.add_node("scraper", scraper_node)
    graph.add_node("summarizer", summarizer_node)
    graph.add_node("compiler", compiler_node)

    graph.set_entry_point("supervisor")

    graph.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "web_search": "web_search",
            "scraper": "scraper",
            "summarizer": "summarizer",
            "compiler": "compiler",
            "END": END,
        },
    )

    graph.add_edge("web_search", "scraper")
    graph.add_edge("scraper", "summarizer")
    graph.add_edge("summarizer", "supervisor")
    graph.add_edge("compiler", END)

    return graph.compile()


research_graph = build_graph()
