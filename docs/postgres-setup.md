# PostgreSQL 本地部署

qmt-quant 使用 **PostgreSQL** 作为唯一关系型存储（已移除 SQLite）。不迁移历史 `.db`，切换后需重新同步数据。

## 前置

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)（Windows / macOS）或 Linux Docker Engine

## 启动

```bash
cd qmt-quant
docker compose up -d
```

默认连接串：

```text
postgresql://qmt:qmt@localhost:5432/qmt_quant
```

复制 `.env.example` 为 `.env`，或写入 `config/settings.yaml`：

```yaml
data:
  db_url: "postgresql://qmt:qmt@localhost:5432/qmt_quant"
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
