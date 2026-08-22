# AGENTS.md — qmt-quant 维护指南

给人类开发者与 AI Agent 的项目说明书。**改代码前先读本文件**与 [docs/需求文档.md](./docs/需求文档.md)。

> **维护（AI 自维护）**：助手在改 `qmt-quant/` 代码前须先读本文；**每次有实质代码/配置变更时，在同一轮对话内更新变更记录**（见 §2），重大功能另更新 §9。用户无需每次重复「记得记改动」。

---

## 1. 项目是什么

- **qmt-quant**：基于迅投 **QMT / xtquant** 的 **Windows 本机**量化工作台（单用户）。
- **主链路**：同步数据 → 快速研究 → 统一 A 股内核验证 → 实验中心比较 → 选股 → 模拟/实盘。
- **双 Python 环境**（硬约束）：
  - **qmt-env**（3.8–3.11 + xtquant）：数据同步、xttrader 实盘
  - **quant-env**（3.12+）：VectorBT、Polars、FastAPI、回测/选股/Web
  - 数据交换：**PostgreSQL** + **Parquet**（`data/`），两环境互不污染依赖。
- **统一内核**：`core/backtest/` 提供策略注册、成本/组合配置、实验产物；research 与 custom validation 共用 `STRATEGIES` 信号插件和 A 股撮合语义。Nautilus 仅为显式选择的实验引擎，能力不足或依赖缺失时直接报错，**绝不 fallback**（见 [docs/phase7-nautilus.md](./docs/phase7-nautilus.md)）。
- **实盘默认 dry_run**；真实下单须 CLI `--confirm LIVE` 或 Web 二次确认。

权威需求：[docs/需求文档.md](./docs/需求文档.md)（v0.3）  
进度对照：[docs/progress.md](./docs/progress.md)  
变更记录：[docs/CHANGELOG.md](./docs/CHANGELOG.md)

---

## 2. 变更记录（硬规则 — 避免用户重复指令）

**每次交付前**，若本次对话改动了代码、配置示例、CLI/API/Web 行为、迁移或测试，**必须在同一轮对话内**完成下列文档更新（无变更则跳过）：

| 优先级 | 文件 | 何时更新 | 写法 |
|--------|------|----------|------|
| **必做** | [docs/CHANGELOG.md](./docs/CHANGELOG.md) | 任意实质变更 | 在 `## [Unreleased]` 下追加条目；分类用 `### Added` / `### Changed` / `### Fixed`；尽量附 PRD 编号（如 `DS-016`、`BT-V-007`） |
| **必做** | [docs/progress.md](./docs/progress.md) | 完成或部分完成 PRD 需求项 | 更新对应 ID 的 Status（Done / Partial / Not started）与 Phase 表 |
| **按需** | [README.md](./README.md) | 新增/变更 CLI 子命令、Web 页面、安装步骤、环境变量 | 只写入口级信息，细节放 `docs/` |
| **按需** | [docs/需求文档.md](./docs/需求文档.md) | 架构决策、分期计划、验收标准变化 | 更新 §9 勾选与 §12.4 变更记录 |
| **重大功能** | 本文 **§9 近期变更** | 新模块、新策略、跨层重构、Phase 里程碑 | 一行摘要 + 日期 |
| **架构/分层** | 本文 **§3–§5** | 目录结构、环境策略、分层约定变化 | 改对应章节 |

**禁止**：只改代码不更新 CHANGELOG；在 CHANGELOG 里写与 diff 无关的内容。

**发版时**（仅用户要求）：将 `[Unreleased]` 归档为 `## [x.y.z] - YYYY-MM-DD`，并新建空 `[Unreleased]`。

---

## 3. 仓库结构

