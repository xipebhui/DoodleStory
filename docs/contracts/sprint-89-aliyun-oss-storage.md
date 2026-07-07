# Sprint Contract

## Sprint Name

`aliyun-oss-storage`

## Goal

在现有本地存储和七牛对象存储之外，新增阿里云 OSS 对象存储后端，解决七牛公开域名到期后内容提取图片 URL 无法被视觉模型下载的问题。

## In Scope

- 新增 `STORAGE_BACKEND=aliyun_oss` 存储模式。
- 新增阿里云 OSS 上传配置读取、上传实现和公开 URL 生成。
- 未配置自定义公网域名时，使用 OSS 默认公开 Bucket 域名生成 `public_url`。
- 上传 OSS 时默认不长期保留服务器本地镜像，避免生成图片和内容提取图片持续占用系统盘；如确需保留，可通过 `OBJECT_STORAGE_KEEP_LOCAL_MIRROR=true` 显式开启。
- 任务下载打包需要本地文件时，可从对象存储临时 materialize 到 `_cache`，打包结束后清理临时缓存；下载 zip 跟随当前存储后端保存。
- 提供历史本地镜像和旧下载 zip 的运维清理脚本，默认 dry-run，显式传入 `--delete` 才会删除文件和对应旧下载记录。
- 资产读取、前端资产 URL 和内容提取继续复用 `file_assets.public_url`。
- 增加单元测试覆盖 OSS URL 生成、上传路径和资产公开 URL 序列化。

## Out of Scope

- 不迁移历史七牛资产。
- 不新增 base64 图片提取兜底。
- 不改成私有 Bucket 签名 URL。
- 不改变抖音下载服务、视觉模型或内容提取 Prompt。
- 不在未确认的情况下自动删除线上历史本地文件。

## Deliverables

- 后端配置、存储枚举和存储服务更新。
- 前端/API 资产 URL 序列化兼容 `aliyun_oss`。
- `oss2` 依赖声明。
- 规格和进度记录更新。

## Done Means

- `STORAGE_BACKEND=aliyun_oss` 时新资产能上传到 OSS，并生成公网可下载 `public_url`。
- 内容提取图文 VL 继续按顺序传公网图片 URL。
- 新写入对象存储资产上传成功后不会继续占用本地镜像空间，除非显式开启本地镜像配置。
- 任务下载 zip 在对象存储模式下保存到对象存储，旧下载 zip 可用清理脚本删除并让用户后续重新生成。
- 相关单测和基础编译检查通过。
- 本地内容提取测试能完成抖音素材下载、OSS 上传和文案提取。

## Verification

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_aliyun_oss_storage backend.tests.test_content_extraction_media_flow backend.tests.test_storage_upload backend.tests.test_qiniu_asset_urls
backend/.venv/bin/python -m compileall backend/app
git diff --check
```

Manual or QA checks:

- 使用本地 `.env` 的阿里云 OSS 配置启动服务。
- 对用户提供的抖音分享链接执行内容提取，确认新登记图片 `public_url` 为 OSS 公开地址，且视觉模型不再返回 URL 不可下载错误。

## Risks / Notes

- OSS Bucket 当前按用户说明保持公开读；如果后续改为私有 Bucket，需要单独设计签名 URL 有效期和模型下载窗口。
- 历史七牛资产的 `public_url` 不会自动改写，新内容提取会使用新的 OSS 存储后端。
