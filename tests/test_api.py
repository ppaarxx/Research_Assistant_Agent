from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("langgraph")
pytest.importorskip("asyncpg")

import app.routers.research as research_router
from app.main import app
from fastapi.testclient import TestClient


app.router.on_startup.clear()
app.router.on_shutdown.clear()
client = TestClient(app)


async def _fake_run_research_job(job_id: str, request):
    return None


async def _fake_create_job(*, topic: str, depth: str, max_sources: int, output_format: str, max_iterations: int):
    return "11111111-1111-1111-1111-111111111111"


async def _fake_get_job_overview(job_id: str):
    return {
        "job_id": job_id,
        "topic": "Agentic AI in healthcare 2025",
        "status": "queued",
        "current_stage": "supervisor",
        "iteration": 0,
        "updated_at": "2026-03-01T00:00:00+00:00",
        "report": None,
        "sources_used": 0,
        "iterations_taken": 0,
        "error": None,
    }


def test_start_research_returns_job(monkeypatch):
    monkeypatch.setattr(research_router, "run_research_job", _fake_run_research_job)
    monkeypatch.setattr(research_router.job_manager, "create_job", _fake_create_job)
    monkeypatch.setattr(research_router.job_manager, "get_job_overview", _fake_get_job_overview)
    monkeypatch.setattr(research_router, "get_settings", lambda: SimpleNamespace(max_iterations=3))

    payload = {
        "topic": "Agentic AI in healthcare 2025",
        "depth": "deep",
        "max_sources": 8,
        "output_format": "markdown",
    }

    response = client.post("/research", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body["job_id"] == "11111111-1111-1111-1111-111111111111"
    assert body["status"] == "queued"

    status_response = client.get(f"/research/{body['job_id']}")
    assert status_response.status_code == 200
    status_body = status_response.json()
    assert status_body["topic"] == payload["topic"]
    assert status_body["current_stage"] == "supervisor"