```text
qmt-quant/
  AGENTS.md                 ← 本文件（AI 协作真源）
  README.md                 ← 用户向快速开始
  config/
    settings.yaml.example   ← 配置模板（勿提交 settings.yaml）
    watchlist.txt
  docs/
    需求文档.md              ← PRD
    progress.md             ← 需求进度
    CHANGELOG.md            ← 变更记录
    UI设计稿.md
  migrations/               ← PostgreSQL 迁移（按编号顺序执行）
  qmt_quant/
    adapters/qmt/           ← xtdata / xttrader（qmt-env）
    core/
      backtest/             ← 统一策略注册、计算内核、实验指标/产物
      data/                 ← 日/周频率与聚合
      sync/                 ← 数据同步
      catalog/              ← DB → Parquet
      research/             ← VectorBT 研究
      validation/           ← AShareDailyBacktester + 引擎工厂；Nautilus 实验适配
      screener/             ← 选股 DSL / rolling IC / 点时快照 / bridge
      universe.py           ← 共用点时股票池
      trade/                ← 实盘 dry_run / 风控
      jobs/                 ← 任务调度（含跨环境 subprocess）
    storage/                ← PostgreSQL 仓储（psycopg）
    cli/                    ← Typer CLI + _job_worker.py
    web/                    ← FastAPI
  strategies/
    vectorbt/               ← 研究策略参考
    nautilus/               ← Nautilus 实验策略
    rules/                  ← 选股 YAML
  web/                      ← React + Vite 前端
  tests/
  data/                     ← gitignore：db + catalog
```

---

## 4. 双环境与运行

### qmt-env（Windows + QMT 在线）

```powershell
pip install -r requirements-qmt.txt
pip install -e .
copy config\settings.yaml.example config\settings.yaml
docker compose up -d
python -m qmt_quant.cli doctor
python -m qmt_quant.cli init-db
python -m qmt_quant.cli sync bars --incremental
```

### quant-env（回测 / Web）

```powershell
pip install -r requirements-quant.txt
pip install -e ".[quant,web,dev]"
pytest
python -m qmt_quant.cli serve api
```

### 关键配置（`config/settings.yaml`）

| 键 | 含义 |
|----|------|
| `python.qmt_env` / `python.quant_env` | 两环境 Python 可执行文件路径 |
| `jobs.inline` | `false` 时 qmt 类 job 通过 subprocess 切到 qmt-env |
| `data.db_url` / `data.parquet_catalog_dir` | PostgreSQL DSN 与 Parquet 目录 |
| `data.catalog_nt_dir` / `data.export_nt_catalog` | Nautilus 实验 Catalog 与是否附加导出 |
| `data.sync.name_backfill_on_incremental` / `concurrency` | 增量名称补全（默认关）/ QMT 同步并发（默认 1） |
| `web.api_token` | 可选 Bearer Token（保护 POST/PUT API） |
| `trade.dry_run` | 默认模拟下单 |
| `qmt.userdata_path` / `qmt.account_id` | xttrader 实盘 |

环境变量：`DATABASE_URL` 覆盖 PostgreSQL 连接串（测试/CI 用）。

---

## 5. 分层约定

| 层 | 职责 | 不要做 |
|----|------|--------|
| `adapters/qmt/` | xtquant 封装 | 业务编排、Web 逻辑 |
| `core/sync/` | 拉数、质量检查 | 回测计算 |
| `core/backtest/` | 策略插件、共享配置/内核、实验产物 | 引入 Web 或 QMT 适配逻辑 |
| `core/research/` | 参数扫描、Walk-Forward、报告 | 复制策略注册或 A 股规则 |
| `core/validation/` | 统一 A 股验证；Nautilus 实验适配 | 静默切换引擎 |
| `core/screener/` | 选股、DSL、rolling IC、点时快照、bridge | 用当前选股结果贯穿历史 |
| `core/trade/` | 下单、风控 | 默认 live 下单 |
| `storage/` | 表读写、迁移 | 调用 xtquant |
| `cli/` | 命令入口 | 复杂 UI |
| `web/` | REST + WebSocket job | 阻塞 sync 在主线程 |
| `web/src/` | React 页面 | 直接调 xtquant |

**新增能力时**：

