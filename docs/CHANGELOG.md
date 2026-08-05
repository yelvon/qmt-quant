# Changelog

All notable changes to qmt-quant are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added

- 数据浏览 MVP：`daily_bar` / `instrument` 分页查询、日 K 线 API 与 Web 页 `/data/browse`
- `qmt_quant/core/data/`：`table_meta`、`query`、`kline`；CLI `data query` / `data kline`
- Web 组件：CandlestickChart、DataTable、`dataApi.ts`；导航「数据浏览」入口
- Web UX 优化：导航重组（①–⑥ 主流程 + 次要入口）、总览行动卡片、首次引导 checklist
- 共享组件：DataHealthPanel、ComparisonCard、StepProgress、ActionCard、EmptyState、TechnicalDetails
- `/api/status` 扩展 `actions` / `onboarding_complete`；`GET /api/doctor`；`POST /api/jobs/{id}/retry`
- Pipeline 分步进度推送（sync → catalog → research → validate）
- 任务失败人话映射（errorMessages.ts）；JobProgressBar 失败引导与完成 CTA
- Walk-Forward 研究模块（BT-V-008）：`research walk-forward` CLI、Web job、测试
- Phase 7 Nautilus MVP：`nautilus_trader` 可选依赖、NT Parquet Catalog 导出、`NautilusValidationEngine`
- Web：沪深300/中证500 板块、数据页复权/全量区间、选股 YAML 高级、IC 页、帮助页、Walk-Forward 折叠区
- `validation_engine` 配置与落库 `custom_validator` / `nautilus` 区分
- `jobs.force_subprocess_for_qmt` 默认 true；doctor WARN 未配置 qmt_python
- `docs/windows-e2e.md`、`docs/phase7-nautilus.md`、`scripts/verify_e2e.ps1` / `.sh`
- `GET /api/options/validate-runs`；`POST /api/jobs/research/walk-forward`、`/api/jobs/screen/ic`
- `AGENTS.md` — AI 协作真源；规定每次实质变更须同步 CHANGELOG + progress
- `docs/progress.md` — PRD requirement checklist and phase milestones
- Data quality detection on bar sync (DS-016)
- `ValidationEngine` protocol；`pe_momentum` / `screening_rebalance` 策略
- QuantStats summary；YAML screening DSL；screen backtest bridge；Factor IC CLI
- xttrader 骨架；跨环境 job subprocess；Web Settings/Jobs 页；GitHub Actions CI

### Changed

- Web：③ 补股票池；④ ③vs④ 对比卡；数据健康/IC/订单/任务记录表格化；设置页环境检测
- `settings.yaml.example`：`jobs.inline: false`；新增 `validation_engine`、`catalog_nt_dir`
- `catalog export --fmt flat|nt|both` 支持 NT Catalog
- `validate run --engine nautilus` CLI 覆盖
- `progress.md` Phase 1–4 / Web 标 Done；Phase 7 MVP In progress
- Screener 跳过无财报数据标的；`sync_universe` 写入 ST/退市日
- `AShareDailyBacktester`：next_open、滑点、过户费、涨跌停

### Fixed

- Validation 落库 engine 误标 `nautilus` → 按实际引擎 `custom_validator` / `nautilus`
- QMT job 在 quant-env Web 下强制 subprocess 到 qmt-env（当配置了 qmt_python）
- Validation `next_open` 使用下一根 K 线开盘价
