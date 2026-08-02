---
title: "已上传视频 | Video API 文档"
url: "https://video.inboxlinks.top/api-docs/uploaded-videos/"
requestedUrl: "https://video.inboxlinks.top/api-docs/uploaded-videos/"
siteName: "Video API 文档"
summary: "已成功上传到 YouTube 的视频管理"
adapter: "generic"
capturedAt: "2026-08-02T03:24:54.849Z"
conversionMethod: "defuddle"
kind: "generic/article"
language: "zh"
---

## 已上传视频

当上传任务成功后，对应的视频会出现在这里。你可以把它理解为“最终成果清单”。

常见用途：

- 展示已上传记录、YouTube 视频 ID、标题、状态等
- 对视频做后续管理：删除、改可见性、评论、刷新统计数据、修改关联视频、修改封面等

---

## 字段说明

```ts
type UploadedVideo = {
  youtube_video_id: string; // YouTube 生成的视频 ID
  local_video_id: string | null; // 对应的服务器暂存视频 ID
  upload_task_id: string | null; // 对应的上传任务 ID
  channel_id: string; // 频道 ID
  youtube_account_email: string | null; // YouTube 账号邮箱
  uploaded_at: string; // 上传时间 (ISO 8601)
  /** @deprecated 将在未来版本移除，请改用下方类型化字段（title/description/tags/...），见下方说明 */
  datas: UploadVideoTaskArgsBody; // 上传任务中 body 部分（视频元数据），服务端不做强类型校验
  subscribers: string | null; // 订阅者数量
  views: number | null; // 总观看数量
  last_sync_at: string | null; // 最后一次同步尝试的时间（成功/失败均更新）
  last_sync_error: string | null; // 最后一次同步错误（成功时为 null）
  last_sync_success_at: string | null; // 最后一次「成功」同步的时间（仅成功时更新）
  likes: number | null; // 点赞数量
  // 以下 9 个字段见下方「单向写入」说明
  title: string | null;
  description: string | null;
  tags: string[] | null;
  has_paid_promotion: boolean | null;
  is_made_for_kids: boolean | null;
  contains_synthetic_media: boolean | null;
  is_adults_only: boolean | null;
  visibility: 'public' | 'private' | 'unlisted' | null;
  related_video_id: string | null;
};
```

### 字段列表

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `youtube_video_id` | `string` | YouTube 生成的视频 ID |
| `local_video_id` | `string \| null` | 对应的服务器暂存视频 ID |
| `upload_task_id` | `string \| null` | 对应的上传任务 ID |
| `channel_id` | `string` | 频道 ID |
| `youtube_account_email` | `string \| null` | YouTube 账号邮箱（内部通过关联表 join 得到，理论上可能为 `null` ） |
| `uploaded_at` | `string` | 上传时间（ISO 8601） |
| `datas` | `UploadVideoTaskArgsBody` | **已废弃，将在未来版本移除** ，请改用下方类型化字段，见下方说明 |
| `subscribers` | `string \| null` | 订阅者数量变化，展示字符串（如 `"+2.4K"` ），原文透传 |
| `views` | `number \| null` | 总观看数量 |
| `last_sync_at` | `string \| null` | 最后一次同步尝试的时间（成功/失败均更新） |
| `last_sync_error` | `string \| null` | 最后一次同步错误（成功时为 `null` ） |
| `last_sync_success_at` | `string \| null` | 最后一次「成功」同步的时间（仅成功时更新） |
| `likes` | `number \| null` | 点赞数量 |
| `title` | `string \| null` | 视频标题 |
| `description` | `string \| null` | 视频描述 |
| `tags` | `string[] \| null` | 视频标签 |
| `has_paid_promotion` | `boolean \| null` | 是否包含付费推广 |
| `is_made_for_kids` | `boolean \| null` | 是否面向儿童 |
| `contains_synthetic_media` | `boolean \| null` | 是否包含合成媒体（AI 生成/篡改内容） |
| `is_adults_only` | `boolean \| null` | 是否仅限成人 |
| `visibility` | `'public' \| 'private' \| 'unlisted' \| null` | 可见性 |
| `related_video_id` | `string \| null` | 关联视频（结束画面推荐）的 YouTube 视频 ID |

