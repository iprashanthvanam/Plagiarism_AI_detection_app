






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
    ai_detected_percentage FLOAT,
    web_source_percentage FLOAT,
    human_written_percentage FLOAT,
    analysis_summary TEXT,
    analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);



ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_type TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS size INTEGER;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS extracted_text TEXT;




