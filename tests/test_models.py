from app.models.request import ResearchRequest


def test_research_request_defaults():
    request = ResearchRequest(topic="Agentic AI in healthcare 2025")
    assert request.depth == "deep"
    assert request.output_format == "markdown"
