---
title: "频道分析数据 | Video API 文档"
url: "https://video.inboxlinks.top/api-docs/channel-analytics/"
requestedUrl: "https://video.inboxlinks.top/api-docs/channel-analytics/"
siteName: "Video API 文档"
summary: "频道最新汇总数据（总量、近 28 天变化量与每日点位）"
adapter: "generic"
capturedAt: "2026-08-02T03:25:13.985Z"
conversionMethod: "defuddle"
kind: "generic/article"
language: "zh"
---

## 频道分析数据

用于获取 YouTube 频道的分析数据，包括最新汇总数据。数据来自上游 `channel/overview` 接口聚合而来，一次同步会拿到总量、近 28 天变化量、近 28 天每日趋势点位三组数据。

常见用途：

- 获取频道的总订阅数、总观看数、总观看时长
- 获取频道近 28 天的订阅数/观看数/观看时长变化量
- 通过每日点位字段（ `*_28d_daily` ）绘制近 28 天的趋势图

---

## 获取频道最新汇总数据

获取指定频道的最新汇总数据，包括总订阅数、总观看量、总观看时长，以及近 28 天的变化量和每日点位数据。

### Query Parameters

| 参数名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `channel_id` | `string` | ✅ | 频道 ID |

### 成功响应

- **HTTP 状态码** ： `200 OK`

```ts
/** 近 28 天每日点位数据点。 */
type ChannelOverviewDailyPoint = {
  date: string; // 日期，格式 YYYY-MM-DD
  value: number; // 该日的数据值，含义随所属字段而定（订阅数/观看数/观看时长）
};

type ChannelAnalyticsLatest = {
  channel_id: string; // 频道 ID
  analytics: {
    // ── 总量统计 ──
    total_subscribers: number | null; // 总订阅数
    total_views: number | null; // 总观看数
    total_watch_time_hours: number | null; // 总观看时长（小时，整数，服务端对上游数字取整后存储）

    // ── 近 28 天变化量 ──
    total_subscribers_28d: number | null; // 近 28 天订阅数变化（可能为负数）
    total_views_28d: number | null; // 近 28 天观看数
    total_watch_time_hours_28d: number | null; // 近 28 天观看时长（小时，整数）

    // ── 近 28 天每日点位 ──
    subscribers_28d_daily: ChannelOverviewDailyPoint[] | null; // 近 28 天订阅数每日点位
    views_28d_daily: ChannelOverviewDailyPoint[] | null; // 近 28 天观看数每日点位
    watch_time_hours_28d_daily: ChannelOverviewDailyPoint[] | null; // 近 28 天观看时长每日点位
  };
  // ── 同步状态 ──
  last_sync_at: string | null; // 最近一次同步尝试的时间（ISO 8601；成功或失败都更新）
  last_sync_error: string | null; // 最近一次同步的错误信息（成功时为 null）
  last_sync_success_at: string | null; // 最近一次「成功」同步的时间（ISO 8601；仅成功时更新）
};
```

### 字段分组说明

| 分组 | 字段 | 类型 | 说明 |
| --- | --- | --- | --- |
| **总量统计** | `total_subscribers` | `number \| null` | 总订阅数 |
|  | `total_views` | `number \| null` | 总观看数 |
|  | `total_watch_time_hours` | `number \| null` | 总观看时长（小时，整数） |
| **近 28 天变化量** | `total_subscribers_28d` | `number \| null` | 近 28 天订阅数变化，可能为负数（掉粉） |
|  | `total_views_28d` | `number \| null` | 近 28 天观看数 |
|  | `total_watch_time_hours_28d` | `number \| null` | 近 28 天观看时长（小时，整数） |
| **近 28 天每日点位** | `subscribers_28d_daily` | `ChannelOverviewDailyPoint[] \| null` | 近 28 天订阅数每日趋势 |
|  | `views_28d_daily` | `ChannelOverviewDailyPoint[] \| null` | 近 28 天观看数每日趋势 |
|  | `watch_time_hours_28d_daily` | `ChannelOverviewDailyPoint[] \| null` | 近 28 天观看时长每日趋势 |
| **同步状态** | `last_sync_at` | `string \| null` | 最近一次同步尝试的时间（ISO 8601；成功或失败都更新） |
|  | `last_sync_error` | `string \| null` | 最近一次同步的错误信息（成功时为 `null` ） |
|  | `last_sync_success_at` | `string \| null` | 最近一次「成功」同步的时间（ISO 8601；仅成功时更新） |

