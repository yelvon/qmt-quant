# PostgreSQL 本地部署

qmt-quant 使用 **PostgreSQL** 作为唯一关系型存储（已移除 SQLite）。不迁移历史 `.db`，切换后需重新同步数据。

## 启动方式（一键脚本自动选择）

`./scripts/start.sh` 按以下顺序尝试：

1. **本机 PostgreSQL**（推荐，尤其 Windows ARM64 / 无 WSL）
2. **Docker Compose**（备选）

默认连接串：

```text
postgresql://qmt:qmt@localhost:5432/qmt_quant
```

写入 `config/settings.yaml`：

```yaml
data:
  db_url: "postgresql://qmt:qmt@localhost:5432/qmt_quant"
```

## 方式一：本机 PostgreSQL（推荐）

无需 Docker / WSL。一键脚本会通过 `winget` 尝试安装 PostgreSQL 16，并创建 `qmt` 用户与 `qmt_quant` 数据库。

手动安装：

```powershell
winget install PostgreSQL.PostgreSQL.16
```

安装时超级用户 (`postgres`) 密码建议设为 `qmt`（与默认 `db_url` 一致）。安装完成后重新运行：

```bash
./scripts/start.sh
```

## 方式二：Docker Compose（备选）

需 [Docker Desktop](https://www.docker.com/products/docker-desktop/)（Windows 通常还需 WSL2）。

```bash
cd qmt-quant
docker compose up -d
```

## 初始化与同步

```bash
python -m qmt_quant.cli init-db
python -m qmt_quant.cli sync universe
python -m qmt_quant.cli sync bars --incremental false --range-preset 3y
python -m qmt_quant.cli sync financial
```

## 验证

```bash
python -m qmt_quant.cli doctor
python -m qmt_quant.cli sync check
python -m qmt_quant.cli serve api
```

## 测试

```bash
export DATABASE_URL=postgresql://qmt:qmt@localhost:5432/qmt_quant
pytest -q
```

## 可选 API Token

```yaml
web:
  api_token: "your-secret-token"
```

写操作需 Header：`Authorization: Bearer your-secret-token`。
