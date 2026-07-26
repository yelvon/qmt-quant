# qmt-quant

基于 **迅投 QMT（xtquant）** 的本地量化系统：数据同步、策略回测、选股、实盘交易。

## 状态

当前处于 **需求设计阶段**（PRD v0.2），尚未开始编码实现。

## 文档

- [产品需求文档（PRD）](./docs/需求文档.md)
- [UI / 交互设计稿](./docs/UI设计稿.md)

## 技术栈

| 层级 | 技术 |
|------|------|
| 数据源 | QMT / xtquant（`xtdata` + `xttrader`） |
| 研究回测 | **VectorBT**（向量化参数扫描、横截面因子） |
| 验证回测 | **NautilusTrader**（Rust 事件驱动、A 股 T+1 高保真） |
| 选股 | Polars + VectorBT |
| 存储 | SQLite（元数据/财务）+ Parquet Catalog（行情） |
| 实盘（P2） | xttrader |

## 环境要求

- Windows 10/11
- 迅投 QMT 已安装（本机路径示例：`C:\qmt`）
- QMT 客户端保持登录在线
- **双 Python 环境**：
  - `qmt-env`：QMT 自带 Python，跑数据同步与实盘
  - `quant-env`：Python 3.12+，跑 VectorBT / NautilusTrader 回测

## 功能优先级

| 优先级 | 模块 |
|--------|------|
| P0 | 日线行情同步、财务数据同步、双引擎策略回测 |
| P1 | 选股引擎 |
| P2 | 实盘交易（xttrader） |

## 回测工作流

```
QMT 同步 → SQLite + Parquet → VectorBT 快速研究 → NautilusTrader 高保真验证 → 实盘
```
