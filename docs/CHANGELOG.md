# Changelog

All notable changes to qmt-quant are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added

- 单股验证写入全部成交并在日 K 标注 B/S；多标的成交列表截断并带 `trades_truncated`
- 研究股票池可选 `sample=head|turnover` 与 `universe_n`（默认仍代码序前 50）
- 单股策略 `signal_replay`：信号表走 A 股规则引擎；无 K 线日期写入 `skipped_signals`
- `/api/status.has_strategy_run`：引导第三步「试策略」按是否已有回测/验证记录勾选
- `GET /api/options/research-universe`：提交前展示股票池规模 vs 实际回测只数；支持 `sample` / `universe_n`（默认仍代码序 50）
- `GET /api/options/validation-engines`；验证页可选引擎；设置页可保存 `validation_engine`（默认仍 custom）
- 选股表单透传均线窗口 / 上市天数；YAML 可编辑；`rule_yaml` 非法返回 400
- 实盘预览走风控；`TradeBody.orders[]`；页面展示持仓/资金，支持买卖与手数
- PostgreSQL 存储层：`docker-compose.yml`、`data.db_url` / `DATABASE_URL`、Greenfield PG schema
- `docs/postgres-setup.md`；doctor「PostgreSQL 可达」检查
- 一键启动脚本（`start.bat` / `scripts/start.sh`）会自动 `docker compose up -d` 拉起 PostgreSQL；**若容器已在运行则不会重启**
- Pipeline 一键跑通 sync 步骤走 qmt-env subprocess（与单独同步任务一致）
- 数据同步补强：缺口检测（`gaps.py`）、定向修复（`repair.py`）、`sync_meta` 水位表
- 深度健康检查：市场新鲜度、个股滞后、市场缺日、区间完整度（`--detailed`）
- CLI / Web：`sync repair`、`sync check --repair`；数据页「一键修复」；设置页 `auto_repair`
- 财报增量同步（DS-024）：`announce_date` 水位 + `sync financial --full` 全量选项
- QMT 交易日历真源：`get_trading_dates` + `sync calendar`（fallback 指数 K 线）
- `data.sync.*` 配置项
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

- 顶栏 ①–⑥ 编号固定，不再随回测模式改序号或隐藏 ④
- 总览一键跑通步骤跟随 `job.step`；简单模式完成 CTA 去 ③
- 简单/单股模式打开 ④ 仍可看历史验证，不再整页拦截
- 任务横幅叠加展示其它 running 任务；任务记录有运行中任务时轮询
- **Breaking**：移除 SQLite；所有读写改 PostgreSQL（`psycopg`），旧 `.db` 不迁移，需重新同步
- 合并迁移为 PG 版 `migrations/001_init.sql`；CI pytest 依赖 postgres service
- CORS 默认仅本地 Vite 源（`web.cors_origins`）
- Web：③ 补股票池；④ ③vs④ 对比卡；数据健康/IC/订单/任务记录表格化；设置页环境检测
- `settings.yaml.example`：`jobs.inline: false`；新增 `validation_engine`、`catalog_nt_dir`
- `catalog export --fmt flat|nt|both` 支持 NT Catalog
- `validate run --engine nautilus` CLI 覆盖
- `progress.md` Phase 1–4 / Web 标 Done；Phase 7 MVP In progress
- Screener 跳过无财报数据标的；`sync_universe` 写入 ST/退市日
- `AShareDailyBacktester`：next_open、滑点、过户费、涨跌停

### Fixed

- 选股结果代码可跳转 K 线；数据浏览支持 `?tab=&code=`
- Walk-Forward 非双均线时按钮禁用并说明原因
- Validation 落库 engine 误标 `nautilus` → 按实际引擎 `custom_validator` / `nautilus`
- QMT job 在 quant-env Web 下强制 subprocess 到 qmt-env（当配置了 qmt_python）
- Validation `next_open` 使用下一根 K 线开盘价