> `UploadVideoTaskArgsBody` 完整（历史）结构详见 [上传任务 — 任务字段定义](https://video.inboxlinks.top/api-docs/upload-tasks/#%E4%BB%BB%E5%8A%A1%E5%AD%97%E6%AE%B5%E5%AE%9A%E4%B9%89) ，注意实际拼出的 `datas` 只覆盖其中的子集，见上方说明。

---

## 查找已上传到 YouTube 的视频列表

- **URL** ： `{服务器域名}/api/youtube/video/v1/list`
- **Method** ： `POST`
- **Content-Type** ： `application/json`

请求 / 返回结构与 [查找数据列表](https://video.inboxlinks.top/api-docs/crud/#%E6%9F%A5%E6%89%BE%E6%95%B0%E6%8D%AE%E5%88%97%E8%A1%A8) 一致， `T` 类型为 `UploadedVideo` 。

### curl 调用示例

```bash
curl 'https://video.inboxlinks.top/api/youtube/video/v1/list' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: token' \
  --data-raw '{
    "where": null,
    "order": [["uploaded_at", "desc"]],
    "limit": 10
  }'
```

### curl 调用示例（key\_set 游标续拉）

```bash
# 首次拉取：不传 key_set（或传 null）
curl 'https://video.inboxlinks.top/api/youtube/video/v1/list' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: token' \
  --data-raw '{
    "where": null,
    "order": [["youtube_video_id", "desc"]],
    "limit": 10
  }'

# 下一页：把上次响应里的 next 原样放入 cursor
# curl 'https://video.inboxlinks.top/api/youtube/video/v1/list' \
#   -H 'Content-Type: application/json' \
#   -H 'x-api-key: token' \
#   --data-raw '{
#     "cursor": <PASTE_NEXT_KEY_SET_HERE>,
#     "where": null,
#     "order": [["youtube_video_id", "desc"]],
#     "limit": 10
#   }'
```

如果要全量增量拉取视频数据，需要按照 [游标拉取流程说明](https://video.inboxlinks.top/api-docs/crud/#%E6%B8%B8%E6%A0%87%E6%8B%89%E5%8F%96%E6%B5%81%E7%A8%8B%E8%AF%B4%E6%98%8E%E5%85%A8%E9%87%8F%E6%96%AD%E7%82%B9%E7%BB%AD%E6%8B%89) 进行调用。

---

## 查找单个视频详情

- **URL** ： `{服务器域名}/api/youtube/video/v1/one`
- **Method** ： `GET`

通过 `youtube_video_id` 查询单个 `UploadedVideo` 详情。

### curl 调用示例

```bash
curl -X GET 'https://video.inboxlinks.top/api/youtube/video/v1/one?youtube_video_id=VIDEO_ID' \
  -H 'x-api-key: token'
```

---

## 删除视频

- **URL** ： `{服务器域名}/api/youtube/video/v1/del`
- **Method** ： `POST`
- **Content-Type** ： `application/json`

请求体为要删除视频的 `youtube_video_id` 列表。

### curl 调用示例

```bash
curl 'https://video.inboxlinks.top/api/youtube/video/v1/del' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: token' \
  --data-raw '["VIDEO_ID_1", "VIDEO_ID_2"]'
```

---

## 修改视频可见性

修改已上传到 YouTube 的视频的可见性。

- **URL** ： `{服务器域名}/api/youtube/video/v1/change-visibility`
- **Method** ： `POST`
- **Content-Type** ： `application/json`

### Request Body

```ts
type ChangeVisibilityRequest = {
  youtube_video_id: string; // YouTube 视频 ID
  visibility: string; // 可见性，可选值见下表
};
```

`visibility` 可选值：

| 值 | 含义 |
| --- | --- |
| `public` | 公开 |
| `private` | 私有 |
| `unlisted` | 不公开列出（拥有链接的人可观看，但不会出现在搜索/频道视频列表中） |

调用上游成功后，本系统会把这次设置的 `visibility` 同步写入本地 [已上传视频](https://video.inboxlinks.top/api-docs/uploaded-videos/#%E5%AD%97%E6%AE%B5%E8%AF%B4%E6%98%8E) 记录的 `visibility` 字段（与 [修改视频信息](https://video.inboxlinks.top/api-docs/uploaded-videos/#%E4%BF%AE%E6%94%B9%E8%A7%86%E9%A2%91%E4%BF%A1%E6%81%AF) 接口写入的是同一个字段）。

### 成功响应

- **HTTP 状态码** ： `200 OK`
- **Body** ：无内容

### curl 调用示例

```bash
curl 'https://video.inboxlinks.top/api/youtube/video/v1/change-visibility' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: token' \
  --data-raw '{
    "youtube_video_id": "VIDEO_ID",
    "visibility": "private"
  }'
```

---

## 修改视频信息

批量修改已上传视频的标题/描述/标签/付费推广/面向儿童/合成媒体/成人限制/可见性/关联视频。

- **URL** ： `{服务器域名}/api/youtube/video/v1/patch`
- **Method** ： `POST`
- **Content-Type** ： `application/json`

### Request Body

```ts
interface VideoPatch {
  title: string | null; // 标题；null 清空
  description: string | null; // 描述；null 清空
  tags: string[] | null; // 标签；null 清空
  has_paid_promotion: boolean; // 是否包含付费推广
  is_made_for_kids: boolean; // 是否面向儿童
  contains_synthetic_media: boolean; // 是否包含合成媒体
  is_adults_only: boolean; // 是否仅限成人
  visibility: 'public' | 'private' | 'unlisted'; // 可见性
  related_video_id: string | null; // 关联视频 ID；null 清空
  remark: string; // 备注（仅本系统内部使用，不会同步到 YouTube）
}

interface PatchRequest {
  ids: string[]; // youtube_video_id 数组
  data: Partial<VideoPatch>;
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `title` | `string \| null` | 视频标题；支持清空 |
| `description` | `string \| null` | 视频描述；支持清空 |
| `tags` | `string[] \| null` | 视频标签；支持清空 |
| `has_paid_promotion` | `boolean` | 是否包含付费推广 |
| `is_made_for_kids` | `boolean` | 是否面向儿童（YouTube 合规声明字段，会直接影响该视频在 YouTube 上的功能限制，如评论/个性化广告等） |
| `contains_synthetic_media` | `boolean` | 是否包含合成媒体（AI 生成/篡改内容的披露声明，YouTube 对未如实声明的内容有处罚政策） |
| `is_adults_only` | `boolean` | 是否仅限成人（内容合规声明字段） |
| `visibility` | `'public' \| 'private' \| 'unlisted'` | 可见性，可选值同 [修改视频可见性](https://video.inboxlinks.top/api-docs/uploaded-videos/#%E4%BF%AE%E6%94%B9%E8%A7%86%E9%A2%91%E5%8F%AF%E8%A7%81%E6%80%A7) |
| `related_video_id` | `string \| null` | 关联视频 ID；支持清空。生效条件同 [修改关联视频](https://video.inboxlinks.top/api-docs/uploaded-videos/#%E4%BF%AE%E6%94%B9%E5%85%B3%E8%81%94%E8%A7%86%E9%A2%91) ：要求账号具备高级权限且已完成手机号验证，目标视频须为同账号已发布的长视频 |
| `remark` | `string` | 备注，仅本系统内部使用 |

### 成功响应

- **HTTP 状态码** ： `200 OK`
- **Body** ：一个 JSON 数字，表示本次实际处理的视频数量（即 `ids` 的长度），例如 `1` 。若某个字段的上游调用失败，则返回错误响应而非该数字，错误信息中包含失败字段的详情（其余已生效的字段修改不会因此被撤销）。

### curl 调用示例

```bash
curl 'https://video.inboxlinks.top/api/youtube/video/v1/patch' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: token' \
  --data-raw '{
    "ids": ["VIDEO_ID"],
    "data": {
      "title": "新标题",
      "visibility": "unlisted"
    }
  }'
```

---

## 评论视频

为已上传到 YouTube 的视频添加评论。

- **URL** ： `{服务器域名}/api/youtube/video/v1/comment`
- **Method** ： `POST`
- **Content-Type** ： `application/json`

### Request Body

```ts
type CommentRequest = {
  youtube_video_id: string; // YouTube 视频 ID
  comment: string; // 评论内容
  pin_comment: boolean; // 是否尝试置顶评论（最终是否置顶由 YouTube 决定）
};
```

### 成功响应

- **HTTP 状态码** ： `200 OK`
- **Body** ：无内容

### curl 调用示例

```bash
curl 'https://video.inboxlinks.top/api/youtube/video/v1/comment' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: token' \
  --data-raw '{
    "youtube_video_id": "VIDEO_ID",
    "comment": "Great video!",
    "pin_comment": false
  }'
```

### 错误响应

```json
{
  "errcode": "错误码",
  "error": "错误信息"
}
```

---

## 刷新视频统计数据

触发一次实时同步，从上游拉取该视频最新的统计数据（观看/点赞/评论、趋势点位、留存曲线等），写入 [视频分析数据](https://video.inboxlinks.top/api-docs/video-analytics/) 对应的表。

- **URL** ： `{服务器域名}/api/youtube/video/v1/refresh-stats`
- **Method** ： `POST`
- **Content-Type** ： `application/json`

### Request Body

```ts
type RefreshVideoStatsRequest = {
  youtube_video_id: string; // YouTube 视频 ID
};
```

### 成功响应

- **HTTP 状态码** ： `200 OK`
- **Body** ：无内容

### curl 调用示例

```bash
curl 'https://video.inboxlinks.top/api/youtube/video/v1/refresh-stats' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: token' \
  --data-raw '{
    "youtube_video_id": "VIDEO_ID"
  }'
```

---

## 修改关联视频

根据视频 ID 设置或清空指定视频的“相关视频”（YouTube 结束画面/推荐关联的视频）：传入 `related_video_id` 时写入相关视频，传空字符串或不传时清空相关视频。

- **URL** ： `{服务器域名}/api/youtube/video/v1/change-related-video`
- **Method** ： `POST`
- **Content-Type** ： `application/json`

### Request Body

```ts
type ChangeRelatedVideoRequest = {
  video_id: string; // 当前视频的 YouTube 视频 ID
  related_video_id: string; // 要关联的目标视频的 YouTube 视频 ID；传空字符串表示清空关联视频链接
};
```

### 成功响应

- **HTTP 状态码** ： `200 OK`
- **Body** ：无内容

### curl 调用示例

```bash
curl 'https://video.inboxlinks.top/api/youtube/video/v1/change-related-video' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: token' \
  --data-raw '{
    "video_id": "VIDEO_ID",
    "related_video_id": "RELATED_VIDEO_ID"
  }'
```

### curl 调用示例（清空相关视频）

```bash
curl 'https://video.inboxlinks.top/api/youtube/video/v1/change-related-video' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: token' \
  --data-raw '{
    "video_id": "VIDEO_ID",
    "related_video_id": ""
  }'
```

---

## 修改视频封面

根据公开图片地址修改指定视频的封面（自定义缩略图）。

### Request Body

```ts
type ChangeThumbnailRequest = {
  video_id: string; // YouTube 视频 ID
  thumbnail_url: string; // 公开可访问的图片地址，需符合下方 YouTube 官方缩略图要求
};
```

### 成功响应

- **HTTP 状态码** ： `200 OK`
- **Body** ：无内容

### curl 调用示例

```bash
curl 'https://video.inboxlinks.top/api/youtube/video/v1/change-thumbnail' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: token' \
  --data-raw '{
    "video_id": "VIDEO_ID",
    "thumbnail_url": "https://example.com/thumbnail.jpg"
  }'
```