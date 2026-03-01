# Multi-Agent Research Assistant

Autonomous research pipeline built with Python, LangGraph, Gemini 2.5 Flash, FastAPI, and PostgreSQL persistence.

## What Changed

- Job lifecycle is now persisted in PostgreSQL (no in-memory job dict).
- Every stage writes auditable artifacts:
  - `research_jobs`
  - `job_search_queries`
  - `job_search_results`
  - `job_scraped_content`
  - `job_source_summaries`
  - `job_reports`
- `/research/{job_id}` now includes live stage metadata: `current_stage`, `updated_at`.

## Project Structure

```text
app/
  agents/
  core/
  db/
    connection.py
    init_db.py
    repository.py
    schema.sql
  graph/
  models/
  routers/
  services/
tests/
requirements.txt
.env.example
```

## Setup

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
# source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

Set required env values in `.env`:

- `GEMINI_API_KEY`
- `DATABASE_ADMIN_URL`
- `DATABASE_URL`
- Optional: `DATABASE_NAME` (defaults to `research_assistant_agent`)

## Database Bootstrap

Run one-time (or safely re-run):

```bash
python -m app.db.init_db
```

At app startup, DB bootstrap and pool initialization also run automatically.

## Run

```bash
uvicorn app.main:app --reload --port 8000
```

## API

### 1. Start a research job

```bash
curl -X POST http://127.0.0.1:8000/research \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Agentic AI in healthcare 2025",
    "depth": "deep",
    "max_sources": 8,
    "output_format": "markdown"
  }'
```

### 2. Poll status (with stage metadata)

```bash
curl http://127.0.0.1:8000/research/{job_id}
```

### 3. Get final report

```bash
curl http://127.0.0.1:8000/research/{job_id}/report
```

## Live SQL Inspection

```sql
SELECT job_id, topic, status, current_stage, iteration, created_at
FROM research_jobs
ORDER BY created_at DESC;

SELECT COUNT(*)
FROM job_search_results
WHERE job_id = 'YOUR-JOB-ID';

SELECT title, relevance_score, source_type
FROM job_source_summaries
WHERE job_id = 'YOUR-JOB-ID'
ORDER BY relevance_score DESC;

SELECT report_content
FROM job_reports
WHERE job_id = 'YOUR-JOB-ID';
```
