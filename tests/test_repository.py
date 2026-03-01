from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("asyncpg")

import app.db.repository as repository_module


class FakePool:
    def __init__(self) -> None:
        self.execute_calls = []
        self.executemany_calls = []

    async def execute(self, query, *args):
        self.execute_calls.append((query, args))

    async def executemany(self, query, records):
        self.executemany_calls.append((query, records))


def test_upsert_search_queries_uses_on_conflict(monkeypatch):
    fake_pool = FakePool()
    monkeypatch.setattr(repository_module, "get_pool", lambda: fake_pool)

    asyncio.run(
        repository_module.repository.upsert_search_queries(
            job_id="11111111-1111-1111-1111-111111111111",
            iteration=1,
            queries=["query one", "query two"],
        )
    )

    assert len(fake_pool.executemany_calls) == 1
    query, records = fake_pool.executemany_calls[0]
    assert "ON CONFLICT (job_id, iteration, query_text) DO NOTHING" in query
    assert len(records) == 2


def test_set_job_complete_updates_status(monkeypatch):
    fake_pool = FakePool()
    monkeypatch.setattr(repository_module, "get_pool", lambda: fake_pool)

    asyncio.run(repository_module.repository.set_job_complete("11111111-1111-1111-1111-111111111111"))

    assert len(fake_pool.execute_calls) == 1
    query, _ = fake_pool.execute_calls[0]
    assert "SET status = 'complete'" in query
