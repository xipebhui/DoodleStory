---
title: "认证与约定 | Video API 文档"
url: "https://video.inboxlinks.top/api-docs/auth-conventions/"
requestedUrl: "https://video.inboxlinks.top/api-docs/auth-conventions/"
siteName: "Video API 文档"
summary: "API 认证方式与通用约定"
adapter: "generic"
capturedAt: "2026-08-02T03:24:26.535Z"
conversionMethod: "defuddle"
kind: "generic/article"
language: "zh"
---

## 认证与约定

## 认证方式

本系统使用 **API Key** 进行认证。调用方需要在每个请求的 Header 中携带：

```plaintext
x-api-key: <YOUR_API_KEY>
```

示例：

```http
GET /api/example HTTP/1.1
Host: example.com
Content-Type: application/json
x-api-key: your-api-token
```

---

## 通用约定

本章是“所有接口都通用”的规则说明。读懂这里，你会更容易理解后面每个接口的字段含义与行为一致性。

- 统一使用 UTF-8 编码
- 除文件上传/表单上传外，默认 `Content-Type: application/json`
- 响应一般都会有明确的成功/失败结构（错误响应见下文）
- 字段命名以接口定义为准（通常为 `snake_case` 或与第三方 API 对齐的结构）

### HTTP 接口规范

**Header 约定（常用）**

| Header | 说明 |
| --- | --- |
| `x-api-key` | 认证用（必带） |
| `Content-Type` | `application/json` （JSON 请求） |
| `Accept` | `application/json` （建议） |

**HTTP 方法语义**

| 方法 | 用途 |
| --- | --- |
| `POST` | 创建、批量查询（尤其是复杂 where 条件） |
| `GET` | 获取单个资源 |

**Base URL**

- 文中使用 `{服务器域名}` 或 `{资源URL前缀}` 作为占位，实际使用时请替换为真实域名/路径。
- 服务器域名，如 `video.inboxlinks.top` 。

### 日期时间格式

所有时间字段建议使用 **ISO 8601** / **RFC 3339** 字符串，例如：

- `2026-01-16T12:34:56Z` （UTC）
- `2026-01-16T20:34:56+08:00` （带时区偏移）

在 JavaScript 中可以使用：

```js
new Date().toISOString();
```

常见时间字段示例：

| 字段名 | 含义 |
| --- | --- |
| `create_time` / `created_at` | 创建时间 |
| `updated_at` | 更新时间 |
| `plan_run_at` | 计划执行时间 |
| `last_run_at` | 最后一次运行时间 |
| `uploaded_at` | 上传到 YouTube 的时间 |
| `last_sync_at` | 最后一次同步尝试的时间（成功/失败均更新） |
| `last_sync_error` | 最后一次同步错误（成功时为 `null` ） |
| `last_sync_success_at` | 最后一次「成功」同步的时间（仅成功时更新） |

### 错误码与错误响应

当请求失败时，服务端会返回统一结构的错误响应。你需要基于 `errcode` 做程序化处理，基于 `error` 给人看的提示/日志。

所有接口在失败时都返回统一的错误结构：

```json
{
  "errcode": "错误码字符串",
  "error": "错误信息"
}
```

| 字段 | 说明 |
| --- | --- |
| `errcode` | 机器可读错误码，如 `FORBIDDEN` 、 `INVALID_PARAM` 等 |
| `error` | 人类可读错误描述，通常为中文说明 |

HTTP 状态码约定：

| 状态码 | 含义 |
| --- | --- |
| `200` | 成功 |
| `400-500` | 错误 |