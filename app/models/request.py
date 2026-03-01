from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    topic: str = Field(
        min_length=5,
        max_length=500,
        description="Research topic or question",
    )
    depth: Literal["shallow", "deep"] = Field(default="deep")
    max_sources: int = Field(default=8, ge=3, le=20)
    output_format: Literal["markdown", "json"] = Field(default="markdown")
