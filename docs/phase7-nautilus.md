# Phase 7: NautilusTrader 实验 MVP

> Nautilus 是显式选择的实验引擎，不是默认验证路径。默认及生产判断应使用统一 A 股规则内核 `AShareDailyBacktester`。Nautilus 失败时会直接返回错误，**不会 fallback 到 custom**。

## 架构

```
PostgreSQL bars → nt_export.py → ParquetDataCatalog (data/catalog_nt/)
                                      ↓
                         nautilus_runner.py (BacktestEngine)
                                      ↓
                         ValidationResult（与 custom 验证器同形）
```

- **flat parquet**（`data/catalog/`）仍供 VectorBT / 自研验证器使用
- **NT catalog**（`data/catalog_nt/`）供 Nautilus `ParquetDataCatalog` 加载

## 配置

```yaml
backtest:
  validation_engine: custom   # 或 nautilus

data:
  catalog_nt_dir: data/catalog_nt
  export_nt_catalog: false    # true 时 flat 导出同时写 NT
```

CLI 覆盖：`validate run --engine nautilus`

## MVP 限制

| 项 | MVP | Phase 7b |
|----|-----|----------|
| 策略 | ma_cross | 更多策略 |
| 标的数 | ≤10 | 全市场 batch |
| Venue | SIM + 简化费率 | 完整 CN_A_SHARE T+1 |
| Bar type | 仅 `1-DAY-LAST-EXTERNAL` 日线 | 周线、分钟线等 |
| 结果 | 仅期末收益占位；无完整逐日净值/回撤/成交统计 | 可审计绩效与成交 |

## 与 custom 验证器对比

| | Custom (`AShareDailyBacktester`) | Nautilus MVP |
|--|----------------------------------|--------------|
| T+1 / 涨跌停 | 完整 | 未完整（SIM） |
| 依赖 | 无 | nautilus_trader ≥1.200 |
| 用途 | 默认生产验证 | 依赖、Catalog 与引擎接线实验 |

下列情况直接失败，不得静默切换引擎：

- 未安装 `nautilus_trader`
- 策略不是 `ma_cross`
- NT Catalog 没有标的/Bar
- 导出或引擎执行异常

当前实现只把 Catalog 中第一个 instrument 绑定到 `MACrossStrategy`；即使最多导出/载入 10 个标的，也不代表已完成 10 标的组合策略。返回的 `max_drawdown_pct=0`、`trade_count=0` 和单点 equity curve 是 MVP 占位值，不能与 custom 的完整指标等价比较，也不能据此做生产决策。

## 相关文件

- `qmt_quant/core/catalog/nt_export.py`
- `qmt_quant/core/validation/nautilus_runner.py`
- `qmt_quant/core/validation/engine.py`
- `strategies/nautilus/ma_cross.py`
