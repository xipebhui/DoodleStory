# 内容提取设计

## 背景

内容提取是 DoodleStory 的新工作台页面，用于从抖音作品中提取可复用文案。用户输入一段可能包含口令、标题、话题、说明文字和短链的抖音分享文本，后端提取真实 URL，调用同机抖音下载服务下载图文或视频，再基于媒体类型提取原始文案。

下载服务只作为后端工具使用，前端不得直接请求 `127.0.0.1:8010`。

参考接口：

- 抖音下载服务健康检查：`GET http://127.0.0.1:8010/health`
- 抖音下载服务下载：`POST http://127.0.0.1:8010/api/v1/download`
- SiliconFlow 多模态能力：`https://docs.siliconflow.cn/cn/userguide/capabilities/multimodal-vision`

## 目标

- 新增主导航 tab：`内容提取`。
- 用户可以粘贴完整抖音分享文本，系统从中解析真实抖音链接。
- 后端下载抖音图文或视频到本地，并把媒体文件登记为 DoodleStory `FileAsset`。
- 下载结果在页面中可见，但不抢占页面主区域。
- 用户点击 `提取文案` 后：
  - 视频：从下载到的 `.mp4` 分离音频，再调用 SiliconFlow 音频理解能力提取原始口播、旁白或字幕文案。
  - 图文：按下载图片顺序逐张调用 SiliconFlow 视觉理解能力提取图片中的文字，再合并为完整文案。
- 页面以文案结果为主，媒体预览为辅助信息；多图下载结果默认折叠。

## 非目标

- 不让前端直连抖音下载服务。
- 不把抖音下载服务返回的服务器绝对路径暴露给浏览器。
- 不自动把提取出的文案创建为 DoodleStory 生成任务。
- 不自动总结、润色、改写或扩写提取结果。
- 不做浏览器下载兜底、无 Cookie 兜底、Mock 下载结果或 Mock 提取结果。
- 不做评论采集、点赞采集、作者主页采集、音乐下载或账号素材库。

## 用户流程

1. 用户进入 `内容提取` tab。
2. 用户在输入框粘贴抖音分享文本，例如：

```text
6.10 eoQ:/ K@w.SY 05/04 :6pm 多和自己相处吧。# 治愈系漫画 # 原创漫画 # 画渣日常 # procreate绘画 # 绘画教程 https://v.douyin.com/Vcpjpg3pcMk/ 复制此链接，打开Dou音搜索，直接观看视频！
```

3. 前端提交原始输入给 DoodleStory 后端。
4. 后端解析出第一个可用抖音 URL：`https://v.douyin.com/Vcpjpg3pcMk/`。
5. 后端创建内容提取记录，状态为 `queued`，并进入下载步骤。
6. 下载成功后，页面展示媒体类型、作品 ID、少量媒体预览和折叠的文件列表。
7. 用户点击 `提取文案`。
8. 后端根据媒体类型执行提取步骤。
9. 页面展示提取状态和最终文案；用户可以复制文案。

## 链接解析

后端负责从用户输入中提取抖音链接。输入字段保留原文，解析字段保存提取出的 URL。

支持的 URL 形态：

- `https://v.douyin.com/.../`
- `http://v.douyin.com/.../`
- `https://www.douyin.com/video/...`
- `https://www.douyin.com/note/...`

规则：

- 从输入文本中提取第一个匹配的抖音 URL。
- URL 末尾如果带中文说明、空格或标点，只保留 URL 本体。
- 如果没有找到抖音 URL，返回校验错误。
- 如果找到多个 URL，第一版只使用第一个，并在详情中保留原始输入用于排查。
- 不对非抖音 URL 做兼容跳转或搜索兜底。

## 后端架构

新增后端模块：

- `app/api/content_extractions.py`：内容提取 REST API。
- `app/services/douyin_import_service.py`：调用同机抖音下载服务。
- `app/services/content_extraction_worker.py`：内容提取轻量队列与状态推进。
- `app/services/media_text_extraction.py`：SiliconFlow 多模态调用和媒体处理。

新增配置：

