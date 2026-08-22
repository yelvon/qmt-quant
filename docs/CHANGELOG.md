# Changelog

All notable changes to qmt-quant are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added

- 指数日线写入独立表 `index_daily_bar` / `index_instrument`（不进股票 `daily_bar`）；数据浏览可切换「指数日线」核对；④ 沪深300 基准曲线读指数表
- 实验中心：每次研究/验证保存 strategy identity、数据指纹、manifest、完整指标/诊断及隔离的 `reports/<run_id>/` 产物；新增实验列表、详情、双 run 比较 API 与 Web 页面
- 选股 rolling 点时快照与审计：`SelectionSnapshotProvider` 在每个调仓日仅使用当时可见数据；rolling IC 支持多窗口/多 horizon
- 代表性性能基线（300 标的、10 年、参数网格、周线、rolling IC），以 `performance` marker 显式运行
- 原生周线研究与验证：`BarFrequency(daily/weekly)` 统一加载入口从本地日线按实际交易日期聚合 OHLCV/amount/pre_close，API/job/策略参数及 Web 支持周期选择，Walk-Forward 窗口按所选 K 线根数计量
- 周线采用日频执行上下文：每周实际最后交易日收盘确认信号，下一实际交易日开盘成交；新增节假日短周聚合与无未来函数测试
- 点时 `PointInTimeUniverse` 服务，按上市/退市日期过滤，可供研究、验证和选股复用；新增可信基线黄金测试
- `SelectionSnapshotProvider.codes_as_of(date)` 历史选股快照扩展接口
- 单股验证写入全部成交并在日 K 标注 B/S；多标的成交列表截断并带 `trades_truncated`
- 研究股票池支持 `sample=all|turnover` 与可选 `universe_n`
- 单股策略 `signal_replay`：信号表走 A 股规则引擎；无 K 线日期写入 `skipped_signals`
- `/api/status.has_strategy_run`：引导第三步「试策略」按是否已有回测/验证记录勾选
- `GET /api/options/research-universe`：提交前展示股票池规模 vs 实际回测只数；支持 `sample` / `universe_n`
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

- 指数同步从个股日线任务拆出：② 准备数据独立「指数同步」卡片；CLI `sync index`；`POST /api/jobs/sync/index`。日线与缺口修复不再顺带拉指数；一键跑通仍会在日线后补一次增量指数
- Nautilus 明确降级为显式实验引擎：仅 `ma_cross`、日线、最多导入 10 标的且当前只运行首标的 SIM 策略；依赖/Catalog/能力失败直接报错，绝不 fallback custom
- 默认 `pytest` 排除 `performance` marker；本地数据库 fixture 会清空目标库，文档统一要求使用独立 `qmt_quant_test`
- Web 主导航调整为 ⑤实验中心、⑥选股/实盘高级
- 研究股票池默认使用确定性完整代码集，不再隐式截断前 50；显式流动性抽样改用回测期初数据
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

- 单股回测默认用全部资金下单：此前组合 10% 仓位对茅台等高价股凑不够 1 手，MACD/均线会出现扫描有收益、A 股内核成交与收益全为 0；买不起 1 手时写入 `insufficient_cash_for_lot`
- 研究报告净值严格来自策略收益，不再缺失时回退为全股票等权净值
- 禁止单次 `screening_rebalance` 选股结果静态贯穿历史；停牌（`volume=0`）信号禁止成交并记录原因
- 选股结果代码可跳转 K 线；数据浏览支持 `?tab=&code=`
- Walk-Forward 非双均线时按钮禁用并说明原因
- Validation 落库 engine 误标 `nautilus` → 按实际引擎 `custom_validator` / `nautilus`
- QMT job 在 quant-env Web 下强制 subprocess 到 qmt-env（当配置了 qmt_python）
- Validation `next_open` 使用下一根 K 线开盘价