---

### 近 28 天每日点位的数据形状

`subscribers_28d_daily` / `views_28d_daily` / `watch_time_hours_28d_daily` 三个字段都是 `ChannelOverviewDailyPoint[]` 数组，按日期递增排列，元素形状完全一致，只是 `value` 的含义随所属字段而定（订阅数变化 / 观看数 / 观看时长）。

```json
{
  "views_28d_daily": [
    { "date": "2026-06-13", "value": 1520 },
    { "date": "2026-06-14", "value": 1380 },
    { "date": "2026-06-15", "value": 1690 }
  ]
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `points[].date` | `string` | 日期，格式 `YYYY-MM-DD` |
| `points[].value` | `number` | 该日的数据值： `subscribers_28d_daily` 为当日订阅数变化（可能为负）； `views_28d_daily` 为当日观看数； `watch_time_hours_28d_daily` 为当日观看时长（小时，整数） |

---

### 字段为 null 的情况

所有统计字段（总量/28 天变化量/每日点位）都可能为 `null` ，常见原因：

| 场景 | 说明 |
| --- | --- |
| 频道尚未同步 | 系统后台同步任务还未轮到该频道，此时整个 `analytics` 对象所有字段均为 `null` |
| 上游本次未返回该数据 | `channel/overview` 接口本次调用只返回了部分字段（例如只返回了总量，没有 28 天数据），未返回的字段保留上一次同步成功的旧值；如果从未成功过，则为 `null` |
| 上游采集失败 | 本次同步请求失败（错误信息记录在 `last_sync_error` 中），本次不会覆盖任何已有数据，所有字段保留上一次的值 |

---

### 完整响应示例

```json
{
  "channel_id": "UCxxxxxxxxxxxxxxxx",
  "analytics": {
    "total_subscribers": 12500,
    "total_views": 3200000,
    "total_watch_time_hours": 48400,
    "total_subscribers_28d": 320,
    "total_views_28d": 98000,
    "total_watch_time_hours_28d": 1450,
    "subscribers_28d_daily": [
      { "date": "2026-06-13", "value": 12 },
      { "date": "2026-06-14", "value": -3 },
      { "date": "2026-06-15", "value": 25 }
    ],
    "views_28d_daily": [
      { "date": "2026-06-13", "value": 1520 },
      { "date": "2026-06-14", "value": 1380 },
      { "date": "2026-06-15", "value": 1690 }
    ],
    "watch_time_hours_28d_daily": [
      { "date": "2026-06-13", "value": 52 },
      { "date": "2026-06-14", "value": 47 },
      { "date": "2026-06-15", "value": 58 }
    ]
  },
  "last_sync_at": "2026-06-15T08:00:00Z",
  "last_sync_error": null,
  "last_sync_success_at": "2026-06-15T08:00:00Z"
}
```

### curl 调用示例

```bash
curl -X GET 'https://video.inboxlinks.top/api/youtube/channel/v1/analytics/latest?channel_id=CHANNEL_ID' \
  -H 'x-api-key: token'
```

---

## 批量获取频道最新汇总数据

按频道列表批量获取最新汇总数据，支持游标分页。内部复用频道列表接口，对每个频道查询最新汇总数据后合并返回。

- **URL** ： `{服务器域名}/api/youtube/channel/v1/analytics/latest/list`
- **Method** ： `POST`
- **Content-Type** ： `application/json`

### Request Body

请求体与 [获取所有 YouTube 频道](https://video.inboxlinks.top/api-docs/youtube-channels/#%E8%8E%B7%E5%8F%96%E6%89%80%E6%9C%89-youtube-%E9%A2%91%E9%81%93) 一致（ `where` 、 `order` 、 `limit` 、 `cursor` 参数相同），用于筛选和分页频道。

### Response Body

```ts
// 游标分页响应
{
  datas: ChannelAnalyticsLatest[]; // 每个频道的最新汇总数据（类型同上方 ChannelAnalyticsLatest）
  total: number;                   // 符合条件的频道总数
  next: object | null;             // 下一页游标，传入下次请求的 cursor 字段
  prev: object | null;             // 上一页游标
}
```

### curl 调用示例

```bash
curl -X POST 'https://video.inboxlinks.top/api/youtube/channel/v1/analytics/latest/list' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: token' \
  --data-raw '{
    "where": null,
    "order": [["channel_id", "asc"]],
    "limit": 10
  }'
```