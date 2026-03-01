from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.core.config import get_settings
from app.graph.graph_builder import research_graph
from app.graph.state import build_initial_state
from app.models.request import ResearchRequest
from app.models.response import JobStatus, ResearchJobResponse, ResearchReportResponse
from app.services.job_manager import job_manager


router = APIRouter(prefix="/research", tags=["research"])


async def _run_graph(initial_state: dict[str, Any]) -> dict[str, Any]:
    if hasattr(research_graph, "ainvoke"):
        return await research_graph.ainvoke(initial_state)
    return await asyncio.to_thread(research_graph.invoke, initial_state)


async def run_research_job(job_id: str, request: ResearchRequest) -> None:
    settings = get_settings()
    state = build_initial_state(request, settings, job_id=job_id)

    await job_manager.set_job_running(job_id)
    await job_manager.set_stage_and_iteration(job_id, "supervisor", 0)

    try:
        result = await _run_graph(state)
        has_final_report = bool(result.get("final_report"))

        status = str(result.get("status", JobStatus.COMPLETE.value))
        if status == JobStatus.ERROR.value and not has_final_report:
            await job_manager.set_job_error(
                job_id,
                str(result.get("error_message") or "Research graph returned an error status."),
            )
            return

        if result.get("error_message") and not has_final_report:
            await job_manager.set_job_error(job_id, str(result.get("error_message")))
            return

        await job_manager.finalize_job_from_state(job_id, result)
    except Exception as exc:
        await job_manager.set_job_error(job_id, str(exc))


@router.post("", response_model=ResearchJobResponse)
async def start_research(request: ResearchRequest, background_tasks: BackgroundTasks) -> ResearchJobResponse:
    settings = get_settings()
    job_id = await job_manager.create_job(
        topic=request.topic,
        depth=request.depth,
        max_sources=request.max_sources,
        output_format=request.output_format,
        max_iterations=settings.max_iterations,
    )
    background_tasks.add_task(run_research_job, job_id, request)

    return ResearchJobResponse(
        job_id=job_id,
        status=JobStatus.QUEUED,
        topic=request.topic,
        message="Research job queued. Poll /research/{job_id} for progress.",
    )


@router.get("/{job_id}", response_model=ResearchReportResponse)
async def get_job_status(job_id: str) -> ResearchReportResponse:
    job = await job_manager.get_job_overview(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    status = JobStatus(job["status"])

    return ResearchReportResponse(
        job_id=job_id,
        status=status,
        topic=str(job["topic"]),
        current_stage=job.get("current_stage"),
        updated_at=job.get("updated_at"),
        report=job.get("report") if status == JobStatus.COMPLETE else None,
        sources_used=job.get("sources_used"),
        iterations_taken=job.get("iterations_taken"),
        error=job.get("error"),
    )


@router.get("/{job_id}/report", response_model=ResearchReportResponse)
async def get_research_report(job_id: str) -> ResearchReportResponse:
    job = await job_manager.get_job_report(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return ResearchReportResponse(
        job_id=job_id,
        status=JobStatus(job["status"]),
        topic=str(job["topic"]),
        current_stage=job.get("current_stage"),
        updated_at=job.get("updated_at"),
        report=job.get("report"),
        sources_used=job.get("sources_used"),
        iterations_taken=job.get("iterations_taken"),
        error=job.get("error"),
    )
