from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    ERROR = "error"


class ResearchJobResponse(BaseModel):
    job_id: str
    status: JobStatus
    topic: str
    message: str


class ResearchReportResponse(BaseModel):
    job_id: str
    status: JobStatus
    topic: str
    current_stage: Optional[str] = None
    updated_at: Optional[str] = None
    report: Optional[str] = None
    sources_used: Optional[int] = None
    iterations_taken: Optional[int] = None
    error: Optional[str] = None
