# Sprint 95 合同：Docker 与 Coolify 部署支持

## Goal

让 DoodleStory 在保留本地开发方式的同时，支持通过 Docker 镜像或 Coolify Docker Compose 部署到现有 Coolify + Traefik + Let’s Encrypt 节点。部署形态必须只暴露容器内部 HTTP 端口，由 Coolify 负责公网域名、HTTPS 和反向代理。

## In Scope

- 新增生产 Dockerfile，构建前端静态文件并运行 FastAPI 后端。
- FastAPI 在生产容器中可直接提供前端静态文件和 SPA fallback，`/api/v1/*` 仍由后端 API 处理。
- 容器启动时执行 Alembic migration，再启动 Uvicorn。
- 新增 Coolify Compose 示例，使用 `expose` 暴露容器端口，不映射宿主机 80/443。
- 明确 SQLite 数据库、文件存储和缓存使用持久化 volume。
- 更新部署文档、环境变量示例、README、规格和进度记录。

## Out of Scope

- 不改成 PostgreSQL、Redis、Celery 或独立 worker。
- 不新增外部反向代理配置，不手写 Coolify 管理的 Traefik labels。
- 不迁移线上数据或直接修改远程服务器 `/data/coolify/services/*` 文件。
- 不把现有本地开发脚本替换为 Docker 开发流。

## Deliverables

- `Dockerfile`
- `.dockerignore`
- `scripts/docker-entrypoint.sh`
- `docker-compose.coolify.yml`
- `docs/deployment/coolify-docker.md`
- 后端静态前端挂载支持
- 文档和进度更新

## Done Means

- 本地可以构建 Docker 镜像。
- 容器启动后 `/health` 可访问。
- 容器启动后非 API 路径可返回前端 `index.html`，前端同源调用 `/api/v1/*`。
- Coolify 部署文档明确端口、FQDN、volume 和关键环境变量。
- `./scripts/check.sh` 通过，或明确记录未通过原因。

## Verification

```bash
backend/.venv/bin/python -m compileall backend/app
npm run build --prefix frontend
docker build -t doodlestory:local .
git diff --check
./scripts/check.sh
```
