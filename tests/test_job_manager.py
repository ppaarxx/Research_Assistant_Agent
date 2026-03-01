import pytest

pytest.importorskip("asyncpg")

from app.services.job_manager import JobManager


def test_normalize_row_extracts_report_content_from_storage_payload():
    row = {
        "job_id": "11111111-1111-1111-1111-111111111111",
        "topic": "Agentic AI",
        "status": "complete",
        "current_stage": "compiler",
        "iteration": 2,
        "updated_at": "2026-03-01T00:00:00+00:00",
        "report_content": '{"schema_version":"1.0","content":"# Title\\nBody"}',
        "sources_used": 3,
        "iterations_taken": 2,
        "error_message": None,
    }

    normalized = JobManager._normalize_row(row)
    assert normalized["report"] == "# Title\nBody"
