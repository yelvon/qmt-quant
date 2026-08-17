# qmt-quant

基于 **迅投 QMT（xtquant）** 的本地量化工作台：数据同步、VectorBT 快速研究、A 股规则验证回测、选股与模拟实盘。

## 功能概览

| 页面 | 说明 |
|------|------|
| ① 总览 | 环境/数据状态、一键跑通 ②→③→④ |
| ② 准备数据 | QMT 同步日线/财报、导出 Parquet |
| 数据浏览 | 横截面/时间序列表格、日 K 线（`/data/browse`） |
| ③ 快速试策略 | 日/周线参数扫描（双均线 / MACD 金叉死叉 / 低PE动量 / 选股调仓） |
| ④ 仔细验策略 | 统一 A 股规则内核（T+1/滑点/涨跌停）+ 与 ③ 对比 |
| ⑤ 实验中心 | 浏览实验产物、指标与诊断，对比两次 run |
| ⑥ 选股 / 实盘高级 | 点时滚动选股、因子 IC、模拟/实盘 |
| 因子 IC | 因子与未来收益相关性分析 |
| 帮助 | VectorBT / 验证器 / 双环境说明 |
| 设置 / 任务记录 | QMT 路径、环境 Python、任务历史 |

## 双环境安装

### 1. qmt-env（数据同步 / 实盘）

使用 QMT 自带 Python（3.8–3.11），确保 xtquant 可用：

```powershell
cd C:\github\qmt-quant
$env:PYTHONPATH = "C:\qmt\<终端>\bin.x64\Lib\site-packages"
pip install -r requirements-qmt.txt
pip install -e .
copy config\settings.yaml.example config\settings.yaml
docker compose up -d   # 仅 CLI 手动操作时；一键启动脚本会自动执行
python -m qmt_quant.cli doctor
python -m qmt_quant.cli init-db
```

### 2. quant-env（回测 / 选股 / Web API）

Python 3.12+ 独立虚拟环境：

```powershell
py -3.12 -m venv .venv-quant
.\.venv-quant\Scripts\activate
pip install -r requirements-quant.txt
python -m qmt_quant.cli doctor
```

在 `config/settings.yaml` 中配置：

```yaml
python:
  qmt_env: C:\path\to\qmt\python.exe
  quant_env: C:\github\qmt-quant\.venv-quant\Scripts\python.exe
jobs:
  inline: false   # Web 在 quant-env 时，sync 任务自动 subprocess 到 qmt-env
```

## 如何启动

首次使用请先完成上方 **双环境安装**，并确保 `config/settings.yaml` 已配置 `python.qmt_env` / `python.quant_env`。数据同步与实盘需 **QMT 客户端已登录**。

### 方式一：一键脚本（推荐）

在项目根目录执行，**自动检查并搭建环境**（配置迁移、Python/前端依赖、**本机 PostgreSQL 优先**、init-db；已有则跳过），然后启动 API + 前端并打开浏览器。PostgreSQL 默认优先 **winget 本机安装**，Docker 为备选（Windows ARM64 无需 WSL）。

**PowerShell / CMD（Windows 默认终端）**

```powershell
.\start.bat
# 或
.\scripts\start.ps1
.\scripts\start.ps1 -Restart    # 代码更新后：先停再起
.\scripts\start.ps1 -SetupOnly  # 仅搭建环境，不启动服务
.\scripts\start.ps1 -Stop
.\scripts\start.ps1 -Install
.\scripts\start.ps1 -NoBrowser
```

**Git Bash / MSYS（MINGW64）**

```bash
./start.sh
# 或
./scripts/start.sh
./scripts/start.sh --restart    # 代码更新后：先停再起
./scripts/start.sh --setup-only # 仅搭建环境，不启动服务
./scripts/start.sh --stop
./scripts/start.sh --install
./scripts/start.sh --no-browser
```

> Git Bash 下请用 **正斜杠** `./scripts/start.sh`，不要用 `.\scripts\start.ps1`（那是 PowerShell 脚本）。

