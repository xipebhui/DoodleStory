---
title: "快速开始 | Video API 文档"
url: "https://video.inboxlinks.top/api-docs/getting-started/"
requestedUrl: "https://video.inboxlinks.top/api-docs/getting-started/"
siteName: "Video API 文档"
summary: "3 分钟跑通完整上传流程"
adapter: "generic"
capturedAt: "2026-08-02T03:23:09.787Z"
conversionMethod: "defuddle"
kind: "generic/article"
language: "zh"
---

## 快速开始

本文以「创建一个上传到 YouTube 的计划任务」为例，带你用最短路径跑通完整闭环。

1. **准备 API Key**
	所有请求都需要携带 `x-api-key` （在请求 Header 中）。
2. **选择一个 YouTube 频道（channel\_id）**
	调用「 [获取所有 YouTube 频道](https://video.inboxlinks.top/api-docs/youtube-channels/#%E8%8E%B7%E5%8F%96%E6%89%80%E6%9C%89-youtube-%E9%A2%91%E9%81%93) 」接口获取 `channel_id` 。
	```bash
	curl -X POST 'https://video.inboxlinks.top/api/youtube/channel/v1/list' \
	  -H 'Content-Type: application/json' \
	  -H 'x-api-key: <YOUR_API_KEY>' \
	  --data-raw '{ "where": null, "order": [["channel_id", "asc"]], "limit": 50 }'
	```
3. **创建上传到 YouTube 的计划任务**
	传入 `channel_id` + `thumbnail_url` + `download_url` + `plan_run_at` + `upload_args` （标题/描述/可见性等）。
	```bash
	curl -X POST 'https://video.inboxlinks.top/api/youtube/upload-video/v1/create' \
	  -H 'Content-Type: application/json' \
	  -H 'x-api-key: <YOUR_API_KEY>' \
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
	      "query": { "notifySubscribers": true }
	    },
	    "thumbnail_url": "https://example.com/thumbnail.jpg",
	    "download_url": "https://example.com/video.mp4"
	  }'
	```
	任务创建成功后拿到任务 `id` 。
4. **查询任务状态**
	通过「 [查找任务列表](https://video.inboxlinks.top/api-docs/upload-tasks/#%E6%9F%A5%E6%89%BE%E4%BB%BB%E5%8A%A1%E5%88%97%E8%A1%A8) 」或「 [查找单个任务详情](https://video.inboxlinks.top/api-docs/upload-tasks/#%E6%9F%A5%E6%89%BE%E5%8D%95%E4%B8%AA%E4%BB%BB%E5%8A%A1%E8%AF%A6%E6%83%85) 」轮询任务状态：
	| 状态 | 说明 |
	| --- | --- |
	| `Pending` | 等待执行 |
	| `Running` | 执行中 |
	| `Completed` | 完成（上传成功） |
	| `Cancelled` | 已取消（主动取消或失败重试达到上限） |
	```bash
	curl -X GET 'https://video.inboxlinks.top/api/youtube/upload-video/v1/one?id=<TASK_ID>' \
	  -H 'x-api-key: <YOUR_API_KEY>'
	```
5. **查看已上传视频**
	通过「 [已上传视频列表](https://video.inboxlinks.top/api-docs/uploaded-videos/) 」或详情接口查询最终结果（ `youtube_video_id` 等）。
	```bash
	curl -X POST 'https://video.inboxlinks.top/api/youtube/video/v1/list' \
	  -H 'Content-Type: application/json' \
	  -H 'x-api-key: <YOUR_API_KEY>' \
	  --data-raw '{ "where": null, "order": [["uploaded_at", "desc"]], "limit": 10 }'
	```

## 接口调用约定

- **Header 必须带 `x-api-key`** （详见 [认证与约定](https://video.inboxlinks.top/api-docs/auth-conventions/) ）。
- **请求与响应均使用 JSON** （除文件上传/表单上传类接口外）。
- 参数校验失败 → 返回错误响应（见 [错误码与错误响应](https://video.inboxlinks.top/api-docs/auth-conventions/#%E9%94%99%E8%AF%AF%E7%A0%81%E4%B8%8E%E9%94%99%E8%AF%AF%E5%93%8D%E5%BA%94) ）。
- 成功 → 返回业务对象或仅返回 `200` 状态码（以实际接口为准）。