---
title: "上传任务 | Video API 文档"
url: "https://video.inboxlinks.top/api-docs/upload-tasks/"
requestedUrl: "https://video.inboxlinks.top/api-docs/upload-tasks/"
siteName: "Video API 文档"
summary: "创建与管理上传到 YouTube 的计划任务"
adapter: "generic"
capturedAt: "2026-08-02T03:24:48.293Z"
conversionMethod: "defuddle"
kind: "generic/article"
language: "zh"
---

## 上传任务

这一组接口用于创建与管理“上传到 YouTube”的异步任务。这样做的好处是：

- 上传过程耗时长也不会阻塞你的前端/调用方
- 可以排队、重试、按计划时间执行
- 任务状态清晰可查，便于运营/后台管理

## 任务状态说明

| 状态 | 说明 |
| --- | --- |
| `pending` | 任务已创建，等待执行 |
| `running` | 正在上传/处理中（建议轮询） |
| `completed` | 已完成（成功时可在“已上传视频”里查到结果） |
| `cancelled` | 已取消（手动取消或系统策略取消） |

---

## 任务字段定义

```ts
type UploadVideoTaskArgsBody = {
  snippet: {
    title: string; // 视频标题
    description: string; // 视频描述
    tags: string[]; // 视频标签
  };
  status: {
    privacyStatus: 'private' | 'public'; // 视频隐私状态
    selfDeclaredMadeForKids: boolean; // 是否为儿童视频
    containsSyntheticMedia: boolean; // 是否包含合成媒体
  };
  paidProductPlacementDetails: {
    hasPaidProductPlacement: boolean; // 是否包含付费产品
  };
  contentDetails?: {
    contentRating?: {
      ytRating?: 'ytAgeRestricted'; // YouTube 年龄限制分级
    };
  };
};

type UploadVideoTaskArgsQuery = {
  notifySubscribers: boolean; // 是否通知订阅者
};

type UploadVideoTaskArgs = {
  body: UploadVideoTaskArgsBody;
  query: UploadVideoTaskArgsQuery;
};

type TaskRuntimeData = {
  message: string; // 任务状态描述信息
  request_id: string; // 上游接口请求 ID
  upload_id: string; // 上游接口上传 ID
  upload_status: string; // 上游接口返回的上传状态，如 "pending" / "running"
};

type UploadVideoTask = {
  id: string; // 任务 ID
  local_video_title: string; // 对应的服务器暂存视频文件名
  youtube_account_id: string; // 对应的 YouTube 账号 ID
  youtube_account_email: string; // 对应的 YouTube 账号邮箱
  channel_id: string; // 对应的 YouTube 频道 ID
  youtube_video_id: string | null; // 对应的 YouTube 视频 ID，会在上传成功后设置
  task_status: string; // pending / running / completed / cancelled
  plan_run_at: string; // 计划运行时间 (ISO 8601)
  last_run_at: string | null; // 最后一次运行时间
  last_run_error: string | null; // 最后一次运行错误
  remark: string | null; // 备注
  created_at: string; // 创建时间
  updated_at: string; // 更新时间
  upload_args: UploadVideoTaskArgs; // 上传参数
  thumbnail_url: string | null; // 缩略图网址
  download_url: string | null; // 视频的下载网址
  task_runtime_data: TaskRuntimeData | null; // 上游接口返回的运行时状态数据,只有task_status为running时此字段才有意义，其他状态下请忽略该字段
};
```

`task_runtime_data` 示例值：

```json
// upload_status 为 "pending" 时
{
  "message": "Task is pending",
  "request_id": "019efe57-8ae7-72f0-b595-5425ae15cc33",
  "upload_id": "559d330f-733b-4ebd-b7ac-541c17f02b61",
  "upload_status": "pending"
}

// upload_status 为 "running" 时
{
  "message": "上传中",
  "request_id": "019efe29-7a35-7013-a8e3-8526ffee3818",
  "upload_id": "53a28728-c2b0-4fd7-980b-abdc909d85a7",
  "upload_status": "running"
}
```

---

## 创建上传视频到 YouTube 的任务

- **URL** ： `{服务器域名}/api/youtube/upload-video/v1/create`
- **Method** ： `POST`
- **Content-Type** ： `application/json`

### Request Body

```json
{
  "channel_id": "string",
  "plan_run_at": "2025-12-24T03:29:05.326468Z",
  "upload_args": {
    "body": {
      "snippet": {
        "title": "",
        "description": "",
        "tags": []
      },
      "status": {
        "privacyStatus": "public",
        "selfDeclaredMadeForKids": false,
        "containsSyntheticMedia": true
      },
      "paidProductPlacementDetails": {
        "hasPaidProductPlacement": false
      }
    },
    "query": {
      "notifySubscribers": true
    }
  },
  "thumbnail_url": "string",
  "download_url": "string"
}
```