1. 存储 / 迁移 → `migrations/` + `storage/`
2. 领域逻辑 → `core/<domain>/`
3. CLI → `cli/main.py`
4. API → `web/app.py` + 前端 `web/src/lib/api.ts`
5. 策略 → 实现 `StrategyPlugin` 并在 `core/backtest/strategy.py` 注册；research/Walk-Forward/custom validation 自动按同一 `strategy_id` 解析；Nautilus 支持须另行显式实现
6. 测试 → `tests/test_<domain>.py`
7. **变更记录** → §2 表格

---

## 6. 内置策略与引擎

| strategy_id | 研究 | Custom 验证 | Nautilus 实验 | 说明 |
|-------------|------|-------------|---------------|------|
| `ma_cross` | ✓ | ✓ | MVP | 双均线参数扫描 |
| `macd_cross` | ✓ | ✓ | — | MACD 金叉持有、死叉空仓；扫描快/慢/信号线 |
| `buy_hold` | ✓ | ✓ | — | 基准（策略 ID 不是 `buy_and_hold`） |
| `pe_momentum` | ✓ | ✓ | — | 财报按 `announce_date` 对齐 |
| `screening_rebalance` | ✓ | ✓ | — | 历史回测必须用 rolling 点时快照 |

- `core/backtest/runner.py` 是一键「研究 → custom 验证」入口；插件真源为 `core/backtest/strategy.py`，不要在各 runner 维护分叉策略表。
- 日/周线统一由 `core/data/frequency.py` 处理；周线在实际周末收盘确认信号，下一实际交易日开盘执行，不能把周线索引直接当成交日。
- 研究层默认使用确定性完整股票池；仅显式指定 `universe_n` 时抽样，流动性排序只用回测期初数据。
- `screening_rebalance` 不接受单次静态 `screen_run_id` 贯穿历史；使用 `SelectionSnapshotProvider` / `RuleSelectionSnapshotProvider` 在每个调仓日按当时可见数据生成快照并保留 audit。
- 实验中心数据来自 `backtest_run` 与 `reports/<run_id>/` 的 manifest/detail/equity/trades/positions；当前 Web/API 支持浏览和两次 run 比较，**没有独立实验 CLI**。
- 默认引擎为 `get_validation_engine("custom")`。`nautilus` 仅支持 `ma_cross`、最多 10 标的、日线 SIM 简化撮合；未安装、无 Catalog 或不支持策略时必须失败，不得回退 custom。

---

## 7. 测试与 CI

```bash
pip install -e ".[quant,web,dev]"
pytest
# 显式运行代表性大数据性能基线（默认 pytest 会排除）
pytest -m performance
```

- **危险：测试 fixture 会清库。** `tests/conftest.py` 的 `db` fixture 会对 `DATABASE_URL` 指向的库执行迁移并 `TRUNCATE ... CASCADE`。禁止把开发/生产库交给 pytest；推荐先创建并显式使用 `qmt_quant_test`，例如 `$env:DATABASE_URL="postgresql://qmt:qmt@localhost:5432/qmt_quant_test"`。
- `pyproject.toml` 默认 `addopts = "-m 'not performance'"`；性能测试只在显式 `pytest -m performance` 时运行。
- **Linux CI**（`.github/workflows/test.yml`）无 xtquant；勿让默认测试依赖 QMT 在线。
- 改 `validation/`、`screener/`、`storage/`、`web/app.py` 后应跑相关测试或全量 `pytest`。
- 声称修复完成前须有命令输出依据（见 user rule：evidence before assertions）。

---

## 8. 硬规则（开发）

- **最小改动**：只动与需求相关的文件；匹配现有命名与 Typer/FastAPI 风格。
- **未经用户明确要求**：不要 `git commit`、`git push`、不要改 git config。
- **不要提交**：`config/settings.yaml`、`data/**`、密钥、本机 QMT 绝对路径。
- **财务防未来函数**：研究/选股/验证凡用财报，必须按 `announce_date`（见 `storage/financial.py`）。
- **选股禁止假数据**：无 `Pershareindex` 的股票跳过，不得用 hash 生成 PE/ROE。
- **实盘安全**：默认 dry_run；live 必须显式确认。
- **回复语言**：中文（除非用户用英文）。
- **Plan 文件**：用户 Attach 的 `.plan.md` 一般只读参考；**不要编辑 plan 文件**，改 `docs/` 与 CHANGELOG。

