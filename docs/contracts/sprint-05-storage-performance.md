# Sprint 05 合同：任务列表与对象存储性能

## 目标

降低任务列表页首次加载带宽和渲染压力，并接入七牛对象存储用于生成图片、人物参考图、风格参考图和下载包的持久化访问。任务列表默认只加载摘要和缩略图，不再拉取完整任务详情和原图。

## 范围内

- 任务列表接口返回轻量摘要：
  - 任务基础信息、状态、进度、风格快照和创建时间。
  - 原文预览，不返回完整原文。
  - 当前成功图片数量。
  - 最多 4 张当前成功图片的预览资产。
- 任务详情继续通过 `GET /api/v1/tasks/{task_id}` 单独加载完整 panels、steps、generated_images、人物参考和下载记录。
- 前端任务列表使用摘要响应渲染，进入列表页不再自动请求第一条任务详情。
- 资产访问支持原图和缩略图两种变体：
  - 原图：`/api/v1/assets/{asset_id}/content`
  - 缩略图：`/api/v1/assets/{asset_id}/content?variant=thumbnail`
- 七牛对象存储接入：
  - `STORAGE_BACKEND=qiniu` 时，新上传和新生成资产写入七牛。
  - 七牛配置支持 `QINIU_ACCESS_KEY` / `QINIU_SECRET_KEY` / `QINIU_BUCKET` / `QINIU_BUCKET_DOMAIN`，也兼容现有 `QNY_ACCESS_KEY` / `QNY_SECRET_KEY` / `QNY_BUCKET` / `QNY_DOMAIN`。
  - 七牛私有空间通过签名下载 URL 访问。
  - 七牛缩略图通过 `imageView2` 参数生成。
  - 七牛配置缺失或上传失败时明确报错，不静默切回本地。
- 本地存储资产支持按需生成 WebP 缩略图，避免旧本地资产列表页继续拉原图。
- 任务生成、风格测试、人物参考图生成和下载打包可以读取本地资产或七牛资产。

## 范围外

- 不迁移历史本地资产到七牛。
- 不新增对象存储管理后台。
- 不做 CDN 缓存刷新、生命周期管理或批量迁移工具。
- 不改变任务生成业务流程和图片 provider 选择。

## 完成标准

- `GET /api/v1/tasks` 不再返回完整 `TaskRead`。
- 任务列表首屏不再自动请求第一条任务详情。
- 列表缩略图请求使用 `variant=thumbnail`。
- `STORAGE_BACKEND=qiniu` 下新资产保存到七牛，并在访问时走后端鉴权后重定向到七牛 URL。
- 已运行 `./scripts/check.sh`。

## 验证

```bash
./scripts/check.sh
```

人工检查：

- 打开任务列表，观察 Network 中 `/tasks` 响应不包含 panels 和 generated_images 完整数组。
- 打开任务详情，确认详情抽屉才请求 `/tasks/{id}`。
- 本地资产缩略图访问 `/assets/{id}/content?variant=thumbnail` 返回 WebP。
- 七牛配置齐全时，新生成资产记录 `storage_backend=qiniu`，缩略图 URL 包含 `imageView2` 处理参数。
