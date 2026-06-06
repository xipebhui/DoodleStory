# Sprint 22 合同：QNY 公开访问域名配置

## 目标

将对象存储本地配置切换到新的七牛 Bucket 和公开访问域名，并支持 `QNY_PUBLIC_BASE_URL` 与 `QNY_USE_HTTPS` 配置方式。

## 范围内

- 新增 `QNY_PUBLIC_BASE_URL` 配置，作为 QNY 公开访问域名。
- 新增 `QNY_USE_HTTPS` 配置；当公开访问域名没有写 `http://` 或 `https://` 时，用它决定协议。
- 保持 `QINIU_BUCKET_DOMAIN` 和历史 `QNY_DOMAIN` 兼容。
- 将本地 `.env` 切换到 `QNY_BUCKET=video-space001`、`QNY_PUBLIC_BASE_URL=http://tg721n1on.hn-bkt.clouddn.com`、`QNY_USE_HTTPS=false`。
- 做真实上传、公开 URL 访问、缩略图访问和清理验证。

## 范围外

- 不迁移历史本地资产。
- 不修改数据库 schema。
- 不改变本地镜像优先读取和下载打包规则。
- 不引入兜底到本地存储的逻辑。

## 完成标准

- 新配置能生成 `http://tg721n1on.hn-bkt.clouddn.com/...` 形式的公开 URL。
- `STORAGE_BACKEND=qiniu` 下真实上传成功，原图和缩略图 URL 可访问。
- `./scripts/check.sh` 和 `git diff --check` 通过。
