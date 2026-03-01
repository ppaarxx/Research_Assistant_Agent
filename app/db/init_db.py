from __future__ import annotations

import asyncio
import re
from pathlib import Path
from urllib.parse import urlparse

import asyncpg

from app.core.config import get_settings


_VALID_DB_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_db_name(name: str) -> str:
    if not _VALID_DB_NAME.match(name):
        raise ValueError(f"Invalid DATABASE_NAME '{name}'. Use letters, numbers, and underscores only.")
    return name


async def _ensure_database_exists(admin_url: str, database_name: str) -> None:
    conn = await asyncpg.connect(dsn=admin_url)
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", database_name)
        if not exists:
            db_ident = '"' + database_name.replace('"', '""') + '"'
            await conn.execute(f"CREATE DATABASE {db_ident}")
    finally:
        await conn.close()


async def _apply_schema(database_url: str) -> None:
    schema_path = Path(__file__).with_name("schema.sql")
    schema_sql = schema_path.read_text(encoding="utf-8")

    conn = await asyncpg.connect(dsn=database_url)
    try:
        await conn.execute(schema_sql)
    finally:
        await conn.close()


async def init_db() -> None:
    settings = get_settings()

    if not settings.database_admin_url:
        raise RuntimeError("DATABASE_ADMIN_URL is required for DB bootstrap.")
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required for DB bootstrap.")

    database_name = _validate_db_name(settings.database_name)
    parsed_db_name = urlparse(settings.database_url).path.lstrip("/")
    if parsed_db_name != database_name:
        raise RuntimeError(
            "DATABASE_URL must point to DATABASE_NAME "
            f"('{database_name}'), got '{parsed_db_name or '<empty>'}'."
        )

    await _ensure_database_exists(settings.database_admin_url, database_name)
    await _apply_schema(settings.database_url)


def main() -> None:
    asyncio.run(init_db())


if __name__ == "__main__":
    main()
