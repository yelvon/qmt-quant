-- Speed up per-code MAX(date) scans used by data health checks

CREATE INDEX IF NOT EXISTS idx_daily_bar_adjust_code_date
    ON daily_bar (adjust_type, code, date DESC);

ANALYZE daily_bar;
