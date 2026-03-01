from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os

from dotenv import load_dotenv


load_dotenv()


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str | None
    database_url: str
    database_admin_url: str
    database_name: str
    max_iterations: int
    max_sources: int
    request_timeout: int
    thinking_budget: int
    api_host: str
    api_port: int
    supervisor_model: str
    worker_model: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        database_url=os.getenv("DATABASE_URL", ""),
        database_admin_url=os.getenv("DATABASE_ADMIN_URL", ""),
        database_name=os.getenv("DATABASE_NAME", "research_assistant_agent"),
        max_iterations=_get_int("MAX_ITERATIONS", 3),
        max_sources=_get_int("MAX_SOURCES", 10),
        request_timeout=_get_int("REQUEST_TIMEOUT", 900),
        thinking_budget=_get_int("THINKING_BUDGET", 10000),
        api_host=os.getenv("API_HOST", "0.0.0.0"),
        api_port=_get_int("API_PORT", 8000),
        supervisor_model=os.getenv("SUPERVISOR_MODEL", "gemini-2.5-flash"),
        worker_model=os.getenv("WORKER_MODEL", "gemini-2.5-flash"),
    )
