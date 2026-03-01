from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from app.db.connection import close_pool, init_pool
from app.db.init_db import init_db
from app.routers.research import router as research_router


app = FastAPI(
    title="Multi-Agent Research Assistant",
    description="Autonomous research pipeline using LangGraph + Gemini",
    version="1.0.0",
)


@app.on_event("startup")
async def startup() -> None:
    await init_db()
    await init_pool()


@app.on_event("shutdown")
async def shutdown() -> None:
    await close_pool()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(research_router)


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )