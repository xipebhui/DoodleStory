---
title: "频道刷量任务 | Video API 文档"
url: "https://video.inboxlinks.top/api-docs/channel-boost/"
requestedUrl: "https://video.inboxlinks.top/api-docs/channel-boost/"
siteName: "Video API 文档"
summary: "开始/停止一个频道的刷量任务，查询其当前状态"
adapter: "generic"
capturedAt: "2026-08-02T03:25:19.873Z"
conversionMethod: "defuddle"
kind: "generic/article"
language: "zh"
---

## 频道刷量任务

这一组接口用于发起和管理频道的“刷量”任务（例如提升订阅数）。任务由服务端在后台协调执行，调用方只需要开始/停止任务、查询当前状态。

常见用途：

- 为指定频道发起一次刷量任务，设定目标数值
- 修改进行中任务的目标数值
- 停止一个正在进行或排队中的任务
- 查询任务当前状态与执行进度

---

## 刷量任务对象定义

```ts
type ChannelBoostView = {
  channel_id: string; // YouTube 频道 ID
  status: 'idle' | 'waiting' | 'in_progress' | 'stopping' | 'modifying' | 'ended'; // 任务状态，见下方取值说明
  subscribe_target_count: number; // 目标订阅数
  watch_time_hour: number; // 目标观看时长（小时）
  subscribe_max_per_day: number; // 每天最大订阅数量限制
  started_at: string | null; // 任务首次开始执行的时间
  ended_at: string | null; // 任务结束时间
  last_run_info: string | null; // 最近一次执行的附加信息（内容由执行方写入，不保证格式）
  last_heartbeat: string | null; // 最近一次心跳时间
  run_count: number; // 累计执行次数
  worker_id: string | null; // 当前认领该任务的执行方标识
  channel_handle: string; // 频道句柄（@ 后面的部分）
  channel_title: string; // 频道标题
  local_user_id: string | null; // 本地用户 ID，管理此频道的用户
  local_user_email: string | null; // 本地用户邮箱
};
```

`status` 取值及含义：

| 取值 | 含义 |
| --- | --- |
| `idle` | 空闲，尚未发起过任务 |
| `waiting` | 已排队，等待执行方领取 |
| `in_progress` | 执行中 |
| `stopping` | 已请求停止，等待执行方响应并结束 |
| `modifying` | 执行中收到了新的目标数值，等待执行方应用 |
| `ended` | 已结束 |

---

## 查找刷量任务列表

- **URL** ： `{服务器域名}/api/youtube/channel/v1/boost/list`
- **Method** ： `POST`
- **Content-Type** ： `application/json`

请求 / 返回结构复用通用“ [查找数据列表](https://video.inboxlinks.top/api-docs/crud/#%E6%9F%A5%E6%89%BE%E6%95%B0%E6%8D%AE%E5%88%97%E8%A1%A8) “的分页查询结构（ `where/order/cursor/limit` ）， `T` 类型为 [`ChannelBoostView`](https://video.inboxlinks.top/api-docs/channel-boost/#%E5%88%B7%E9%87%8F%E4%BB%BB%E5%8A%A1%E5%AF%B9%E8%B1%A1%E5%AE%9A%E4%B9%89) 。

### curl 调用示例

```bash
curl 'https://video.inboxlinks.top/api/youtube/channel/v1/boost/list' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: token' \
  --data-raw '{
    "where": null,
    "order": [["channel_id", "asc"]],
    "limit": 50
  }'
```

---

## 开始 / 修改刷量任务

发起一个新任务，或修改一个已存在任务的目标数值。

- **URL** ： `{服务器域名}/api/youtube/channel/v1/boost/start?channel_id={channel_id}`
- **Method** ： `POST`
- **Content-Type** ： `application/json`

### Query Parameters

| 参数名 | 类型 | 必填 | 描述 |
| --- | --- | --- | --- |
| `channel_id` | string | 是 | YouTube 频道 ID |

### Request Body

```ts
type StartBoostRequest = {
  subscribe_target_count: number; // 目标订阅数
  watch_time_hour: number; // 目标观看时长（小时）
  subscribe_max_per_day: number; // 每天最大订阅数量限制
};
```

### 成功响应

- **HTTP 状态码** ： `200 OK`
- **Body** ：更新后的任务对象（不含 `channel_handle` / `channel_title` ）：

```ts
type ChannelBoost = Omit<ChannelBoostView, 'channel_handle' | 'channel_title'>;
```

### curl 调用示例

```bash
curl 'https://video.inboxlinks.top/api/youtube/channel/v1/boost/start?channel_id=UCxxxxxxxxxxxxxxxx' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: token' \
  --data-raw '{
    "subscribe_target_count": 1000,
    "watch_time_hour": 200,
    "subscribe_max_per_day": 100
  }'
```

---

## 停止刷量任务

- **URL** ： `{服务器域名}/api/youtube/channel/v1/boost/stop?channel_id={channel_id}`
- **Method** ： `POST`

### Query Parameters

| 参数名 | 类型 | 必填 | 描述 |
| --- | --- | --- | --- |
| `channel_id` | string | 是 | YouTube 频道 ID |

### 成功响应

- **HTTP 状态码** ： `200 OK`
- **Body** ：无内容

### 错误响应

```json
{
  "errcode": "错误码",
  "error": "错误信息"
}
```

### curl 调用示例

```bash
curl -X POST 'https://video.inboxlinks.top/api/youtube/channel/v1/boost/stop?channel_id=UCxxxxxxxxxxxxxxxx' \
  -H 'x-api-key: token'
```

---

## 查询刷量任务状态

- **URL** ： `{服务器域名}/api/youtube/channel/v1/boost/one?channel_id={channel_id}`
- **Method** ： `GET`

### Query Parameters

| 参数名 | 类型 | 必填 | 描述 |
| --- | --- | --- | --- |
| `channel_id` | string | 是 | YouTube 频道 ID |

### Response Body

响应体直接是 [`ChannelBoostView`](https://video.inboxlinks.top/api-docs/channel-boost/#%E5%88%B7%E9%87%8F%E4%BB%BB%E5%8A%A1%E5%AF%B9%E8%B1%A1%E5%AE%9A%E4%B9%89) 对象；若该频道从未发起过刷量任务，响应体为 `null` （HTTP 状态码仍为 `200` ）。

### curl 调用示例

```bash
curl -X GET 'https://video.inboxlinks.top/api/youtube/channel/v1/boost/one?channel_id=UCxxxxxxxxxxxxxxxx' \
  -H 'x-api-key: token'
```