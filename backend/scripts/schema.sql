-- USERS TABLE
DROP TABLE IF EXISTS users CASCADE;

CREATE TABLE users (
    user_id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'student')),
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- DOCUMENTS TABLE
-- DOCUMENTS TABLE
DROP TABLE IF EXISTS documents CASCADE;

CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    content_type TEXT,  -- ✅ Added
    size INTEGER,       -- ✅ Added
    extracted_text TEXT, -- ✅ Added (Used in analysis)
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ANALYSIS RESULTS TABLE
DROP TABLE IF EXISTS analysis_results CASCADE;

CREATE TABLE analysis_results (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    analyzed_by TEXT,                          -- ✅ User who triggered the analysis
    ai_detected_percentage FLOAT,
    web_source_percentage FLOAT,
    human_written_percentage FLOAT,
    local_similarity_percentage FLOAT,         -- ✅ Internal DB similarity (separate from web)
    analysis_summary TEXT,
    matched_web_sources TEXT[],                -- ✅ JSON-encoded source list
    processing_time_seconds FLOAT,             -- ✅ Analysis runtime metrics
    analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);



ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_type TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS size INTEGER;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS extracted_text TEXT;

-- Add missing columns to analysis_results (for backward compatibility if table already exists)
ALTER TABLE analysis_results ADD COLUMN IF NOT EXISTS analyzed_by TEXT;
ALTER TABLE analysis_results ADD COLUMN IF NOT EXISTS local_similarity_percentage FLOAT;
ALTER TABLE analysis_results ADD COLUMN IF NOT EXISTS matched_web_sources TEXT[];
ALTER TABLE analysis_results ADD COLUMN IF NOT EXISTS processing_time_seconds FLOAT;

-- ============================================================
-- EXTENSIONS (must run BEFORE indexes that use them)
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================
-- INDEXES — CRITICAL FOR PERFORMANCE
-- ============================================================

-- Foreign key lookups
CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);
CREATE INDEX IF NOT EXISTS idx_analysis_results_doc_id ON analysis_results(document_id);
CREATE INDEX IF NOT EXISTS idx_analysis_results_analyzed_by ON analysis_results(analyzed_by);

-- Date-based retention queries (weekly cleanup)
CREATE INDEX IF NOT EXISTS idx_documents_upload_date ON documents(upload_date);

-- Full-text similarity search (pg_trgm trigram index)
-- Enables SIMILARITY() function and efficient text comparison
CREATE INDEX IF NOT EXISTS idx_documents_text_trgm ON documents USING gin(extracted_text gin_trgm_ops);

-- Composite index for common filter patterns
CREATE INDEX IF NOT EXISTS idx_documents_user_extracted ON documents(user_id, extracted_text) 
  WHERE extracted_text IS NOT NULL;

-- Analyze query performance
ANALYZE documents;
ANALYZE analysis_results;