```env
DOUYIN_IMPORT_SERVICE_BASE_URL=http://127.0.0.1:8010
DOUYIN_IMPORT_SERVICE_TIMEOUT_SECONDS=180
CONTENT_EXTRACTION_FFMPEG_PATH=ffmpeg
SILICONFLOW_VISION_MODEL=Qwen/Qwen2.5-VL-72B-Instruct
SILICONFLOW_AUDIO_MODEL=Qwen/Qwen3-Omni-30B-A3B-Instruct
CONTENT_EXTRACTION_MAX_IMAGE_COUNT=40
CONTENT_EXTRACTION_AUDIO_FORMAT=mp3
```

配置规则：

- `DOUYIN_IMPORT_SERVICE_BASE_URL` 缺失或服务不可达时，内容提取记录失败并显示明确错误。
- `CONTENT_EXTRACTION_FFMPEG_PATH` 不可执行时，视频提取步骤失败并显示明确错误。
- SiliconFlow API key 继续使用现有 `SILICONFLOW_API_KEY`。
- 不从失败的主路径静默切换到旧的子进程下载器。

## 工作流

内容提取使用小型工作流：数据库记录是事实来源，进程内队列只调度记录 ID。

状态：

- `queued`
- `downloading`
- `downloaded`
- `extracting`
- `succeeded`
- `failed`
- `cancel_requested`
- `cancelled`

步骤：

1. `parse_link`
   - 保存 `raw_input`。
   - 提取并保存 `source_url`。
2. `download_media`
   - 调用 `POST /api/v1/download`。
   - 保存 `media_type`、`aweme_id`、`output_dir`、`manifest_path`。
   - 把 `media_files` 登记为 `FileAsset` 和内容提取媒体记录。
3. `extract_text`
   - 视频：从本地视频文件分离音频，登记音频资产，调用音频模型转录。
   - 图文：按 `display_order` 逐张读取图片，调用视觉模型提取图片文字。
4. `compose_result`
   - 按媒体顺序合并文本。
   - 保存最终 `extracted_text` 和每个媒体项的 `extracted_text`。

失败规则：

- 下载服务返回 `400`：记录为配置错误。
- 下载服务返回 `502`：记录为下载失败。
- 下载服务不可达：记录为下载服务不可用。
- 下载成功但没有媒体文件：记录为下载产物为空。
- 图文中任意图片提取失败：本次提取失败，不跳过该图。
- 视频音频分离失败：本次提取失败，不直接把视频传给模型作为兜底。

## SiliconFlow 调用

SiliconFlow 多模态模型通过 `/chat/completions` 调用，消息 `content` 支持 `image_url`、`audio_url`、`video_url` 等内容部分。第一版只使用图片与音频输入。

媒体输入策略：

- 本地图片和音频通过 base64 data URL 传给模型，避免要求本地文件必须有公网 URL。
- 已上传到七牛且有公开 URL 的资产仍可读取本地内容后使用 data URL，保持本地和七牛路径一致。
- 单次请求的媒体大小必须受配置限制；超限直接失败并提示用户，不自动压缩或截断。

图文提取 prompt：

```text
请只提取这张图片中可见的中文或英文文字，保持原始顺序和原始措辞。
不要解释图片内容，不要总结，不要改写。
如果图片里没有可读文字，返回空字符串。
```

视频音频转录 prompt：

```text
请转录这段音频中的原始口播、旁白或对白。
保持原始语气词、停顿和句子顺序，尽量不要改写。
不要总结，不要补充音频里没有的内容。
如果无法识别，请说明无法识别的原因。
```

结果合并：

- 图文：按图片顺序拼接，每张图片的结果之间用一个空行分隔。
- 视频：保存一段完整转录文本。
- 每次模型原始输出保存为步骤输出或媒体项字段，便于排查。

## 数据库设计

### `content_extractions`

字段：

- `id`
- `owner_user_id`
- `raw_input`
- `source_url`
- `status`
- `current_step`
- `media_type`，取值 `video`、`gallery` 或下载服务返回的其他明确值
- `aweme_id`
- `output_dir`
- `manifest_path`
- `extracted_text`
- `error_code`
- `error_message`
- `started_at`
- `finished_at`
- `created_at`
- `updated_at`

索引：

- `owner_user_id`, `created_at desc`
- `status`, `updated_at`
- `aweme_id`

权限：

- 普通用户只能访问自己的内容提取记录。
- Admin 可以查看全部内容提取记录。

### `content_extraction_media`

字段：

- `id`
- `content_extraction_id`
- `asset_id`
- `source_path`
- `media_kind`，取值 `image`、`video`、`audio`、`metadata`
- `display_order`
- `extraction_status`
- `extracted_text`
- `error_code`
- `error_message`
- `created_at`
- `updated_at`