| 字段 | 说明 |
| --- | --- |
| `channel_id` | YouTube 频道 ID |
| `plan_run_at` | 计划运行时间，ISO 8601。如要立即上传，填写当前时间或略早时间 |
| `upload_args.body.snippet` | 视频标题、描述、标签 |
| `upload_args.body.status.privacyStatus` | `"public"` / `"private"` / `"unlisted"` |
| `upload_args.body.status.selfDeclaredMadeForKids` | 是否为儿童内容 |
| `upload_args.body.status.containsSyntheticMedia` | 是否包含合成媒体 |
| `upload_args.body.paidProductPlacementDetails.hasPaidProductPlacement` | 是否包含付费产品放置 |
| `upload_args.query.notifySubscribers` | 是否通知订阅者 |
| `thumbnail_url` | 视频缩略图 URL（可选）,格式：png和jpg,小于2M，分辨率16:9，最好1280×720 |
| `download_url` | 视频下载 URL（必填） |

### 成功响应

返回 `UploadVideoTask` 对象（详细结构见上文），包含任务的所有信息。

### curl 调用示例

```bash
curl 'https://video.inboxlinks.top/api/youtube/upload-video/v1/create' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: token' \
  --data-raw '{
    "channel_id": "UCxxxxxxxxxxxxxxxx",
    "plan_run_at": "2025-12-24T03:29:05.326468Z",
    "upload_args": {
      "body": {
        "snippet": {
          "title": "My Video Title",
          "description": "My video description",
          "tags": ["tag1", "tag2"]
        },
        "status": {
          "privacyStatus": "public",
          "selfDeclaredMadeForKids": false,
          "containsSyntheticMedia": false
        },
        "paidProductPlacementDetails": {
          "hasPaidProductPlacement": false
        }
      },
      "query": {
        "notifySubscribers": true
      }
    },
    "thumbnail_url": "https://example.com/thumbnail.jpg",
    "download_url": "https://example.com/video.mp4"
  }'
```

---

## 修改任务

- **URL** ： `{服务器域名}/api/youtube/upload-video/v1/patch`
- **Method** ： `POST`
- **Content-Type** ： `application/json`

可修改字段如下：

```ts
type PatchUploadVideoTaskRequest = PatchRequest<{
  channel_id: string;
  plan_run_at: string; // ISO 8601
  upload_args: UploadVideoTaskArgs;
  task_status: 'pending' | 'running' | 'completed' | 'cancelled';
  thumbnail_url: string | null;
  download_url: string | null;
}>;
```

### curl 调用示例

```bash
curl 'https://video.inboxlinks.top/api/youtube/upload-video/v1/patch' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: token' \
  --data-raw '{
    "ids": ["task-id-1"],
    "data": {
      "remark": "updated remark"
    }
  }'
```

---

## 删除任务

- **URL** ： `{服务器域名}/api/youtube/upload-video/v1/del`
- **Method** ： `POST`
- **Content-Type** ： `application/json`

请求体为任务 ID 列表，参考 [删除数据](https://video.inboxlinks.top/api-docs/crud/#%E5%88%A0%E9%99%A4%E6%95%B0%E6%8D%AE) 。

### curl 调用示例

```bash
curl 'https://video.inboxlinks.top/api/youtube/upload-video/v1/del' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: token' \
  --data-raw '["task-id-1"]'
```

---

## 查找任务列表

- **URL** ： `{服务器域名}/api/youtube/upload-video/v1/list`
- **Method** ： `POST`
- **Content-Type** ： `application/json`

请求 / 返回结构复用 [查找数据列表](https://video.inboxlinks.top/api-docs/crud/#%E6%9F%A5%E6%89%BE%E6%95%B0%E6%8D%AE%E5%88%97%E8%A1%A8) 的 `QueryParams` 与 `PaginationDatas<UploadVideoTask>` 。

### curl 调用示例

```bash
curl 'https://video.inboxlinks.top/api/youtube/upload-video/v1/list' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: token' \
  --data-raw '{
    "where": null,
    "order": [["created_at", "desc"]],
    "limit": 10
  }'
```

---

## 查找单个任务详情

- **URL** ： `{服务器域名}/api/youtube/upload-video/v1/one`
- **Method** ： `GET`

可通过 `id` 查询，返回单个 `UploadVideoTask` 对象。

### curl 调用示例

```bash
curl -X GET 'https://video.inboxlinks.top/api/youtube/upload-video/v1/one?id=task-id-1' \
  -H 'x-api-key: token'
```