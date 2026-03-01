from __future__ import annotations

import json
from typing import Any

from app.db.connection import get_pool


class ResearchRepository:
    async def create_job(
        self,
        *,
        job_id: str,
        topic: str,
        depth: str,
        max_sources: int,
        output_format: str,
        max_iterations: int,
    ) -> None:
        pool = get_pool()
        await pool.execute(
            """
            INSERT INTO research_jobs (
                job_id,
                topic,
                depth,
                max_sources,
                output_format,
                status,
                current_stage,
                iteration,
                max_iterations,
                error_message
            )
            VALUES ($1::uuid, $2, $3, $4, $5, 'queued', 'supervisor', 0, $6, NULL)
            ON CONFLICT (job_id) DO UPDATE SET
                topic = EXCLUDED.topic,
                depth = EXCLUDED.depth,
                max_sources = EXCLUDED.max_sources,
                output_format = EXCLUDED.output_format,
                status = 'queued',
                current_stage = 'supervisor',
                iteration = 0,
                max_iterations = EXCLUDED.max_iterations,
                error_message = NULL,
                updated_at = NOW()
            """,
            job_id,
            topic,
            depth,
            max_sources,
            output_format,
            max_iterations,
        )

    async def set_job_running(self, job_id: str) -> None:
        pool = get_pool()
        await pool.execute(
            """
            UPDATE research_jobs
            SET status = 'running', error_message = NULL, updated_at = NOW()
            WHERE job_id = $1::uuid
            """,
            job_id,
        )

    async def set_stage_and_iteration(self, job_id: str, current_stage: str, iteration: int) -> None:
        pool = get_pool()
        await pool.execute(
            """
            UPDATE research_jobs
            SET current_stage = $2, iteration = $3, updated_at = NOW()
            WHERE job_id = $1::uuid
            """,
            job_id,
            current_stage,
            iteration,
        )

    async def set_job_error(self, job_id: str, error_message: str) -> None:
        pool = get_pool()
        await pool.execute(
            """
            UPDATE research_jobs
            SET status = 'error', error_message = $2, updated_at = NOW()
            WHERE job_id = $1::uuid
            """,
            job_id,
            error_message,
        )

    async def set_job_complete(self, job_id: str, current_stage: str = "compiler") -> None:
        pool = get_pool()
        await pool.execute(
            """
            UPDATE research_jobs
            SET status = 'complete', current_stage = $2, error_message = NULL, updated_at = NOW()
            WHERE job_id = $1::uuid
            """,
            job_id,
            current_stage,
        )

    async def upsert_search_queries(self, job_id: str, iteration: int, queries: list[str]) -> None:
        if not queries:
            return

        pool = get_pool()
        records = [(job_id, iteration, query) for query in queries]
        await pool.executemany(
            """
            INSERT INTO job_search_queries (job_id, iteration, query_text)
            VALUES ($1::uuid, $2, $3)
            ON CONFLICT (job_id, iteration, query_text) DO NOTHING
            """,
            records,
        )

    async def upsert_search_results(self, job_id: str, iteration: int, results: list[dict[str, Any]]) -> None:
        if not results:
            return

        pool = get_pool()
        records = [
            (
                job_id,
                str(item.get("url", "")),
                str(item.get("title", "")) or None,
                str(item.get("snippet", "")) or None,
                iteration,
            )
            for item in results
            if str(item.get("url", "")).strip()
        ]

        if not records:
            return

        await pool.executemany(
            """
            INSERT INTO job_search_results (job_id, url, title, snippet, iteration)
            VALUES ($1::uuid, $2, $3, $4, $5)
            ON CONFLICT (job_id, url) DO UPDATE
            SET title = EXCLUDED.title,
                snippet = EXCLUDED.snippet,
                iteration = EXCLUDED.iteration
            """,
            records,
        )

    async def upsert_scraped_content(self, job_id: str, scraped_items: list[dict[str, Any]]) -> None:
        if not scraped_items:
            return

        pool = get_pool()
        records = [
            (
                job_id,
                str(item.get("url", "")),
                str(item.get("title", "")) or None,
                str(item.get("raw_text", "")),
                bool(item.get("scrape_success", False)),
                int(item.get("word_count", 0) or 0),
            )
            for item in scraped_items
            if str(item.get("url", "")).strip()
        ]

        if not records:
            return

        await pool.executemany(
            """
            INSERT INTO job_scraped_content (
                job_id,
                url,
                title,
                raw_text,
                scrape_success,
                word_count
            )
            VALUES ($1::uuid, $2, $3, $4, $5, $6)
            ON CONFLICT (job_id, url) DO UPDATE
            SET title = EXCLUDED.title,
                raw_text = EXCLUDED.raw_text,
                scrape_success = EXCLUDED.scrape_success,
                word_count = EXCLUDED.word_count
            """,
            records,
        )

    async def upsert_source_summaries(self, job_id: str, summaries: list[dict[str, Any]]) -> None:
        if not summaries:
            return

        pool = get_pool()
        records = []
        for item in summaries:
            url = str(item.get("url", "")).strip()
            if not url:
                continue

            findings = item.get("key_findings", [])
            if not isinstance(findings, list):
                findings = []

            records.append(
                (
                    job_id,
                    url,
                    str(item.get("title", "")) or None,
                    json.dumps(findings, ensure_ascii=True),
                    str(item.get("methodology", "")) or None,
                    float(item.get("relevance_score", 0.0) or 0.0),
                    str(item.get("publication_date", "")) or None,
                    str(item.get("source_type", "other")) or "other",
                )
            )

        if not records:
            return

        await pool.executemany(
            """
            INSERT INTO job_source_summaries (
                job_id,
                url,
                title,
                key_findings,
                methodology,
                relevance_score,
                publication_date,
                source_type
            )
            VALUES ($1::uuid, $2, $3, $4::jsonb, $5, $6, $7, $8)
            ON CONFLICT (job_id, url) DO UPDATE
            SET title = EXCLUDED.title,
                key_findings = EXCLUDED.key_findings,
                methodology = EXCLUDED.methodology,
                relevance_score = EXCLUDED.relevance_score,
                publication_date = EXCLUDED.publication_date,
                source_type = EXCLUDED.source_type
            """,
            records,
        )

    async def upsert_report(
        self,
        job_id: str,
        report_content: str,
        sources_used: int,
        iterations_taken: int,
    ) -> None:
        pool = get_pool()
        await pool.execute(
            """
            INSERT INTO job_reports (job_id, report_content, sources_used, iterations_taken)
            VALUES ($1::uuid, $2, $3, $4)
            ON CONFLICT (job_id) DO UPDATE
            SET report_content = EXCLUDED.report_content,
                sources_used = EXCLUDED.sources_used,
                iterations_taken = EXCLUDED.iterations_taken
            """,
            job_id,
            report_content,
            sources_used,
            iterations_taken,
        )

    async def get_job_overview(self, job_id: str) -> dict[str, Any] | None:
        pool = get_pool()
        row = await pool.fetchrow(
            """
            SELECT
                j.job_id::text AS job_id,
                j.topic,
                j.status,
                j.current_stage,
                j.iteration,
                j.max_iterations,
                j.error_message,
                j.updated_at,
                r.report_content,
                COALESCE(r.sources_used, (
                    SELECT COUNT(*)::int
                    FROM job_source_summaries s
                    WHERE s.job_id = j.job_id
                )) AS sources_used,
                COALESCE(r.iterations_taken, j.iteration) AS iterations_taken
            FROM research_jobs j
            LEFT JOIN job_reports r ON r.job_id = j.job_id
            WHERE j.job_id = $1::uuid
            """,
            job_id,
        )
        return dict(row) if row else None

    async def get_job_report(self, job_id: str) -> dict[str, Any] | None:
        pool = get_pool()
        row = await pool.fetchrow(
            """
            SELECT
                j.job_id::text AS job_id,
                j.topic,
                j.status,
                j.current_stage,
                j.iteration,
                j.error_message,
                j.updated_at,
                r.report_content,
                r.sources_used,
                r.iterations_taken
            FROM research_jobs j
            LEFT JOIN job_reports r ON r.job_id = j.job_id
            WHERE j.job_id = $1::uuid
            """,
            job_id,
        )
        return dict(row) if row else None


repository = ResearchRepository()
