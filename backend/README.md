# DoodleStory FastAPI 后端

本目录是独立 Python FastAPI 后端，默认使用 SQLite 和本地磁盘存储。

## 本地启动

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

API 健康检查：

```bash
curl http://127.0.0.1:8000/health
```