约束：

- `content_extraction_id`, `display_order`, `media_kind` 保持应用层稳定排序。
- `source_path` 只用于服务端排查，不进入普通列表摘要。

### `file_assets`

新增 `FileAssetPurpose`：

- `douyin_media`
- `douyin_audio`
- `douyin_metadata`

下载服务返回的媒体文件必须复制或保存进 DoodleStory 存储抽象，而不是把绝对路径直接作为浏览器资源。

## API 设计

### 健康检查

```http
GET /api/v1/content-extractions/douyin-health
```

响应：

```json
{
  "data": {
    "ok": true,
    "service_base_url": "http://127.0.0.1:8010"
  }
}
```

如果服务不可达，返回明确错误。

### 创建内容提取记录并下载

```http
POST /api/v1/content-extractions
```

请求：

```json
{
  "raw_input": "6.10 eoQ:/ ... https://v.douyin.com/Vcpjpg3pcMk/ ..."
}
```

响应：`202 Accepted`

```json
{
  "data": {
    "id": "ce_...",
    "status": "queued",
    "source_url": "https://v.douyin.com/Vcpjpg3pcMk/"
  }
}
```

### 查询列表

```http
GET /api/v1/content-extractions?status=&query=&limit=20&cursor=...
```

列表只返回摘要：

- `id`
- `source_url`
- `media_type`
- `aweme_id`
- `status`
- `extracted_text_preview`
- `media_count`
- `created_at`
- `updated_at`

### 查询详情

```http
GET /api/v1/content-extractions/{id}
```

详情返回：

- 原始输入
- 解析 URL
- 下载状态
- 媒体摘要和资产 URL
- 提取状态
- 最终文案
- 每个媒体项的提取文本和错误

### 提取文案

```http
POST /api/v1/content-extractions/{id}/extract
```

规则：

- 只有 `downloaded` 或 `failed` 且失败发生在提取步骤的记录可以触发。
- 下载中不能触发。
- 已成功提取的记录再次触发需要后续明确设计，第一版返回冲突错误。

响应：`202 Accepted`

### 取消

```http
POST /api/v1/content-extractions/{id}/cancel
```

取消只在步骤边界生效。已经完成的下载媒体保留。

## UI 设计

主导航新增：

- `任务`
- `内容提取`
- `风格`
- `设置`

### 内容提取页面

页面标题：`内容提取`

主区域：

- 输入框：多行，标签为 `抖音分享文本或链接`。
- 主操作：`解析并下载`。
- 下载完成后主操作切换为 `提取文案`。
- 结果区：最终文案，大文本只读区域，主操作 `复制文案`。

辅助区域：

- 下载状态卡片：媒体类型、作品 ID、媒体数量、更新时间。
- 媒体预览：
  - 视频：显示一个小尺寸视频预览或文件卡片。
  - 图文：默认折叠，只展示首 3 张缩略图和数量；展开后显示完整图片列表。
- 错误区：显示用户可处理的错误，例如下载服务不可用、视频音频分离失败、模型提取失败。

列表区域：

- 最近内容提取记录。
- 支持搜索链接或提取文案预览。
- 支持状态筛选。
- 使用服务端分页。

交互规则：

- 提交失败保留输入内容。
- 下载和提取过程中按钮显示忙碌状态并防止重复提交。
- 页面自动轮询活跃记录。
- 多图预览默认折叠，避免抢占文案结果空间。
- 最终文案是页面视觉中心，媒体只是验证来源。
- 不把下载服务绝对路径展示给普通用户。

## 验证计划

自动验证：

```bash
./scripts/check.sh
```

人工验证：

1. 健康检查：后端能访问 `DOUYIN_IMPORT_SERVICE_BASE_URL/health`。
2. 链接解析：完整分享文本能解析出 `https://v.douyin.com/Vcpjpg3pcMk/`。
3. 图文下载：返回 `media_type=gallery` 后登记多张图片资产。
4. 图文提取：按图片顺序逐张提取并合并文案。
5. 视频下载：返回 `media_type=video` 后登记视频资产。
6. 视频提取：`ffmpeg` 分离音频，音频模型返回原始转录。
7. 错误路径：下载服务不可达、无媒体文件、模型失败都显示明确错误。
