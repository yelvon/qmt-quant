# Windows + QMT 端到端验收清单

> 在 Windows 主机上，分别于 **qmt-env** 与 **quant-env** 执行下列步骤。

## 前置

- 已安装 QMT 客户端并登录
- `config/settings.yaml` 已配置 `python.qmt_env` / `python.quant_env`
- `jobs.inline: false`，`jobs.force_subprocess_for_qmt: true`（推荐）

## 验收步骤

| 步骤 | 命令 | 预期 |
|------|------|------|
| 1 doctor | 两环境各跑 `qmt-quant doctor` | xtquant OK（qmt-env）；路径可写 |
| 2 init | `qmt-quant init-db` | migrations OK |
| 3 sync | `sync universe` → `sync bars --incremental` → `sync financial` | bars/fin 有数据 |
| 3b check | `sync check --detailed` | 返回 freshness / stale_codes / needs_repair |
| 3c repair | 删除某股近 10 日 bar → `sync check --repair` 或 Web「一键修复」 | 数据恢复 |
| 3d fin incr | 连续两次 `sync financial`（第二次应 skipped 或 rows 更少） | 增量生效 |
| 4 catalog | `catalog export --fmt both` | flat + NT parquet 非空 |
| 5 pipeline | `qmt-quant pipeline`（或 Web 一键跑通） | research + validate run_id |
| 6 dry trade | `trade submit --codes 600519.SH`（无 `--live`） | live_order 有 simulated |
| 7 Web | quant-env `serve api` + 浏览器各页提交 job | job completed |

## 跳过说明

- QMT 未在线：步骤 3 可 SKIP，用已有 PostgreSQL 数据继续 4–7
- 未安装 nautilus_trader：步骤 4 NT 导出 SKIP；验证用 `validation_engine: custom`

## 自动化

- Windows：`scripts/verify_e2e.ps1`
- Linux（无 QMT）：`scripts/verify_e2e.sh`（doctor + pytest + API smoke）
