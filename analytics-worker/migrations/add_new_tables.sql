-- Migration: Add web_vitals, client_errors, referrer_stats tables
-- Run: npx wrangler d1 execute tech-econ-analytics-db --remote --file=./migrations/add_new_tables.sql

-- Web Vitals (LCP, FID, CLS, TTFB, INP)
CREATE TABLE IF NOT EXISTS web_vitals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    path TEXT,
    metric TEXT NOT NULL,
    value REAL,
    rating TEXT,
    timestamp INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_vitals_metric ON web_vitals(metric);
CREATE INDEX IF NOT EXISTS idx_vitals_path ON web_vitals(path);
CREATE INDEX IF NOT EXISTS idx_vitals_rating ON web_vitals(rating);

-- Client-side errors
CREATE TABLE IF NOT EXISTS client_errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    path TEXT,
    error_type TEXT,
    message TEXT,
    stack TEXT,
    timestamp INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_errors_path ON client_errors(path);
CREATE INDEX IF NOT EXISTS idx_errors_type ON client_errors(error_type);

-- Referrer source tracking
CREATE TABLE IF NOT EXISTS referrer_stats (
    source TEXT PRIMARY KEY,
    session_count INTEGER DEFAULT 1,
    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP
);