| PowerShell 参数 | Git Bash 参数 | 说明 |
|-----------------|---------------|------|
| `-Install` | `--install` | 强制重新安装 Python / 前端依赖 |
| `-SetupOnly` | `--setup-only` | 仅搭建环境，不启动服务 |
| `-NoBrowser` | `--no-browser` | 不自动打开浏览器 |
| `-Stop` | `--stop` | 停止 8788 / 5173 端口上的服务 |
| `-Restart` | `--restart` | 先停止再启动（代码更新后请用此参数） |

访问地址：前端 http://localhost:5173 ，API http://127.0.0.1:8788

### 方式二：Web 工作台（手动）

需两个终端，均在 **quant-env** 下操作：

```powershell
# 终端 1 — 后端 API
python -m qmt_quant.cli serve api

# 终端 2 — 前端（首次需 npm install）
cd web
npm install
npm run dev
```

浏览器打开 http://localhost:5173（Vite 将 `/api`、`/ws` 代理到 `127.0.0.1:8788`）。

### 方式三：CLI 命令行

不启动 Web 界面，直接在终端跑任务（`qmt-env` 或 `quant-env` 视命令而定，见 `doctor` 输出）：

```powershell
# 健康检查
python -m qmt_quant.cli doctor

# 一键流水线：数据检查 → 研究 → 验证
python -m qmt_quant.cli pipeline

# 仅启动 API（供前端或其他客户端调用）
python -m qmt_quant.cli serve api
```

## 访问与使用

启动成功后，**在浏览器访问前端**即可使用工作台（日常只需打开这一个地址）：

| 入口 | 地址 | 说明 |
|------|------|------|
| **Web 工作台** | http://localhost:5173 | 主界面，左侧顶栏切换页面 |
| 后端 API | http://127.0.0.1:8788/api/status | 健康检查（开发调试用，浏览器直接打开可查看 JSON） |

> 请访问 **5173** 端口的前端页面，不要直接访问 8788。前端会自动把 `/api`、`/ws` 请求代理到后端。

### 界面导航

顶栏按量化流程排列，建议按编号顺序使用：

| 页面 | 路径 | 做什么 |
|------|------|--------|
| ① 总览 | `/` | 环境/数据状态、今日建议、**一键跑通**（②→③→④） |
| ② 准备数据 | `/data` | 从 QMT 同步股票池、日线、财报，导出 Parquet |
| ③ 快速试策略 | `/research` | 日/周线参数扫描与 Walk-Forward |
| ④ 仔细验策略 | `/validation` | 统一 A 股规则验证回测，与 ③ 结果对比 |
| ⑤ 实验中心 | `/experiments` | 浏览 run 产物、完整指标/诊断并比较两次实验 |
| ⑥ 选股 / 实盘高级 | `/screening`、`/live` | 点时滚动选股、YAML/IC；xttrader 默认 **模拟下单** |

辅助页面：

| 页面 | 路径 | 做什么 |
|------|------|--------|
| 数据浏览 | `/data/browse` | 查表、看日 K 线 |
| 因子 IC | `/ic` | 因子与未来收益相关性 |
| 任务记录 | `/jobs` | 查看历史任务、失败重试 |
| 设置 | `/settings` | QMT 路径、Python 环境、回测参数 |
| 帮助 | `/help` | VectorBT / 验证器 / 双环境说明 |

### 推荐首次流程

1. **设置**（`/settings`）— 填写 QMT 安装目录、`qmt_env` / `quant_env`，保存后状态应显示 doctor 通过。
2. **准备数据**（`/data`）— 选择板块与范围（建议「全量 3 年」），点击同步；需 **QMT 已登录**。
3. **快速试策略**（`/research`）— 选策略模板与时间范围，提交后等待任务完成，查看收益曲线与指标。
4. **仔细验策略**（`/validation`）— 基于研究 run 做 A 股规则验证，对比 VectorBT 与验证器差异。
5. **实验中心**（`/experiments`）— 查看 manifest、数据指纹、指标与诊断；选择两个 run 比较参数和结果。
6. **选股 / 实盘高级**（可选）— 选股历史回测按调仓日滚动重算快照；实盘订单默认模拟，真仓需显式确认。

