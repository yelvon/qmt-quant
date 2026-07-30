# qmt-quant

基于 **迅投 QMT（xtquant）** 的本地量化工作台：数据同步、VectorBT 快速研究、A 股规则验证回测、选股与模拟实盘。

## 功能概览

| 页面 | 说明 |
|------|------|
| ① 总览 | 环境/数据状态、一键跑通 ②→③→④ |
| ② 准备数据 | QMT 同步日线/财报、导出 Parquet |
| ③ 快速试策略 | VectorBT 双均线参数扫描 |
| ④ 仔细验策略 | A 股 T+1 高保真回测 + 与 ③ 对比 |
| ⑤ 选股 | 模板 + Polars 规则 |
| ⑥ 实盘 | xttrader 适配，默认 dry_run |

## 双环境安装

### 1. qmt-env（数据同步 / 实盘）

使用 QMT 自带 Python（3.8–3.11），确保 xtquant 可用：

```powershell
cd C:\github\qmt-quant
# 将 QMT site-packages 加入 PYTHONPATH，路径以本机为准
$env:PYTHONPATH = "C:\qmt\<终端>\bin.x64\Lib\site-packages"
pip install -r requirements-qmt.txt
pip install -e .
copy config\settings.yaml.example config\settings.yaml
# 编辑 settings.yaml：qmt.install_dir、python.qmt_env 等
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
```

## CLI 常用命令

```powershell
# 数据
python -m qmt_quant.cli sync bars --incremental
python -m qmt_quant.cli sync financial
python -m qmt_quant.cli catalog export
python -m qmt_quant.cli sync check

# 研究 / 验证
python -m qmt_quant.cli research run --strategy ma_cross --range-preset 3y
python -m qmt_quant.cli validate run --from-run <run_id>

# 选股 / 一键流水线
python -m qmt_quant.cli screen run --template low_pe
python -m qmt_quant.cli pipeline

# Web API
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
├── migrations/001_init.sql
├── qmt_quant/          # Python 包
├── strategies/         # vectorbt / nautilus 策略
├── web/                # React + Vite 前端
├── tests/
└── data/               # SQLite + Parquet（gitignore）
```

## 文档

- [产品需求文档](./docs/需求文档.md)
- [UI 设计稿](./docs/UI设计稿.md)
- [Canvas 原型](./canvases/qmt-quant-ui-mockup.canvas.tsx)

## 测试

```powershell
pip install -e ".[dev]"
pytest
```
