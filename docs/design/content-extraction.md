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
- 后端同步下载抖音图文或视频到本地，并把媒体文件登记为 DoodleStory `FileAsset`。
- 下载完成后，页面展示一个轻量媒体预览区。
- 用户点击 `提取文案` 后，后端同步执行文案提取并返回结果：
  - 视频：从下载到的 `.mp4` 分离音频，再调用 SiliconFlow 音频理解能力提取原始口播、旁白或字幕文案。
  - 图文：按下载图片顺序把整组图片一次性提交给 SiliconFlow 视觉理解能力，结合前后页上下文后按页输出最终内容提取结果。
- 页面以文案结果为主，媒体预览为辅助信息；多图下载结果默认折叠。

## 非目标

- 不设计异步任务状态机。
- 不引入内容提取 worker、队列、轮询或取消流程。
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

3. 用户点击 `解析并下载`。
4. 前端同步请求 DoodleStory 后端。
5. 后端解析出第一个可用抖音 URL：`https://v.douyin.com/Vcpjpg3pcMk/`。
6. 后端调用同机抖音下载服务，下载完成后登记媒体资产，并返回内容提取记录。
7. 页面展示媒体类型、作品 ID、少量媒体预览和折叠的文件列表。
8. 用户点击 `提取文案`。
9. 前端同步请求 DoodleStory 后端。
10. 后端根据媒体类型执行提取，保存并返回最终文案。
11. 页面以大文本区域展示最终内容提取结果，用户可以复制。

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
- `app/services/media_text_extraction.py`：SiliconFlow 多模态调用和媒体处理。

新增配置：

```env
DOUYIN_IMPORT_SERVICE_BASE_URL=http://127.0.0.1:8010
SILICONFLOW_VISION_MODEL=Qwen/Qwen2.5-VL-72B-Instruct
SILICONFLOW_AUDIO_MODEL=Qwen/Qwen3-Omni-30B-A3B-Instruct
```

固定实现参数：

- 下载服务 HTTP 超时：`180` 秒，写在 `douyin_import_service.py` 中。
- 视频音频分离命令：使用系统 `ffmpeg`，写在 `media_text_extraction.py` 中。
- 视频分离出的音频格式：`mp3`，写在 `media_text_extraction.py` 中。
- 单次图文提取最大图片数：`40`，写在 `media_text_extraction.py` 中。

这些参数第一版不暴露为环境变量；后续只有在确实需要频繁调整时再提升为配置项。

配置规则：

- `DOUYIN_IMPORT_SERVICE_BASE_URL` 缺失或服务不可达时，同步请求失败并返回明确错误。
- 系统 `ffmpeg` 不可执行时，视频提取请求失败并返回明确错误。
- SiliconFlow API key 继续使用现有 `SILICONFLOW_API_KEY`。
- 不从失败的主路径静默切换到旧的子进程下载器。

## 同步流程

内容提取第一版是同步流程，不设计任务状态机。

### 解析并下载

1. 校验并保存 `raw_input`。
2. 提取 `source_url`。
3. 调用 `POST {DOUYIN_IMPORT_SERVICE_BASE_URL}/api/v1/download`。
4. 校验下载响应必须包含至少一个媒体文件。
5. 把 `media_files` 复制或保存进 DoodleStory 存储抽象，登记为 `FileAsset`。
6. 创建最小内容提取记录和媒体记录。
7. 同步返回下载结果。

### 提取文案

1. 用户点击 `提取文案`，前端传入内容提取记录 ID。
2. 后端校验记录归属当前用户。
3. 后端加载该记录下的媒体资产。
4. 如果 `media_type=video`：
   - 找到视频资产。
   - 用 `ffmpeg` 从视频中分离音频为临时 `.mp3`。
   - 调用 SiliconFlow 音频多模态模型转录。
   - 保存音频资产和最终文案。
5. 如果 `media_type=gallery`：
   - 按 `display_order` 读取图片资产。
   - 在一次 SiliconFlow 视觉理解请求中按顺序提交全部图片。
   - 模型必须结合前后页上下文，但输出仍按输入图片顺序逐页排列。
   - 模型返回内容直接保存为最终内容提取结果。
6. 同步返回最终内容提取结果。

失败规则：

- 下载服务返回 `400`：请求失败，返回配置错误。
- 下载服务返回 `502`：请求失败，返回下载失败。
- 下载服务不可达：请求失败，返回下载服务不可用。
- 下载成功但没有媒体文件：请求失败，返回下载产物为空。
- 图文中任意图片提取失败：提取请求失败，不跳过该图。
- 视频音频分离失败：提取请求失败，不直接把视频传给模型作为兜底。
- SiliconFlow 调用失败：提取请求失败，不返回占位文案。

## SiliconFlow 调用

SiliconFlow 多模态模型通过 `/chat/completions` 调用，消息 `content` 支持 `image_url`、`audio_url`、`video_url` 等内容部分。第一版只使用图片与音频输入。

媒体输入策略：

- 本地图片和音频通过 base64 data URL 传给模型，避免要求本地文件必须有公网 URL。
- 已上传到七牛且有公开 URL 的资产仍可读取本地内容后使用 data URL，保持本地和七牛路径一致。
- 单次请求媒体大小如果超过代码内固定上限，直接失败并提示用户，不自动压缩或截断。

