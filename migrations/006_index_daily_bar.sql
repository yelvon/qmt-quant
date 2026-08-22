CREATE TABLE IF NOT EXISTS index_instrument (
    code TEXT PRIMARY KEY,
    name TEXT,
    kind TEXT NOT NULL DEFAULT 'benchmark',
    source_sector TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS index_daily_bar (
    code TEXT NOT NULL,
    date TEXT NOT NULL,
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    volume DOUBLE PRECISION,
    amount DOUBLE PRECISION,
    pre_close DOUBLE PRECISION,
    turnover DOUBLE PRECISION,
    quality_status TEXT DEFAULT 'ok',
    source TEXT DEFAULT 'qmt',
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (code, date)
);

CREATE INDEX IF NOT EXISTS idx_index_daily_bar_date ON index_daily_bar(date);
CREATE INDEX IF NOT EXISTS idx_index_instrument_kind ON index_instrument(kind);
