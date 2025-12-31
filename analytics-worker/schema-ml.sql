-- ML Schema Additions for Tech-Econ Analytics
-- Run: wrangler d1 execute tech-econ-analytics-db --remote --file=./schema-ml.sql

-- Session sequences for collaborative filtering (GRU4Rec, SASRec)
CREATE TABLE IF NOT EXISTS session_sequences (
    session_id TEXT PRIMARY KEY,
    page_sequence TEXT,          -- JSON: [{pid, ts, dwell}, ...]
    click_sequence TEXT,         -- JSON: [{from, to, ts, el}, ...]
    item_sequence TEXT,          -- JSON: [{name, section, ts}, ...]
    search_sequence TEXT,        -- JSON: [{q, qid, ts}, ...]
    duration_ms INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sequences_created ON session_sequences(created_at);

-- Search sessions for learning-to-rank
CREATE TABLE IF NOT EXISTS search_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    query_id TEXT UNIQUE,
    query TEXT,
    results_shown TEXT,          -- JSON: [{id, position}, ...]
    clicks TEXT,                 -- JSON: [{id, position, dwellMs}, ...]
    reformulation_of TEXT,       -- Previous query_id if reformulation
    abandonment_type TEXT,       -- 'good', 'bad', 'unknown', NULL (clicked)
    dwell_ms INTEGER,
    scroll_depth INTEGER,
    timestamp INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_search_session ON search_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_search_query ON search_sessions(query);
CREATE INDEX IF NOT EXISTS idx_search_abandon ON search_sessions(abandonment_type);

-- Per-item dwell time for engagement analysis
CREATE TABLE IF NOT EXISTS content_dwell (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    name TEXT NOT NULL,
    section TEXT,
    dwell_ms INTEGER,
    viewable_seconds REAL,       -- IAB viewability (50% for 1s+)
    reading_ratio REAL,          -- actual_time / estimated_read_time
    timestamp INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dwell_session ON content_dwell(session_id);
CREATE INDEX IF NOT EXISTS idx_dwell_name ON content_dwell(name);
CREATE INDEX IF NOT EXISTS idx_dwell_section ON content_dwell(section);
CREATE UNIQUE INDEX IF NOT EXISTS idx_dwell_unique ON content_dwell(session_id, name, section);

-- Scroll milestones per page
CREATE TABLE IF NOT EXISTS scroll_milestones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    path TEXT NOT NULL,
    milestone INTEGER NOT NULL,  -- 25, 50, 75, 90
    timestamp INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_scroll_unique ON scroll_milestones(session_id, path, milestone);

-- Frustration signals for UX analysis
CREATE TABLE IF NOT EXISTS frustration_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    path TEXT,
    event_type TEXT NOT NULL,    -- 'rage_click', 'quick_bounce'
    element TEXT,                -- Element identifier for rage clicks
    timestamp INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_frustration_type ON frustration_events(event_type);
CREATE INDEX IF NOT EXISTS idx_frustration_path ON frustration_events(path);

-- Daily salt for privacy-preserving IP hashing
CREATE TABLE IF NOT EXISTS daily_salts (
    date TEXT PRIMARY KEY,       -- YYYY-MM-DD
    salt TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ML-ready aggregated session features
CREATE TABLE IF NOT EXISTS session_features (
    session_id TEXT PRIMARY KEY,
    pageviews INTEGER DEFAULT 0,
    unique_items INTEGER DEFAULT 0,
    unique_pages INTEGER DEFAULT 0,
    total_dwell_ms INTEGER DEFAULT 0,
    avg_dwell_ms REAL,
    max_scroll_depth INTEGER DEFAULT 0,
    engagement_tier TEXT,        -- 'bounce', 'skim', 'read', 'deep'
    search_count INTEGER DEFAULT 0,
    click_count INTEGER DEFAULT 0,
    frustration_count INTEGER DEFAULT 0,
    duration_ms INTEGER,
    content_sequence TEXT,       -- JSON: ordered list of item names
    first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_features_tier ON session_features(engagement_tier);
CREATE INDEX IF NOT EXISTS idx_features_last ON session_features(last_seen);

-- Aggregated item co-occurrence for recommendations
CREATE TABLE IF NOT EXISTS item_cooccurrence (
    item_a TEXT NOT NULL,
    item_b TEXT NOT NULL,
    coview_count INTEGER DEFAULT 0,
    coclick_count INTEGER DEFAULT 0,
    avg_sequence_distance REAL,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (item_a, item_b)
);

CREATE INDEX IF NOT EXISTS idx_cooccur_a ON item_cooccurrence(item_a);
CREATE INDEX IF NOT EXISTS idx_cooccur_b ON item_cooccurrence(item_b);
