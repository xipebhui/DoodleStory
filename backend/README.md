# DoodleStory FastAPI 后端

本目录是独立 Python FastAPI 后端，默认使用 SQLite 和本地磁盘存储。

## 本地启动

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

从仓库根目录执行数据库迁移：

```bash
backend/.venv/bin/alembic upgrade head
```

启动 API：

```bash
cd backend
.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

API 健康检查：

```bash
curl http://127.0.0.1:8000/health
```

## 数据库

数据库 schema 由 Alembic 管理，应用启动时不会自动创建表。修改 `backend/app/models/` 后必须生成并提交 migration：

```bash
backend/.venv/bin/alembic revision --autogenerate -m "描述变更"
backend/.venv/bin/alembic upgrade head
```