首页 **「一键跑通」** 会自动串联：数据检查 → 研究 → 验证，适合快速体验全流程。

### 任务与进度

- 各页面提交同步、回测、选股等操作后，会显示 **进度条**；完成后页面自动刷新结果。
- 失败时查看进度条下方报错，或到 **任务记录**（`/jobs`）查看详情并重试。
- 长时间任务（如同步全市场日线）请保持 API 窗口运行，不要关闭启动脚本弹出的终端。

### 使用 CLI 时

若用 **方式三** 启动，不打开浏览器，直接在终端执行命令；结果写入 PostgreSQL 与 `data/catalog` Parquet，也可随后启动 Web 查看历史 run 与图表。

### 数据同步与完整性

| 方式 | 说明 |
|------|------|
| **更新今日数据** | 近 5 日增量（`data.sync.incremental_days` 可配） |
| **全量同步** | 按 1y / 3y / 5y 拉历史 |
| **一键修复** | 数据健康面板检测缺口后定向补洞 |
| **自动修复** | 设置页开启 `auto_repair`，增量同步后自动修复（默认关） |

CLI：

```powershell
python -m qmt_quant.cli sync check --detailed
python -m qmt_quant.cli sync check --repair      # 检查并修复
python -m qmt_quant.cli sync repair              # 仅修复
python -m qmt_quant.cli sync financial           # 财报增量（默认）
python -m qmt_quant.cli sync financial --full    # 财报全量
python -m qmt_quant.cli sync calendar            # 从 QMT 同步交易日历
```

健康检查项：日线覆盖率、市场新鲜度、个股滞后、市场缺日、交易日历、财报、K 线质量。

配置示例（`config/settings.yaml`）：

```yaml
data:
  sync:
    incremental_days: 5
    stale_trading_days: 3
    gap_scan_lookback: "3y"
    completeness_threshold: 0.85
    auto_repair: false
    auto_repair_max_codes: 200
```

### 访问异常排查

| 现象 | 处理 |
|------|------|
| 页面打不开 / 一直加载 | 确认两个终端（或启动脚本弹出的 API、前端窗口）都在运行；执行 `.\scripts\start.ps1 -Stop` 或 `./scripts/start.sh --stop` 后重新启动 |
| 脚本提示启动失败 | 查看 `logs/api.log`、`logs/web.log` 及弹出的 PowerShell 窗口；确认 Node.js / Python 路径正确 |
| 接口报错 / 502 | 后端 API 未启动或 8788 被占用；检查 API 窗口日志 |
| 数据同步失败 | QMT 客户端是否已登录；`设置` 页 doctor 是否全部通过；再到任务记录和 API 日志查看 PostgreSQL/QMT 原始错误 |
| 查看运行日志 | 见下方「日志位置」 |

### 日志位置

| 日志 | 路径 / 方式 | 内容 |
|------|-------------|------|
| API 后端 | 项目根目录 `logs/api.log` | Python / uvicorn 输出、同步报错 |
| 前端 Vite | 项目根目录 `logs/web.log` | `npm run dev` 输出 |
| 实时终端 | 启动脚本弹出的两个 PowerShell 窗口 | 最直观，同步进度与异常栈都在这里 |
| 任务记录 | 页面右上角 **任务记录** | 历史任务状态与错误信息 |
| PostgreSQL | `data.db_url`（见 `docker compose` 与 [postgres-setup.md](./docs/postgres-setup.md)） | 行情、任务、元数据 |

```powershell
# 实时跟踪 API 日志（PowerShell）
Get-Content -Path logs\api.log -Wait -Tail 50
```

```bash
# Git Bash
tail -f logs/api.log
```

## CLI 常用命令

```powershell
# 数据
python -m qmt_quant.cli sync bars --incremental
python -m qmt_quant.cli sync check --detailed
python -m qmt_quant.cli sync check --repair
python -m qmt_quant.cli sync repair
python -m qmt_quant.cli sync financial
python -m qmt_quant.cli sync financial --full
python -m qmt_quant.cli sync universe
python -m qmt_quant.cli catalog export --fmt both
python -m qmt_quant.cli data query --table daily_bar --view-mode series --code 600519.SH --from 2024-01-01 --to 2024-06-30 --adjust front
python -m qmt_quant.cli data kline --code 600519.SH --from 2024-01-01 --to 2024-06-30

# 研究 / 验证
python -m qmt_quant.cli research run --strategy ma_cross --range-preset 3y
python -m qmt_quant.cli research walk-forward --range-preset 3y --train-months 12 --test-months 3
python -m qmt_quant.cli validate run --from-run <run_id>
python -m qmt_quant.cli validate run --engine nautilus

# 选股
python -m qmt_quant.cli screen run --template low_pe
python -m qmt_quant.cli screen run --rule strategies/rules/low_pe_momentum.yaml
python -m qmt_quant.cli screen backtest --run-id <id> --engine vectorbt
python -m qmt_quant.cli screen ic --template low_pe

# 实盘
python -m qmt_quant.cli trade status
python -m qmt_quant.cli trade submit --codes 600519.SH --live --confirm LIVE

# 一键流水线
python -m qmt_quant.cli pipeline
```

CLI 的真实边界：

- CLI 可运行数据同步/检查/修复、Catalog 导出、研究、Walk-Forward、验证、选股/IC、交易和 pipeline；`research run` / `validate run` 当前没有周线选项，日/周线选择由 Web job/API 提供。
- 实验中心当前没有 `experiment` CLI；请使用 `/experiments`，其数据来自 `backtest_run` 与 `reports/<run_id>/`。
- `screen backtest --engine` 仅接受 `vectorbt|validate`，不是 `nautilus`；历史 `screening_rebalance` 必须使用调仓日点时快照，不能把单次选股结果静态套用整个历史。
- `validate run --engine nautilus` 是显式实验入口，仅支持 `ma_cross`、日线、最多 10 标的和 SIM 简化撮合。缺依赖、Catalog 或能力不支持时直接失败，绝不回退默认引擎。

## 目录结构

```
qmt-quant/
├── start.bat                  # 一键启动 PostgreSQL + Web 工作台
├── scripts/start.ps1          # 启动脚本（含 -Stop / -Install）
├── config/settings.yaml.example
├── docs/CHANGELOG.md          # 变更记录
├── docs/progress.md           # PRD 进度对照
├── migrations/001_init.sql
├── qmt_quant/
├── strategies/rules/          # 选股 YAML 规则
├── web/
├── tests/
└── data/
```

## 文档

- [AGENTS.md](./AGENTS.md) — **AI / 开发者协作规则（含变更记录要求）**
- [产品需求文档](./docs/需求文档.md)
- [实施进度](./docs/progress.md)
- [变更记录](./docs/CHANGELOG.md)
- [Windows E2E 验收](./docs/windows-e2e.md)
- [Phase 7 Nautilus MVP](./docs/phase7-nautilus.md)
- [UI 设计稿](./docs/UI设计稿.md)

## 测试

```powershell
pip install -e ".[quant,web,dev]"
$env:DATABASE_URL = "postgresql://qmt:qmt@localhost:5432/qmt_quant_test"
pytest
# 默认排除的代表性性能基线
pytest -m performance
```

> **警告：本地测试会清数据。** `tests/conftest.py` 的数据库 fixture 会迁移并 `TRUNCATE ... CASCADE` `DATABASE_URL` 指向的数据库。不要指向开发库或生产库；推荐单独创建 `qmt_quant_test`。默认 `pytest` 通过 `pyproject.toml` 排除 `performance` marker，只有显式 `pytest -m performance` 才运行 300 标的/10 年等代表性基线。

GitHub Actions 在 push/PR 时自动运行普通 pytest（Linux，无需 QMT）。

## 验证层说明

默认使用统一 A 股规则内核 `AShareDailyBacktester`（`validation_engine: custom`），研究与验证共用 `core/backtest/strategy.py` 的策略插件。可选 **NautilusTrader 实验 MVP**（显式 `validation_engine: nautilus` 或 `--engine nautilus`），不具备生产级 A 股规则且不 fallback，详见 [docs/phase7-nautilus.md](./docs/phase7-nautilus.md)。
