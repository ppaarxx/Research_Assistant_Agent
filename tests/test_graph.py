import pytest

pytest.importorskip("langgraph")
pytest.importorskip("asyncpg")

from app.graph.graph_builder import route_from_supervisor


def test_route_from_supervisor_valid():
    state = {"next_agent": "web_search"}
    assert route_from_supervisor(state) == "web_search"


def test_route_from_supervisor_invalid_defaults_to_end():
    state = {"next_agent": "unknown"}
    assert route_from_supervisor(state) == "END"
