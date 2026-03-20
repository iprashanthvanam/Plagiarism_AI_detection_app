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
DROP TABLE IF EXISTS documents CASCADE;

CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    content_type TEXT,
    size INTEGER,
    extracted_text TEXT,              -- ✅ Changed: removed LIMIT, use TEXT
    extracted_text_length INTEGER,    -- ✅ NEW: track actual stored length
    extraction_complete BOOLEAN DEFAULT false,  -- ✅ NEW: validate full extraction
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ANALYSIS RESULTS TABLE
DROP TABLE IF EXISTS analysis_results CASCADE;

CREATE TABLE analysis_results (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    analyzed_by TEXT,
    ai_detected_percentage FLOAT,
    web_source_percentage FLOAT,
    local_similarity_percentage FLOAT,
    human_written_percentage FLOAT,
    analysis_summary TEXT,
    matched_web_sources TEXT[],
    sentence_source_map JSONB,
    processing_time_seconds FLOAT,
    analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- EXTENSIONS
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);
CREATE INDEX IF NOT EXISTS idx_documents_extraction_complete ON documents(extraction_complete);
CREATE INDEX IF NOT EXISTS idx_analysis_results_doc_id ON analysis_results(document_id);
CREATE INDEX IF NOT EXISTS idx_analysis_results_analyzed_by ON analysis_results(analyzed_by);
CREATE INDEX IF NOT EXISTS idx_documents_upload_date ON documents(upload_date);
CREATE INDEX IF NOT EXISTS idx_documents_text_trgm ON documents USING gin(extracted_text gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_documents_user_extracted ON documents(user_id, extraction_complete) 
  WHERE extraction_complete = true;

ANALYZE documents;
ANALYZE analysis_results;




