# qmt-quant Implementation Progress

> Last updated: 2026-07-31  
> PRD version: v0.3

## Phase Milestones

| Phase | Milestone | Status |
|-------|-----------|--------|
| 1 | Data sync + SQLite + Parquet | In progress |
| 2 | VectorBT research + QuantStats | In progress |
| 3a | Custom A-share validator (T+1, fees) | In progress |
| 3b | NautilusTrader integration | Planned (Phase 7) |
| 4 | Screening DSL + backtest bridge + IC | In progress |
| 5 | xttrader live trading | In progress |
| 6 | Web UI enhancements | In progress |
| 7 | NautilusTrader + NT Parquet Catalog | Not started |

## P0 Data Sync (§6.1)

| ID | Requirement | Status |
|----|-------------|--------|
| DS-001 | Sector universe from QMT | Done |
| DS-002 | Watchlist / custom pool | Done |
| DS-003 | Instrument metadata (list/delist/ST) | Done |
| DS-004 | Trade calendar | Done |
| DS-010 | Full history bar sync | Done |
| DS-011 | Incremental bar sync | Done |
| DS-012 | Multiple adjust types | Partial (schema supports, sync one at a time) |
| DS-013 | Standard OHLCV fields | Done |
| DS-014 | Idempotent upsert | Done |
| DS-015 | Parquet catalog export | Done (flat format, not NT standard) |
| DS-016 | Data quality checks | Done |
| DS-020 | Financial batch download | Done |
| DS-021 | Core financial tables | Done |
| DS-022 | report_date + announce_date | Done |
| DS-023 | Structured SQLite storage | Done |
| DS-024 | Financial incremental update | Partial |
| DS-025 | announce_date anti-lookahead | Done |

## P0 Backtest (§6.2)

| ID | Requirement | Status |
|----|-------------|--------|
| BT-V-001 | Single-symbol signals | Done |
| BT-V-002 | Multi-symbol cross-section | Partial (50-stock cap in research) |
| BT-V-003 | Parameter grid search | Done |
| BT-V-004 | cash_sharing portfolio | Done |
| BT-V-005 | A-share fees | Done |
| BT-V-006 | Financial factor alignment | Done |
| BT-V-007 | QuantStats report | Done |
| BT-V-008 | Walk-Forward | Not started |
| BT-N-001 | Daily bar validation | Done (custom engine) |
| BT-N-002 | CN_A_SHARE venue rules | Done (custom engine) |
| BT-N-003 | Fee model | Done |
| BT-N-004 | Slippage | Done |
| BT-N-005 | Strategy lifecycle | Partial (custom engine) |
| BT-N-006 | Anti-lookahead bars | Done |
| BT-N-007 | Multi-symbol portfolio | Done |
| BT-N-008 | Performance analysis | Done |

## P1 Screening (§6.3)

| ID | Requirement | Status |
|----|-------------|--------|
| SC-001 | Multi-condition DSL | Done |
| SC-002 | Price conditions | Partial |
| SC-003 | Financial conditions | Done |
| SC-004 | Sector/ST filters | Done |
| SC-005 | Polars cross-section sort | Done |
| SC-006 | Result persistence | Done |
| SC-007 | Backtest bridge | Done |
| SC-008 | Factor IC analysis | Done |

## P2 Live Trading (§6.4)

| ID | Requirement | Status |
|----|-------------|--------|
| TR-001 | xttrader connection | Done |
| TR-002 | Order placement | Done |
| TR-003 | Query positions/orders | Done |
| TR-004 | Risk controls | Done |
| TR-005 | Signal execution | Partial |
| TR-006 | dry_run default | Done |

## Built-in Strategies

| ID | VectorBT | Validation | Status |
|----|----------|------------|--------|
| buy_and_hold | Yes | Yes | Done |
| ma_cross | Yes | Yes | Done |
| pe_momentum | Yes | Yes | Done |
| screening_rebalance | Yes | Yes | Done |
