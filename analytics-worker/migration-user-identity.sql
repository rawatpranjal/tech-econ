-- Run once: wrangler d1 execute tech-econ-analytics-db --remote --file=./migration-user-identity.sql
ALTER TABLE events ADD COLUMN user_id TEXT;
ALTER TABLE session_features ADD COLUMN user_id TEXT;
ALTER TABLE session_sequences ADD COLUMN user_id TEXT;
CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id);
