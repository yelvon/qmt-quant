-- Persist cancel requests so interrupt works even if in-memory flag is missing
ALTER TABLE job ADD COLUMN cancel_requested INTEGER DEFAULT 0;
