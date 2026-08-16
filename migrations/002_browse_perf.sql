-- Browse/query performance: indexes for cross-section, series/kline, instrument search

-- Cross-section: filter (adjust_type, date) and sort/paginate by code
CREATE INDEX IF NOT EXISTS idx_daily_bar_adjust_date_code
    ON daily_bar (adjust_type, date, code);

-- Series / K-line: filter (code, adjust_type) + date range
CREATE INDEX IF NOT EXISTS idx_daily_bar_code_adjust_date
    ON daily_bar (code, adjust_type, date);

-- Fuzzy instrument search (requires pg_trgm; safe if extension already enabled)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_instrument_name_trgm
    ON instrument USING gin (name gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_instrument_code_trgm
    ON instrument USING gin (code gin_trgm_ops);

ANALYZE daily_bar;
ANALYZE instrument;