---

## 9. 改动检查清单（交付前自问）

- [ ] 是否已更新 [docs/CHANGELOG.md](./docs/CHANGELOG.md) `[Unreleased]`？
- [ ] 是否已更新 [docs/progress.md](./docs/progress.md) 中相关 PRD 项？
- [ ] CLI/API/Web 行为变了吗？README 或 API 是否要同步？
- [ ] 是否破坏双环境边界（quant-env 里直接 import xtquant 且无 fallback）？
- [ ] 新策略是否在 research/validate runner **和** Web options 中注册？
- [ ] 是否 `pytest` 通过？
- [ ] 重大功能是否写入本文 §10？

---

## 10. 近期变更（随开发更新）

| 日期 | 变更 |
|------|------|
| 2026-08-22 | 指数同步独立为「② 指数同步」卡片与 `sync index` 任务，不再绑在个股日线上 |
| 2026-08-18 | 统一策略插件与 A 股内核、实验产物/比较 API、rolling 选股快照与性能基线；Nautilus 明确为无 fallback 的实验引擎 |
| 2026-08-17 | 原生周线：日线按实际交易周聚合，周末收盘确认并在下一交易日开盘执行，研究/验证/Walk-Forward/Web 全链路支持 |
| 2026-08-17 | 可信基线与偏差修复：真实策略净值、点时股票池、禁止静态历史选股、停牌禁成交 |
| 2026-07-31 | **PostgreSQL 迁移（Breaking）**：移除 SQLite；`docker compose` + `DATABASE_URL`；API Token / CORS / Pipeline subprocess P0 |
| 2026-07-31 | 完善计划落地：数据质量、pe_momentum、ValidationEngine、选股 DSL/IC/bridge、xttrader 骨架、跨环境 job、Web 设置/任务页、CI |
| 2026-07-31 | 新增 `AGENTS.md`：规定每次改动须同步 CHANGELOG + progress |

---

## 11. 文档地图

| 主题 | 文档 |
|------|------|
| 产品需求 | [docs/需求文档.md](./docs/需求文档.md) |
| 实施进度 | [docs/progress.md](./docs/progress.md) |
| 变更记录 | [docs/CHANGELOG.md](./docs/CHANGELOG.md) |
| Windows E2E | [docs/windows-e2e.md](./docs/windows-e2e.md) |
| PostgreSQL 本地部署 | [docs/postgres-setup.md](./docs/postgres-setup.md) |
| Nautilus 实验边界 | [docs/phase7-nautilus.md](./docs/phase7-nautilus.md) |
| Canvas 原型 | [canvases/qmt-quant-ui-mockup.canvas.tsx](./canvases/qmt-quant-ui-mockup.canvas.tsx) |

---

## 12. 快速定位

| 想改… | 先看 |
|--------|------|
| QMT 拉数 | `adapters/qmt/client.py`、`core/sync/bars.py` |
| 数据质量 | `adapters/qmt/transform.py`、`core/sync/check.py` |
| 策略注册 / 一键回测 / 实验产物 | `core/backtest/strategy.py`、`runner.py`、`experiments.py` |
| 日/周线 | `core/data/frequency.py` |
| 快速研究 | `core/research/runner.py`、`walk_forward.py` |
| 验证回测 | `core/validation/backtester.py`、`engine.py`、`runner.py` |
| 选股 | `core/screener/runner.py`、`dsl.py`、`snapshots.py`、`bridge.py`、`ic.py` |
| 实盘 | `adapters/qmt/trader.py`、`core/trade/dry_run.py` |
| 后台任务 | `core/jobs/runner.py`、`cli/_job_worker.py` |
| Web API | `web/app.py` |
| 前端页面 | `web/src/pages/`、`web/src/lib/api.ts` |
| 配置 | `config.py`、`config/settings.yaml.example` |

---

*最后更新：2026-08-18*
