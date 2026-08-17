ALTER TABLE backtest_run ADD COLUMN IF NOT EXISTS job_id TEXT;
ALTER TABLE backtest_run ADD COLUMN IF NOT EXISTS run_kind TEXT NOT NULL DEFAULT 'validation';
ALTER TABLE backtest_run ADD COLUMN IF NOT EXISTS strategy_version TEXT;
ALTER TABLE backtest_run ADD COLUMN IF NOT EXISTS strategy_code_hash TEXT;
ALTER TABLE backtest_run ADD COLUMN IF NOT EXISTS settings_json TEXT;
ALTER TABLE backtest_run ADD COLUMN IF NOT EXISTS data_fingerprint_json TEXT;
ALTER TABLE backtest_run ADD COLUMN IF NOT EXISTS universe_json TEXT;
ALTER TABLE backtest_run ADD COLUMN IF NOT EXISTS artifact_dir TEXT;

UPDATE backtest_run
SET run_kind = 'scan'
WHERE run_kind = 'validation'
  AND engine = 'vectorbt'
  AND strategy_id NOT LIKE 'walk_forward_%';

UPDATE backtest_run
SET run_kind = 'walk_forward'
WHERE strategy_id LIKE 'walk_forward_%';

CREATE INDEX IF NOT EXISTS idx_backtest_run_created ON backtest_run(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_backtest_run_job ON backtest_run(job_id);
CREATE INDEX IF NOT EXISTS idx_backtest_run_kind ON backtest_run(run_kind, created_at DESC);
