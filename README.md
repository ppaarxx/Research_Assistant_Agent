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
- `job_reports.report_content` is stored as a JSON envelope (`schema_version`, `output_format`, `content_type`, `content`, `generated_at`) so web/mobile clients can render consistently.

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

## Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

`.env` reference:

```dotenv
# Required
GEMINI_API_KEY=your-gemini-api-key-here

# Database (use these exact values when running via Docker)
DATABASE_URL=postgresql://postgres:Parth%40321@db:5432/research_assistant_agent
DATABASE_ADMIN_URL=postgresql://postgres:Parth%40321@db:5432/postgres
DATABASE_NAME=research_assistant_agent

# Tuning
MAX_ITERATIONS=10
MAX_SOURCES=10
REQUEST_TIMEOUT=900
THINKING_BUDGET=10000

# Server
API_HOST=0.0.0.0
API_PORT=8000

# Models
SUPERVISOR_MODEL=gemini-2.5-flash
WORKER_MODEL=gemini-2.5-flash
```

> **Note:** When running locally (without Docker), change the hostname in `DATABASE_URL` and `DATABASE_ADMIN_URL` from `db` to `localhost`.

---

## Docker

### Run

```bash
docker compose up --build -d
```

This starts two containers:
- `research-assistant-api` — FastAPI app on port `8000`
- `research-assistant-db` — PostgreSQL 16

The API waits for the database health check to pass before starting.

### View logs

```bash
# All services
docker compose logs -f

# API only
docker compose logs -f api
```

### Stop

```bash
docker compose stop
```

### Stop and remove containers

```bash
docker compose down
```

### Stop, remove containers, and delete the database volume

```bash
docker compose down -v
rm -rf ./postgres_data
```

> ⚠️ This permanently deletes all stored research jobs and reports.

---

## Local Setup (without Docker)

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

Update `.env` to use `localhost` instead of `db` for the database host, then bootstrap the schema:

```bash
python -m app.db.init_db
```

### Run

```bash
uvicorn app.main:app --reload --port 8000
```

---

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

---

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