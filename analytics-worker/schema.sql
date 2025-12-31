-- Tech-Econ Analytics D1 Schema
-- Run: wrangler d1 execute tech-econ-analytics --file=./schema.sql

-- Core events table - stores all raw events
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,              -- pageview, click, search, engage, vitals, error
    session_id TEXT,
    path TEXT,
    timestamp INTEGER NOT NULL,      -- Unix timestamp in ms
    country TEXT,
    data TEXT,                       -- JSON payload
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_path ON events(path);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_type_timestamp ON events(type, timestamp);

-- Daily aggregated stats (for fast dashboard queries)
CREATE TABLE IF NOT EXISTS daily_stats (
    date TEXT PRIMARY KEY,           -- YYYY-MM-DD
    pageviews INTEGER DEFAULT 0,
    unique_sessions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    searches INTEGER DEFAULT 0,
    avg_time_on_page REAL DEFAULT 0,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Content click tracking (aggregated)
CREATE TABLE IF NOT EXISTS content_clicks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    section TEXT,                    -- packages, datasets, learning, papers, etc.
    category TEXT,
    click_count INTEGER DEFAULT 1,
    first_clicked DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_clicked DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, section)
);

CREATE INDEX IF NOT EXISTS idx_clicks_section ON content_clicks(section);
CREATE INDEX IF NOT EXISTS idx_clicks_count ON content_clicks(click_count DESC);

-- Content impression tracking (views/visibility)
CREATE TABLE IF NOT EXISTS content_impressions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    section TEXT,
    impression_count INTEGER DEFAULT 1,
    first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, section)
);

CREATE INDEX IF NOT EXISTS idx_impressions_section ON content_impressions(section);
CREATE INDEX IF NOT EXISTS idx_impressions_count ON content_impressions(impression_count DESC);

-- Search query tracking
CREATE TABLE IF NOT EXISTS search_queries (
    query TEXT PRIMARY KEY,
    search_count INTEGER DEFAULT 1,
    first_searched DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_searched DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Page view tracking (aggregated by path)
CREATE TABLE IF NOT EXISTS page_views (
    path TEXT PRIMARY KEY,
    view_count INTEGER DEFAULT 1,
    unique_sessions INTEGER DEFAULT 0,
    last_viewed DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Hourly activity (for time-series charts)
CREATE TABLE IF NOT EXISTS hourly_stats (
    hour_bucket TEXT PRIMARY KEY,    -- YYYY-MM-DD-HH format
    pageviews INTEGER DEFAULT 0,
    unique_sessions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_hourly_bucket ON hourly_stats(hour_bucket);

-- Country stats
CREATE TABLE IF NOT EXISTS country_stats (
    country TEXT PRIMARY KEY,
    session_count INTEGER DEFAULT 1,
    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Cache metadata
CREATE TABLE IF NOT EXISTS cache_meta (
    key TEXT PRIMARY KEY,
    value TEXT,
    expires_at INTEGER
);
