from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from app.db.repository import repository


class JobManager:
    async def create_job(
        self,
        *,
        topic: str,
        depth: str,
        max_sources: int,
        output_format: str,
        max_iterations: int,
    ) -> str:
        job_id = str(uuid4())
        await repository.create_job(
            job_id=job_id,
            topic=topic,
            depth=depth,
            max_sources=max_sources,
            output_format=output_format,
            max_iterations=max_iterations,
        )
        return job_id

    async def set_job_running(self, job_id: str) -> None:
        await repository.set_job_running(job_id)

    async def set_stage_and_iteration(self, job_id: str, current_stage: str, iteration: int) -> None:
        await repository.set_stage_and_iteration(job_id, current_stage, iteration)

    async def set_job_error(self, job_id: str, error_message: str) -> None:
        await repository.set_job_error(job_id, error_message)

    async def set_job_complete(self, job_id: str) -> None:
        await repository.set_job_complete(job_id)

    async def finalize_job_from_state(self, job_id: str, state: dict[str, Any]) -> None:
        report = state.get("final_report")
        if report:
            await repository.upsert_report(
                job_id=job_id,
                report_content=str(report),
                sources_used=len(state.get("summaries", [])),
                iterations_taken=int(state.get("iteration", 0) or 0),
            )
        await repository.set_job_complete(job_id)

    async def get_job_overview(self, job_id: str) -> dict[str, Any] | None:
        row = await repository.get_job_overview(job_id)
        if row is None:
            return None
        return self._normalize_row(row)

    async def get_job_report(self, job_id: str) -> dict[str, Any] | None:
        row = await repository.get_job_report(job_id)
        if row is None:
            return None
        return self._normalize_row(row)

    @staticmethod
    def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
        updated_at = row.get("updated_at")
        if isinstance(updated_at, datetime):
            updated_at_value = updated_at.isoformat()
        else:
            updated_at_value = str(updated_at) if updated_at else None

        return {
            "job_id": row.get("job_id"),
            "topic": row.get("topic"),
            "status": row.get("status"),
            "current_stage": row.get("current_stage"),
            "iteration": row.get("iteration"),
            "updated_at": updated_at_value,
            "report": row.get("report_content"),
            "sources_used": row.get("sources_used"),
            "iterations_taken": row.get("iterations_taken"),
            "error": row.get("error_message"),
        }


job_manager = JobManager()
