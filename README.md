# qmt-quant

基于 **迅投 QMT（xtquant）** 的本地量化工作台：数据同步、VectorBT 快速研究、A 股规则验证回测、选股与模拟实盘。

## 功能概览

| 页面 | 说明 |
|------|------|
| ① 总览 | 环境/数据状态、一键跑通 ②→③→④ |
| ② 准备数据 | QMT 同步日线/财报、导出 Parquet |
| ③ 快速试策略 | VectorBT 参数扫描（双均线 / 低PE动量 / 选股调仓） |
| ④ 仔细验策略 | 自研 A 股验证器（T+1/滑点/涨跌停）+ 与 ③ 对比 |
| ⑤ 选股 | 模板 + 可视化条件 + YAML 规则 |
| 因子 IC | 因子与未来收益相关性分析 |
| ⑥ 实盘 | xttrader 连接，默认 dry_run |
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

## CLI 常用命令

```powershell
# 数据
python -m qmt_quant.cli sync bars --incremental
python -m qmt_quant.cli sync financial
python -m qmt_quant.cli sync universe
python -m qmt_quant.cli catalog export --fmt both
python -m qmt_quant.cli sync check

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

# 一键流水线 / Web API
python -m qmt_quant.cli pipeline
python -m qmt_quant.cli serve api
```

## Web 工作台

终端 1（quant-env）：

```powershell
python -m qmt_quant.cli serve api
```

终端 2：

```powershell
cd web
npm install
npm run dev
```

浏览器打开 http://localhost:5173（Vite 代理 `/api` → `127.0.0.1:8788`）。

## 目录结构

```
qmt-quant/
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
pytest
```

GitHub Actions 在 push/PR 时自动运行 pytest（Linux，无需 QMT）。

## 验证层说明

默认使用自研 `AShareDailyBacktester`（`validation_engine: custom`）。可选 **NautilusTrader MVP**（`validation_engine: nautilus` 或 `--engine nautilus`），详见 [docs/phase7-nautilus.md](./docs/phase7-nautilus.md)。
