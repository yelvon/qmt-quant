# Phase 7: NautilusTrader MVP

## 架构

```
SQLite bars → nt_export.py → ParquetDataCatalog (data/catalog_nt/)
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
| Bar type | 1-DAY-LAST-EXTERNAL | 分钟线等 |

## 与 custom 验证器对比

| | Custom (`AShareDailyBacktester`) | Nautilus MVP |
|--|----------------------------------|--------------|
| T+1 / 涨跌停 | 完整 | 未完整（SIM） |
| 依赖 | 无 | nautilus_trader ≥1.200 |
| 用途 | 默认生产验证 | 引擎对齐 / 迁移验证 |

未安装 `nautilus_trader` 时，`NautilusValidationEngine` 自动 fallback 到 custom。

## 相关文件

- `qmt_quant/core/catalog/nt_export.py`
- `qmt_quant/core/validation/nautilus_runner.py`
- `strategies/nautilus/ma_cross.py`
