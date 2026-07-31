# Changelog

All notable changes to qmt-quant are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added

- `AGENTS.md` — AI 协作真源；规定每次实质变更须同步 CHANGELOG + progress
- `docs/progress.md` — PRD requirement checklist and phase milestones
- Data quality detection on bar sync (DS-016): `ok` / `bad` / `suspicious` status
- `ValidationEngine` protocol and factory for future NautilusTrader (Phase 7)
- `pe_momentum` and `screening_rebalance` research/validation strategies
- QuantStats summary in research and validation reports (BT-V-007)
- YAML screening DSL parser and `strategies/rules/low_pe_momentum.yaml` (SC-001)
- `screen backtest` CLI/API bridge from screening to research/validation (SC-007)
- Factor IC analysis CLI `screen ic` (SC-008)
- xttrader connection, live order placement, position/order queries (TR-001–TR-003)
- Cross-environment job subprocess dispatch via `cli/_job_worker.py`
- Web: Settings, Jobs pages; screening form; validation benchmark; live confirm modal
- GitHub Actions CI workflow for pytest on Linux

### Changed

- Screener skips stocks without financial data (removed hash-based PE/ROE fallback)
- `sync_universe` writes `is_st`, `delist_date` from QMT instrument detail
- `AShareDailyBacktester`: next_open, slippage, transfer fee, limit-up/down rules
- PRD §9 Phase 3 split into 3a (custom validator) and 3b (Nautilus, Phase 7)

### Fixed

- Validation `next_open` match price now uses next bar open, not same bar close
