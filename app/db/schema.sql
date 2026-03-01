CREATE TABLE IF NOT EXISTS research_jobs (
    job_id UUID PRIMARY KEY,
    topic TEXT NOT NULL,
    depth VARCHAR(10) NOT NULL,
    max_sources INTEGER NOT NULL,
    output_format VARCHAR(10) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('queued', 'running', 'complete', 'error')),
    current_stage VARCHAR(30) NOT NULL CHECK (current_stage IN ('supervisor', 'web_search', 'scraper', 'summarizer', 'compiler')),
    iteration INTEGER NOT NULL DEFAULT 0,
    max_iterations INTEGER NOT NULL,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS job_search_queries (
    id SERIAL PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES research_jobs(job_id) ON DELETE CASCADE,
    iteration INTEGER NOT NULL,
    query_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (job_id, iteration, query_text)
);

CREATE TABLE IF NOT EXISTS job_search_results (
    id SERIAL PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES research_jobs(job_id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    title TEXT,
    snippet TEXT,
    iteration INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (job_id, url)
);

CREATE TABLE IF NOT EXISTS job_scraped_content (
    id SERIAL PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES research_jobs(job_id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    title TEXT,
    raw_text TEXT,
    scrape_success BOOLEAN NOT NULL,
    word_count INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (job_id, url)
);

CREATE TABLE IF NOT EXISTS job_source_summaries (
    id SERIAL PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES research_jobs(job_id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    title TEXT,
    key_findings JSONB NOT NULL,
    methodology TEXT,
    relevance_score DOUBLE PRECISION,
    publication_date TEXT,
    source_type VARCHAR(30),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (job_id, url)
);

CREATE TABLE IF NOT EXISTS job_reports (
    id SERIAL PRIMARY KEY,
    job_id UUID NOT NULL UNIQUE REFERENCES research_jobs(job_id) ON DELETE CASCADE,
    report_content TEXT NOT NULL,
    sources_used INTEGER,
    iterations_taken INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_research_jobs_status_updated_at
    ON research_jobs (status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_job_search_results_job_id
    ON job_search_results (job_id);

CREATE INDEX IF NOT EXISTS idx_job_scraped_content_job_id
    ON job_scraped_content (job_id);

CREATE INDEX IF NOT EXISTS idx_job_source_summaries_job_id_relevance
    ON job_source_summaries (job_id, relevance_score DESC);

CREATE INDEX IF NOT EXISTS idx_job_reports_job_id
    ON job_reports (job_id);
