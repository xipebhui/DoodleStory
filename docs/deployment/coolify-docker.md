# Coolify Docker 部署

本文档用于把 DoodleStory 部署到 Coolify + Traefik + Let’s Encrypt 节点。它不会要求手动修改 Coolify 生成的 `/data/coolify/services/<uuid>/docker-compose.yml`。

## 推荐部署形态

DoodleStory 应用镜像本身是单容器应用：

- 容器内 FastAPI 监听 `0.0.0.0:8000`。
- 前端由 Vite 构建为静态文件，并由同一个 FastAPI 进程提供。
- 前端同源调用 `/api/v1/*`，不需要单独的前端域名或跨域配置。
- SQLite 数据库和本地文件资产都写入 `/app/data`，需要挂载持久化 volume。
- 容器启动时先执行 `alembic upgrade head`，再启动 Uvicorn。

当前 `docker-compose.coolify.yml` 会同时编排两个服务：

- `doodlestory`：对外提供 Web/API，容器端口 `8000`。
- `douyin-import-service`：DoodleStory 的抖音素材导入依赖，只在 Compose 内部网络提供 `8010`，不配置公网域名。

Coolify / Traefik 只需要把 HTTPS 域名流量转发到 `doodlestory` 容器端口 `8000`。

## 目录布局要求

多服务 Compose 构建抖音导入服务时，会从 DoodleStory 的上级目录读取相邻项目：

```text
tmp-project/
  .dockerignore
  DoodleStory/
    docker-compose.coolify.yml
  douyin-import-service/
    Dockerfile
  douyin-downloader/
    run.py
```

`douyin-import-service` 镜像构建会把 `douyin-import-service` 和 `douyin-downloader` 一起复制进镜像。上级目录的 `.dockerignore` 是给 legacy Docker builder 使用的上下文白名单；`.env`、Cookie 文件、下载产物、虚拟环境和历史下载目录不会被打进镜像。

## DNS 与 Coolify

在新节点或新域名上部署时：

1. 在 DNS 服务商添加 A 记录：

   ```text
   A  your-domain.example.com  192.129.209.36
   ```

2. 在 Coolify 面板中新建服务。
3. 如果使用 Git 项目，选择仓库并使用根目录的 `Dockerfile`。
4. 如果使用 Compose 服务，使用仓库里的 `docker-compose.coolify.yml` 作为模板，并确认 Coolify 的构建上下文能访问上述同级目录。
5. 在服务 FQDN / Domain 中填写：

   ```text
   https://your-domain.example.com
   ```

6. 重新部署，让 Coolify 自动生成 Traefik labels 和 Let’s Encrypt 证书。

不要在 compose 中写宿主机端口映射：

```yaml
ports:
  - "8000:8000"
```

应该只暴露容器端口给 Traefik：

```yaml
expose:
  - "8000"
```

## 必填环境变量

最少需要在 Coolify 环境变量里配置：

```env
SESSION_SECRET=replace-with-a-long-random-secret
DATABASE_URL=sqlite:////app/data/doodlestory.db
DOODLESTORY_STORAGE_ROOT=/app/data/storage
DOODLESTORY_FRONTEND_DIST=/app/frontend/dist
```

生产环境建议保留：

```env
APP_ENV=production
FRONTEND_ORIGIN=
STORAGE_BACKEND=local
OBJECT_STORAGE_KEEP_LOCAL_MIRROR=false
```

`FRONTEND_ORIGIN` 可以为空，因为生产镜像是同源访问；如果后续需要允许其它域名跨域访问 API，再填逗号分隔的完整 origin。

## 业务能力相关环境变量

按实际启用能力配置：

```env
ADMIN_EMAILS=

SILICONFLOW_API_KEY=
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
SILICONFLOW_MODEL=deepseek-ai/DeepSeek-V3.2
SILICONFLOW_VISION_MODEL=Qwen/Qwen3-VL-32B-Instruct
SILICONFLOW_AUDIO_MODEL=Qwen/Qwen3-Omni-30B-A3B-Instruct

LIO_API_KEY=
LIO_BASE_URL=
LIO_MODEL=gemini-3.1-flash-lite-preview-thinking-minimal

TEXT_FALLBACK_API_KEY=
TEXT_FALLBACK_BASE_URL=
TEXT_FALLBACK_MODEL=gpt-5.4

IMAGE_PROVIDER=qy
IMAGE_GATEWAY_API_KEY=
IMAGE_GATEWAY_BASE_URL=http://192.129.209.36:3001/v1

XG_BASE_URL=https://api.xgapi.top
XG_API_KEY=
XG_IMAGE_QUALITY=1k
```