图文图片识别 prompt：

```text
请把我接下来按顺序提供的一组漫画图片作为同一个连续作品理解，逐页完整提取漫画内容，并严格按以下要求输出：

1、旁白文字：原文旁白必须逐字照抄，一字不改、一字不漏。
2、对话文字：原文对话必须逐字照抄，保留标点和语气，一字不改。
3、人物内心OS/独白/心里话：完整逐字照抄，标注为【内心OS】。
4、画面描述：客观描述每页画面内容（人物动作、神态、环境、道具），不做删减。
5、分格信息：如果是分格漫画，明确标注【上格】【中格】【下格】及各格内容。
6、必须结合前后图片保持内容连贯，但输出必须按输入图片顺序逐页排列，不要跳页、合并页或改写成故事总结。

输出格式：
第X页：
【分格】单页 / 上中下三格等
画面：（客观描述画面内容）
旁白：（逐字照抄原文旁白，无则写"无"）
对话：（逐字照抄原文对话，无则写"无"）
内心OS：（逐字照抄，无则写"无"）
```

视频音频转录 prompt：

```text
请转录这段音频中的原始口播、旁白或对白。
保持原始语气词、停顿和句子顺序，尽量不要改写。
不要总结，不要补充音频里没有的内容。
如果无法识别，请说明无法识别的原因。
```

结果合并：

- 图文：模型一次性返回完整多页内容，直接写入内容提取详情的主结果区。
- 视频：保存一段完整转录文本。
- 每次模型原始输出写入后端日志，便于排查。

## 数据库设计

内容提取需要最小持久化记录，用于支撑第二个按钮、权限校验和页面刷新后查看结果。该记录不是任务状态机。

### `content_extractions`

字段：

- `id`
- `owner_user_id`
- `raw_input`
- `source_url`
- `media_type`，取值 `video`、`gallery` 或下载服务返回的其他明确值
- `aweme_id`
- `output_dir`
- `manifest_path`
- `extracted_text`
- `created_at`
- `updated_at`

索引：

- `owner_user_id`, `created_at desc`
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
- `extracted_text`
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

### 解析并下载

```http
POST /api/v1/content-extractions/download
```

请求：

```json
{
  "raw_input": "6.10 eoQ:/ ... https://v.douyin.com/Vcpjpg3pcMk/ ..."
}
```

响应：`200 OK`

```json
{
  "data": {
    "id": "ce_...",
    "raw_input": "6.10 eoQ:/ ...",
    "source_url": "https://v.douyin.com/Vcpjpg3pcMk/",
    "media_type": "gallery",
    "aweme_id": "7578551127650620323",
    "media": [
      {
        "id": "cem_...",
        "media_kind": "image",
        "display_order": 1,
        "asset": {
          "id": "asset_...",
          "content_url": "/api/v1/assets/asset_.../content",
          "thumbnail_url": "/api/v1/assets/asset_.../content?variant=thumbnail"
        }
      }
    ],
    "extracted_text": null
  }
}
```

### 提取文案

```http
POST /api/v1/content-extractions/{id}/extract
```

响应：`200 OK`

```json
{
  "data": {
    "id": "ce_...",
    "media_type": "gallery",
    "extracted_text": "第一张图片文字...\n\n第二张图片文字...",
    "media": [
      {
        "id": "cem_...",
        "display_order": 1,
        "extracted_text": "第一张图片文字..."
      }
    ]
  }
}
```

规则：

- 只有当前用户自己的内容提取记录可以提取。
- 没有媒体文件时返回错误。
- 已有 `extracted_text` 时，再次点击 `提取文案` 会重新执行提取并覆盖旧结果；这是用户显式动作，不属于自动重试或静默兜底。

### 查询列表

```http
GET /api/v1/content-extractions?query=&limit=20&cursor=...
```

列表只返回摘要：

- `id`
- `source_url`
- `media_type`
- `aweme_id`
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
- 媒体摘要和资产 URL
- 最终文案
- 每个媒体项的提取文本

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
- 下载完成后显示 `提取文案`。
- 结果区：最终文案，大文本只读区域，主操作 `复制文案`。

辅助区域：

- 下载摘要：媒体类型、作品 ID、媒体数量、更新时间。
- 媒体预览：
  - 视频：显示一个小尺寸视频预览或文件卡片。
  - 图文：默认折叠，只展示首 3 张缩略图和数量；展开后显示完整图片列表。
- 错误区：显示用户可处理的错误，例如下载服务不可用、视频音频分离失败、模型提取失败。

列表区域：

- 最近内容提取记录。
- 支持搜索链接或提取文案预览。
- 使用服务端分页。

交互规则：

- 提交失败保留输入内容。
- `解析并下载` 和 `提取文案` 同步等待完成，按钮显示忙碌状态并防止重复提交。
- 不做自动轮询。
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
3. 图文下载：同步返回 `media_type=gallery` 并登记多张图片资产。
4. 图文提取：同步把全部图片按顺序一次提交给视觉模型，并按输入顺序输出逐页内容。
5. 视频下载：同步返回 `media_type=video` 并登记视频资产。
6. 视频提取：代码内固定使用 `ffmpeg` 分离 `.mp3` 音频，音频模型返回原始转录。
7. 错误路径：下载服务不可达、无媒体文件、模型失败都显示明确错误。
