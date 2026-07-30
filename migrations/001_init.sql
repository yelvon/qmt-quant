-- qmt-quant initial schema

CREATE TABLE IF NOT EXISTS instrument (
    code TEXT PRIMARY KEY,
    name TEXT,
    exchange TEXT,
    list_date TEXT,
    delist_date TEXT,
    is_st INTEGER DEFAULT 0,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS trade_calendar (
    cal_date TEXT PRIMARY KEY,
    is_open INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS daily_bar (
    code TEXT NOT NULL,
    date TEXT NOT NULL,
    adjust_type TEXT NOT NULL DEFAULT 'front',
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    amount REAL,
    pre_close REAL,
    turnover REAL,
    quality_status TEXT DEFAULT 'ok',
    source TEXT DEFAULT 'qmt',
    updated_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (code, date, adjust_type)
);
CREATE INDEX IF NOT EXISTS idx_daily_bar_date ON daily_bar(date);

CREATE TABLE IF NOT EXISTS financial_balance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    report_date TEXT NOT NULL,
    announce_date TEXT,
    data_json TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(code, report_date)
);
CREATE INDEX IF NOT EXISTS idx_fin_balance_announce ON financial_balance(code, announce_date);

CREATE TABLE IF NOT EXISTS financial_income (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    report_date TEXT NOT NULL,
    announce_date TEXT,
    data_json TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(code, report_date)
);
CREATE INDEX IF NOT EXISTS idx_fin_income_announce ON financial_income(code, announce_date);

CREATE TABLE IF NOT EXISTS financial_cashflow (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    report_date TEXT NOT NULL,
    announce_date TEXT,
    data_json TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(code, report_date)
);

CREATE TABLE IF NOT EXISTS financial_pershareindex (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    report_date TEXT NOT NULL,
    announce_date TEXT,
    data_json TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(code, report_date)
);

CREATE TABLE IF NOT EXISTS sync_batch (
    id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL,
    params_json TEXT,
    stats_json TEXT,
    error_message TEXT,
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS job (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    job_type TEXT NOT NULL,
    env TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    progress REAL DEFAULT 0,
    params_json TEXT,
    result_json TEXT,
    error_message TEXT,
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS backtest_run (
    id TEXT PRIMARY KEY,
    engine TEXT NOT NULL,
    strategy_id TEXT NOT NULL,
    title TEXT,
    params_json TEXT,
    metrics_json TEXT,
    result_path TEXT,
    status TEXT NOT NULL DEFAULT 'completed',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS screening_result (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    code TEXT NOT NULL,
    score REAL,
    reason TEXT,
    rank_no INTEGER,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_screening_run ON screening_result(run_id);

CREATE TABLE IF NOT EXISTS live_order (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT,
    code TEXT NOT NULL,
    side TEXT NOT NULL,
    price REAL,
    quantity INTEGER,
    status TEXT,
    dry_run INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);