## 抖音导入依赖服务

Compose 默认把 DoodleStory 配成：

```env
DOUYIN_IMPORT_SERVICE_BASE_URL=http://douyin-import-service:8010
```

这是 Compose 内部服务名，不需要也不应该暴露到公网。

抖音导入服务需要以下配置：

```env
DOUYIN_COOKIE=
DOUYIN_DOWNLOAD_TIMEOUT_SECONDS=180
```

如果不想把 Cookie 放入环境变量，也可以把 `cookies.json` 放入 `douyin-import-cache` volume 中的：

```text
/app/douyin-import-service/.cache/douyin/cookies.json
```

没有有效 Cookie 时，健康检查仍可通过，但实际下载会明确失败并提示 Cookie 缺失或不可用。

如果启用阿里云 OSS：

```env
STORAGE_BACKEND=aliyun_oss
ALIYUN_OSS_ACCESS_KEY_ID=
ALIYUN_OSS_ACCESS_KEY_SECRET=
ALIYUN_OSS_BUCKET=
ALIYUN_OSS_ENDPOINT=
ALIYUN_OSS_PUBLIC_BASE_URL=
```

## 外部服务地址

如果使用仓库提供的多服务 Compose，抖音导入服务已经在同一 Compose 网络内，不需要填 `127.0.0.1`。

如果你没有一起部署抖音导入服务，而是使用其它节点上的服务，不要把地址继续留成 `127.0.0.1`。容器内的 `127.0.0.1` 指向当前容器自身。

需要按实际网络填可访问地址：

```env
COMIC_VIDEO_SERVICE_BASE_URL=http://host-or-service:51103
COMIC_VIDEO_SERVICE_API_KEY=
```

未部署对应外部服务时，对应功能会在调用时明确报错。

## 持久化 volume

必须持久化 DoodleStory 数据：

```text
/app/data
```

默认包含：

```text
/app/data/doodlestory.db
/app/data/storage/
```

如果使用本地存储，图片、音频、下载包和缩略图都依赖这个目录。迁移节点时需要一并备份。

抖音导入服务还需要持久化：

```text
/app/douyin-import-service/storage
/app/douyin-import-service/.cache/douyin
```

`storage` volume 同时以只读方式挂载到 DoodleStory 容器的相同路径。这样 DoodleStory 能读取抖音导入服务返回的本地媒体路径，并登记为自己的文件资产。

## 健康检查

容器内健康检查：

```bash
curl http://127.0.0.1:8000/health
```

抖音导入服务健康检查：

```bash
curl http://douyin-import-service:8010/health
```

公网检查：

```bash
curl https://your-domain.example.com/health
```

前端页面：

```bash
curl https://your-domain.example.com/
```

API 示例：

```bash
curl https://your-domain.example.com/api/v1/auth/me
```

## 本地构建验证

```bash
docker build -t doodlestory:local .
docker-compose -f docker-compose.coolify.yml -f docker-compose.local.yml up --build
```

打开：

```text
http://127.0.0.1:18080
```

本地端口可通过 `DOODLESTORY_LOCAL_PORT` 调整：

```bash
DOODLESTORY_LOCAL_PORT=18081 docker-compose -f docker-compose.coolify.yml -f docker-compose.local.yml up --build
```

## 当前 Coolify 节点注意事项

现有节点的 `80/443/8080` 已由 `coolify-proxy` 占用。新 DoodleStory 服务不要映射这些宿主机端口。

如果部署到同一台机器并需要访问现有 `new-api`，优先在 Coolify 中给 `new-api` 配 FQDN，或者确认 DoodleStory 容器能访问当前 `IMAGE_GATEWAY_BASE_URL`。不要手改 Coolify 自动生成的 Traefik 配置文件。
