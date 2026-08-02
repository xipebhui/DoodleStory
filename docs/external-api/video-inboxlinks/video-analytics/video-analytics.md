---
title: "视频分析数据 | Video API 文档"
url: "https://video.inboxlinks.top/api-docs/video-analytics/"
requestedUrl: "https://video.inboxlinks.top/api-docs/video-analytics/"
siteName: "Video API 文档"
summary: "最新汇总数据（含时序 points 和留存曲线）"
adapter: "generic"
capturedAt: "2026-08-02T03:25:02.586Z"
conversionMethod: "defuddle"
kind: "generic/article"
language: "zh"
---

## 视频分析数据

用于获取已上传到 YouTube 的视频的分析数据，包括最新汇总数据（含时序 points）。

常见用途：

- 通过最新汇总数据的 `*_points` 时序字段查看观看者参与度、独立观看者、平均观看时长等趋势
- 获取视频发布以来的汇总数据和流量来源（ `how_viewers_find` ，含各来源占比）
- 获取观众参与度、独立观看人数、平均观看时长等时序数据
- 获取视频时间轴上的留存曲线（audience\_retention）数据
- 获取 Shorts 概览统计、点赞/点踩、展示次数与展示点击率等数据

---

## 获取视频最新汇总数据

获取指定视频自发布以来的最新汇总数据。此接口聚合了来自多个上游数据源的指标，包括基础统计、流量来源、观众参与度时序数据、独立观看者时序数据和平均观看时长时序数据。

### Query Parameters

| 参数名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `youtube_video_id` | `string` | ✅ | YouTube 视频 ID |

### 成功响应

- **HTTP 状态码** ： `200 OK`

```ts
/**
 * 时序数据点。
 * 不同指标的 value 类型不同，详见下方「各时序字段的数据形状」章节。
 */
type TimeSeriesPoint = {
  ms: number; // Unix 时间戳（毫秒），表示该时间桶的起始时间
  value: number; // 数据值（具体含义和单位取决于所属指标，见下文）
};

/**
 * 留存曲线数据点（audience_retention source）。
 * position 为视频时间轴的百分位索引（0..N-1），N 随视频长度变化，客户端不应硬编码。
 * value 为该位置的留存百分比（float），可超过 100（重看 / 回拖等真实信号），不做裁剪。
 */
type RetentionPoint = {
  position: number; // 视频时间轴百分位索引（整数，如 0 / 50 / 99）
  value: number; // 留存百分比（float，可超过 100）
};

/** 日期型数据点（video_overview 各卡片的趋势点位）。 */
type DateValuePoint = {
  date: string; // 日期，格式 YYYY-MM-DD
  value: number; // 数据值
};

/** 时间型数据点（impressions 小时级点位）。 */
type DateTimePoint = {
  time: string; // 时间点，格式 YYYY-MM-DD HH:MM:SS
  value: number; // 数据值
};

/** 日期+百分比文本数据点（impressions_click_rate 每日点位）。 */
type DatePercentPoint = {
  date: string; // 日期，格式 YYYY-MM-DD
  value: string; // 百分比展示文本，如 "0.0%"
};

/** 单个 source 的失败详情。只有失败的 source 会出现在 source_error 对象里。 */
type SourceErrorEntry = {
  status: 'failed'; // 目前只会出现 failed（success/empty 不会被收录）
  error_message: string | null; // 该 source 的原始错误信息
};

type VideoAnalyticsLatest = {
  youtube_video_id: string; // YouTube 视频 ID
  analytics: {
    // ── 基础统计 ──
    // views/watch_time_hours/subscribers/estimated_revenue 由上游 video_overview 卡片聚合
    // （若该来源无数字数据，views 会退回 shorts_analytics_summary 的观看数）；
    // likes 优先取自 likes_dislikes，缺失时退回 shorts_analytics_summary；
    // comments 只来自 shorts_analytics_summary。字段名/类型保持不变，仅数据来源更完整。
    views: number | null; // 自视频发布以来的观看数量
    watch_time_hours: string | null; // 自视频发布以来的总观看时长（小时）
    likes: number | null; // 点赞数量

    // ── 额外统计 ──
    subscribers: string | null; // 订阅者变化（如 "+2.4K"），原文透传
    estimated_revenue: string | null; // 预估收入（如 "$20.63"），原文透传
    comments: number | null; // 评论数

    // ── 热门观看者参与度（hot_viewers_engaged）──
    stayed_to_watch: string | null; // 留下观看比例，百分比字符串（如 "32.2%"），原文透传
    swiped_away: string | null; // 滑走比例，百分比字符串（如 "67.8%"），原文透传
    hot_viewers_engaged_points: TimeSeriesPoint[] | null; // 参与度时序数据，value 为 float（stayed-to-watch 百分比）

    // ── 独立观看者（unique_viewers）──
    unique_viewer: number | null; // 独立观看者聚合总数（整数）
    unique_viewers_points: TimeSeriesPoint[] | null; // 独立观看者时序数据，value 为 int（该时间桶的独立观看人数）

    // ── 平均观看时长（average_view_duration）──
    average_view_duration: string | null; // 平均观看时长文本（常见格式 "MM:SS"，也可能是纯秒数字符串），原文透传，有48小时延迟
    average_view_duration_points: TimeSeriesPoint[] | null; // 平均观看时长时序数据，value 为 int（该时间桶的平均观看时长，单位：毫秒），有48小时延迟

    // ── 观众留存（audience_retention）──
    // 注意：stayed_to_watch / average_view_duration 来自 audience_retention 卡片头部，
    // 与上方 hot_viewers_engaged.stayed_to_watch 和 average_view_duration source 各自独立，数值可能不同。
    audience_retention_stayed_to_watch: string | null; // 开头留存率，百分比字符串（如 "32.2%"），原文透传
    audience_retention_average_view_duration: string | null; // 平均观看时长文本（如 "0:09"），原文透传
    audience_retention_points: RetentionPoint[] | null; // 留存曲线，按 position 递增（见 RetentionPoint 类型）

    // ── 流量来源（how_viewers_find）──
    how_viewers_find: {
      source_name: string; // 来源名称
      views: number | null; // 来自该来源的观看次数
      percent: string | null; // 该来源占比展示文本（如 "98.1%"）
    }[];

    // ── Shorts 概览（shorts_analytics_summary，views/likes/comments 已合并进上方「基础统计」）──
    published_date: string | null; // 发布日期展示文本（如 "20 May 2025"）
    shorts_analytics_summary_visibility: string | null; // 可见性展示文本（自由文本，上游原文透传），值可能为 null；
    // 与下方 video_status_visibility 相互独立，互不覆盖

    // ── 视频类型 ──
    video_type: string | null; // 常见取值 "shorts"/"video"；默认请求或显式包含 video_status source 时返回；
    // 上游定义，未做强校验，取值集合可能变化

    // ── 视频状态摘要（video_status）──
    // visibility/restrictions/quality 均为上游定义的字符串 token，未做强校验（即不保证是封闭枚举），
    // 无法识别的状态上游会统一返回 "unknown"；常见取值参考下方「video_status 参考取值」；
    // 基础可见性与年龄/地区限制取值可同时出现（如 "public,age_restricted"）
    video_status_visibility: string | null; // 可见性（数组），多个值用逗号连接，如 "public,age_restricted"
    video_status_restrictions: string | null; // 限制（数组），多个限制用逗号连接，如 "age_restricted,made_for_kids"
    video_status_quality: string | null; // 质量（数组），如 "sd,hd"，多个 badge 用逗号连接
    video_status_unknown_statuses: unknown[] | null;
    // 无法识别的原始状态透传（protobuf 字段路径 + 原始值），仅供问题排查参考，
    // 不透明、不保证结构稳定，不建议解析

    // ── 视频概览趋势点位（video_overview）──
    // 注意：观看数/观看时长/订阅者/预估收入的聚合值已经由上方「基础统计」「额外统计」分组的
    // views / watch_time_hours / subscribers / estimated_revenue 覆盖，这里只新增各自的每日趋势点位。
    video_overview_views_points: DateValuePoint[] | null; // 观看数每日趋势
    video_overview_watch_time_hours_points: DateValuePoint[] | null; // 观看时长每日趋势
    video_overview_subscribers_points: DateValuePoint[] | null; // 订阅者每日趋势
    video_overview_estimated_revenue_points: DateValuePoint[] | null; // 预估收入每日趋势

    // ── 点赞/点踩（likes_dislikes）──
    // 注意：likes 已由上方「基础统计」分组覆盖，这里只新增 dislikes
    dislikes: number | null; // 点踩数

    // ── 展示次数（impressions）──
    impressions: number | null; // 展示次数总数
    impressions_points: DateTimePoint[] | null; // 展示次数小时级点位

    // ── 展示点击率（impressions_click_rate）──
    impressions_click_rate: string | null; // 展示点击率总值展示文本（如 "0.0%"）
    impressions_click_rate_points: DatePercentPoint[] | null; // 展示点击率每日点位

    // ── 同步失败详情 ──
    // key 是 source 名称（如 "hot_viewers_engaged"/"impressions"），value 是该 source 的失败详情。
    // 只收录本次同步中失败的 source；全部成功时为空对象 {};
    // 从未成功同步过 full_info 时为 null。
    source_error: Record<string, SourceErrorEntry> | null;
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
| **基础统计** | `views` | `number \| null` | 自视频发布以来的总观看数 |
|  | `watch_time_hours` | `string \| null` | 总观看时长（小时） |
|  | `likes` | `number \| null` | 点赞数量 |
| **额外统计** | `subscribers` | `string \| null` | 订阅者变化（如 “+2.4K”），上游原文透传 |
|  | `estimated_revenue` | `string \| null` | 预估收入（如 “$20.63”），上游原文透传 |
|  | `comments` | `number \| null` | 评论数 |
| **热门观看者参与度** | `stayed_to_watch` | `string \| null` | 留下观看比例（百分比字符串，如 `"32.2%"` ） |
|  | `swiped_away` | `string \| null` | 滑走比例（百分比字符串，如 `"67.8%"` ），与 `stayed_to_watch` 互补（两者之和 ≈ 100%） |
|  | `hot_viewers_engaged_points` | `TimeSeriesPoint[] \| null` | 参与度时序数据 |
| **独立观看者** | `unique_viewer` | `number \| null` | 独立观看者聚合总数（整数） |
|  | `unique_viewers_points` | `TimeSeriesPoint[] \| null` | 独立观看者时序数据 |
| **平均观看时长** | `average_view_duration` | `string \| null` | 平均观看时长文本（常见 `"MM:SS"` 格式，有48小时延迟） |
|  | `average_view_duration_points` | `TimeSeriesPoint[] \| null` | 平均观看时长时序数据，有48小时延迟 |
| **观众留存** | `audience_retention_stayed_to_watch` | `string \| null` | 开头留存率（百分比字符串，如 `"32.2%"` ）；来自 audience\_retention 卡片头部，独立于 `stayed_to_watch` |
|  | `audience_retention_average_view_duration` | `string \| null` | 平均观看时长文本；来自 audience\_retention 卡片头部，独立于 `average_view_duration` source |
|  | `audience_retention_points` | `RetentionPoint[] \| null` | 留存曲线，按 `position` 递增； `value` 为 float，可超过 100 |
| **流量来源** | `how_viewers_find` | `array` | 各来源名称、观看次数及占比（ `percent` ） |
| **Shorts 概览** | `published_date` | `string \| null` | 发布日期展示文本 |
|  | `shorts_analytics_summary_visibility` | `string \| null` | 可见性展示文本（自由文本，上游原文透传），值可能为 `null` ；与 `video_status_visibility` 相互独立 |
| **视频类型** | `video_type` | `string \| null` | 常见取值 `"shorts"` / `"video"` ；默认请求或显式包含 `video_status` source 时返回 |
| **视频状态摘要** | `video_status_visibility` | `string \| null` | 可见性（数组），多个值用逗号连接（如 `"public,age_restricted"` ），常见取值见下方参考表 |
|  | `video_status_restrictions` | `string \| null` | 限制（数组），多个限制用逗号连接，常见取值见下方参考表 |
|  | `video_status_quality` | `string \| null` | 质量（数组），如 `"sd,hd"` ，多个 badge 用逗号连接，常见取值见下方参考表 |
|  | `video_status_unknown_statuses` | `unknown[] \| null` | 无法识别的原始状态透传，仅供问题排查参考，不透明、不建议解析 |
| **视频概览趋势点位** | `video_overview_views_points` | `DateValuePoint[] \| null` | 观看数每日趋势 |
|  | `video_overview_watch_time_hours_points` | `DateValuePoint[] \| null` | 观看时长每日趋势 |
|  | `video_overview_subscribers_points` | `DateValuePoint[] \| null` | 订阅者每日趋势 |
|  | `video_overview_estimated_revenue_points` | `DateValuePoint[] \| null` | 预估收入每日趋势 |
| **点赞/点踩** | `dislikes` | `number \| null` | 点踩数 |
|  | `likes` | `number \| null` | 点赞数量 |
| **展示次数** | `impressions` | `number \| null` | 展示次数总数 |
|  | `impressions_points` | `DateTimePoint[] \| null` | 展示次数小时级点位 |
| **展示点击率** | `impressions_click_rate` | `string \| null` | 展示点击率总值展示文本 |
|  | `impressions_click_rate_points` | `DatePercentPoint[] \| null` | 展示点击率每日点位 |
| **同步失败详情** | `source_error` | `Record<string, SourceErrorEntry> \| null` | 本次同步中失败的 source（key 为 source 名称）；全部成功时为 `{}` ，从未同步过时为 `null` |
| **同步状态** | `last_sync_at` | `string \| null` | 最近一次同步尝试的时间（ISO 8601；成功或失败都更新） |
|  | `last_sync_error` | `string \| null` | 最近一次同步的错误信息（成功时为 `null` ） |
|  | `last_sync_success_at` | `string \| null` | 最近一次「成功」同步的时间（ISO 8601；仅成功时更新） |

### video\_status 参考取值

`video_status_visibility` / `video_status_restrictions` / `video_status_quality` 均为上游定义的字符串 token；下表列出 **当前已知** 的常见取值供参考， **不是封闭枚举** ——上游可能随时新增取值，本服务不做强校验，收到未在表中列出的 token 会原样透传（无法识别的状态上游一般会返回 `unknown` ，但不保证所有情况都归为该值）。调用方不建议写死穷举匹配，应对未知取值做好兜底展示。三个字段均为多值字段（数组语义），用逗号连接返回，例如 `visibility` 的 `"public,age_restricted"` 、 `restrictions` 的 `"age_restricted,made_for_kids"` 。

**`video_status_visibility`** （数组，逗号连接）：

| 取值 | 含义 |
| --- | --- |
| `public` | 视频公开可见 |
| `unlisted` | 仅持有链接的用户可见 |
| `private` | 视频私有 |
| `age_restricted` | 仅限已登录且年满 18 岁的观众观看 |
| `partially_blocked` | 视频在部分国家或地区不可见 |
| `blocked` | 视频在全球不可见 |
| `unknown` | 无法识别可见性状态 |

基础可见性（ `public` / `unlisted` / `private` ）与限制类取值（ `age_restricted` / `partially_blocked` / `blocked` ）可同时出现在同一个值里（如 `"public,age_restricted"` ）， `age_restricted` 不再覆盖基础可见性——带年龄/地区限制的视频也能明确读出它是公开还是不列出。

**`video_status_restrictions`** （数组，逗号连接）：

| 取值 | 含义 |
| --- | --- |
| `none` | 没有检测到限制 |
| `age_restricted` | 视频存在年龄限制 |
| `made_for_kids` | 视频被设置为面向儿童 |
| `copyright_no_visibility_impact` | 检测到版权限制，但当前不影响视频可见性 |
| `copyright_blocked_some_regions` | 因版权限制在部分国家或地区不可观看 |
| `copyright_blocked_worldwide` | 因版权限制在全球不可观看 |
| `potential_earning_limitation` | 发现版权声明；当前不影响视频，但未来启用 YouTube 获利后可能影响收益 |
| `unknown` | 无法识别限制状态 |

**`video_status_quality`** （数组，逗号连接）：

| 取值 | 含义 |
| --- | --- |
| `sd` | SD 版本可用 |
| `hd` | HD 版本可用 |
| `unknown` | 无法识别质量状态 |

---

### 各时序字段的数据形状

`hot_viewers_engaged_points` / `unique_viewers_points` / `average_view_duration_points` 三个字段都是 `TimeSeriesPoint[]` 数组，但 `value` 的 **含义和类型因指标而异** ； `video_overview_*_points` 是 `DateValuePoint[]` 、 `impressions_points` 是 `DateTimePoint[]` 、 `impressions_click_rate_points` 是 `DatePercentPoint[]` ，均按日期/时间递增排列。以下分别说明。

#### hot\_viewers\_engaged\_points — 观众参与度

按时间递增的 (`ms`, `value`) 序列。 `value` 是 **float** ，表示该时间桶的 “stayed-to-watch” 百分比；与 `swiped_away` 互补（即 100 - value ≈ swiped\_away 对应比例）。

```json
{
  "stayed_to_watch": "32.2%",
  "swiped_away": "67.8%",
  "hot_viewers_engaged_points": [
    { "ms": 1746082800000, "value": 0.0 },
    { "ms": 1748761200000, "value": 32.18 }
  ]
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `stayed_to_watch` | `string` | 上游聚合百分比字符串，原文透传，不做数值化 |
| `swiped_away` | `string` | 上游聚合百分比字符串，原文透传，与 `stayed_to_watch` 互补 |
| `points[].ms` | `number` (int) | Unix 毫秒时间戳，时间桶起始时间 |
| `points[].value` | `number` (float) | 该时间桶的 stayed-to-watch 百分比（0.0 ~ 100.0） |

#### unique\_viewers\_points — 独立观看者

按时间递增的 (`ms`, `value`) 序列。 `value` 是 **int** ，表示该时间桶的独立观看人数。

```json
{
  "unique_viewer": 2,
  "unique_viewers_points": [
    { "ms": 1755500400000, "value": 2 },
    { "ms": 1762066800000, "value": 1 }
  ]
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `unique_viewer` | `number` (int) | 上游提供的聚合总数；优先使用图例值，图例缺失时退化为 `sum(points.value)` |
| `points[].ms` | `number` (int) | Unix 毫秒时间戳，时间桶起始时间 |
| `points[].value` | `number` (int) | 该时间桶的独立观看人数 |

#### average\_view\_duration\_points — 平均观看时长

按时间递增的 (`ms`, `value`) 序列。 `value` 是 **int** ，表示该时间桶的平均观看时长， **单位为毫秒** 。 **该 source 有 48 小时的数据延迟。**

```json
{
  "average_view_duration": "0:09",
  "average_view_duration_points": [
    { "ms": 1747638000000, "value": 9517 },
    { "ms": 1747724400000, "value": 11100 }
  ]
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `average_view_duration` | `string` | 上游提供的时长文本（常见 `"MM:SS"` 格式，也可能是纯秒数字符串）， **原文透传** ，由调用方决定展示格式， **有48小时延迟** |
| `points[].ms` | `number` (int) | Unix 毫秒时间戳，时间桶起始时间 |
| `points[].value` | `number` (int) | 该时间桶的平均观看时长（毫秒）。示例： `9517` 表示约 9.5 秒 |

#### audience\_retention\_points — 观众留存曲线

按 `position` 递增的 (`position`, `value`) 序列，描述视频时间轴上各百分位的留存率。与其他三个 source 不同， `audience_retention` **没有“零总数短路”** ——即使头部聚合为 `"0%"` / `"0:00"` ， `points` 也按上游原文返回。

```json
{
  "audience_retention_stayed_to_watch": "32.2%",
  "audience_retention_average_view_duration": "0:09",
  "audience_retention_points": [
    { "position": 0, "value": 122.9 },
    { "position": 1, "value": 123.09 },
    { "position": 50, "value": 90.46 },
    { "position": 99, "value": 34.16 }
  ]
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `audience_retention_stayed_to_watch` | `string` | 开头留存率，来自 audience\_retention 卡片头部，原文透传； **独立于** `stayed_to_watch` （hot\_viewers\_engaged 来源） |
| `audience_retention_average_view_duration` | `string` | 平均观看时长，来自 audience\_retention 卡片头部，原文透传； **独立于** `average_view_duration` source |
| `points[].position` | `number` (int) | 视频时间轴的百分位索引（整数，从 0 开始）。上游桶数随视频长度变化， **不应硬编码长度** 。 |
| `points[].value` | `number` (float) | 该位置的留存百分比。 **可超过 100** （重看 / 回拖等真实信号），服务端不做裁剪。 |

#### video\_overview\_\*\_points — 视频概览趋势点位

按日期递增的 (`date`, `value`) 序列， `date` 格式为 `YYYY-MM-DD` 。四个字段（ `video_overview_views_points` / `video_overview_watch_time_hours_points` / `video_overview_subscribers_points` / `video_overview_estimated_revenue_points` ）分别对应观看数/观看时长/订阅者/预估收入这四张概览卡片各自的每日趋势，互相独立，某一个为 `null` 不影响其他。

```json
{
  "video_overview_views_points": [
    { "date": "2026-06-20", "value": 120 },
    { "date": "2026-06-21", "value": 98 }
  ]
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `points[].date` | `string` | 日期，格式 `YYYY-MM-DD` |
| `points[].value` | `number` | 该日的数据值，含义随所属字段而定（观看数/观看时长/订阅者变化/预估收入） |

#### impressions\_points — 展示次数点位

按时间递增的 (`time`, `value`) 序列， `time` 格式为 `YYYY-MM-DD HH:MM:SS` （ **小时级** 颗粒度，注意与 `TimeSeriesPoint.ms` 的毫秒时间戳不同）。

```json
{
  "impressions": 5000,
  "impressions_points": [
    { "time": "2026-06-20 00:00:00", "value": 210 },
    { "time": "2026-06-20 01:00:00", "value": 185 }
  ]
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `points[].time` | `string` | 时间点，格式 `YYYY-MM-DD HH:MM:SS` |
| `points[].value` | `number` | 该小时的展示次数 |

#### impressions\_click\_rate\_points — 展示点击率点位

按日期递增的 (`date`, `value`) 序列。与其他 points 字段不同， `value` 是 **百分比展示文本** （字符串），不做数值化。

```json
{
  "impressions_click_rate": "0.0%",
  "impressions_click_rate_points": [
    { "date": "2026-06-20", "value": "0.0%" },
    { "date": "2026-06-21", "value": "1.2%" }
  ]
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `points[].date` | `string` | 日期，格式 `YYYY-MM-DD` |
| `points[].value` | `string` | 该日的点击率展示文本，原文透传，不做数值化 |

#### source\_error — 同步失败详情

本次同步请求会并发拉取 11 个上游 source（ `hot_viewers_engaged` / `unique_viewers` / `average_view_duration` / `audience_retention` / `shorts_analytics_summary` / `video_overview` / `likes_dislikes` / `how_viewers_find` / `impressions` / `impressions_click_rate` / `video_status` ），每个 source 独立成功/失败。 `source_error` 是一个以 **source 名称为 key** 的对象，只收录 **本次请求中失败** 的 source；成功或“无数据”（视频太新等）的 source 不会出现在这里。

```json
{
  "source_error": {
    "impressions": { "status": "failed", "error_message": "upstream timeout after 20s" }
  }
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `source_error` 的 key | `string` | 失败的 source 名称，如 `"impressions"` |
| `source_error[key].status` | `string` | 目前恒为 `"failed"` （只收录失败的 source） |
| `source_error[key].error_message` | `string \| null` | 该 source 的原始错误信息 |

---

### 字段为 null 的情况

所有时序字段（ `*_points` ）以及对应的聚合值字段都可能为 `null` ，常见原因：

| 场景 | 说明 |
| --- | --- |
| 视频太新 | 视频刚发布，YouTube 后台尚未生成分析数据 |
| 上游无数据 | 上游数据源调用成功，但返回空数据（如视频观看量极低，无法产生统计） |
| 上游采集失败 | 该数据源在同步时出错（错误信息记录在 `last_sync_error` 中），其他数据源不受影响 |
| 尚未同步 | 系统的后台同步任务还未轮到该视频 |

---

### 完整响应示例

```json
{
  "youtube_video_id": "HpUSguQL_us",
  "analytics": {
    "views": 1234,
    "watch_time_hours": "56.3",
    "likes": 89,
    "subscribers": "+120",
    "estimated_revenue": "$20.63",
    "comments": 15,
    "stayed_to_watch": "32.2%",
    "swiped_away": "67.8%",
    "hot_viewers_engaged_points": [
      { "ms": 1746082800000, "value": 0.0 },
      { "ms": 1746169200000, "value": 12.5 },
      { "ms": 1748761200000, "value": 32.18 }
    ],
    "unique_viewer": 2,
    "unique_viewers_points": [
      { "ms": 1755500400000, "value": 2 },
      { "ms": 1762066800000, "value": 1 }
    ],
    "average_view_duration": "0:09",
    "average_view_duration_points": [
      { "ms": 1747638000000, "value": 9517 },
      { "ms": 1747724400000, "value": 11100 }
    ],
    "audience_retention_stayed_to_watch": "32.2%",
    "audience_retention_average_view_duration": "0:09",
    "audience_retention_points": [
      { "position": 0, "value": 122.9 },
      { "position": 1, "value": 123.09 },
      { "position": 50, "value": 90.46 },
      { "position": 99, "value": 34.16 }
    ],
    "how_viewers_find": [
      { "source_name": "YouTube search", "views": 580, "percent": "58.0%" },
      { "source_name": "Suggested videos", "views": 320, "percent": "32.0%" },
      { "source_name": "External", "views": 150, "percent": "10.0%" }
    ],
    "published_date": null,
    "shorts_analytics_summary_visibility": null,
    "video_type": "video",
    "video_status_visibility": "public,age_restricted",
    "video_status_restrictions": "age_restricted",
    "video_status_quality": "sd",
    "video_status_unknown_statuses": [],
    "video_overview_views_points": [
      { "date": "2026-06-20", "value": 120 },
      { "date": "2026-06-21", "value": 98 }
    ],
    "video_overview_watch_time_hours_points": null,
    "video_overview_subscribers_points": null,
    "video_overview_estimated_revenue_points": null,
    "dislikes": 3,
    "impressions": 5000,
    "impressions_points": [
      { "time": "2026-06-20 00:00:00", "value": 210 },
      { "time": "2026-06-20 01:00:00", "value": 185 }
    ],
    "impressions_click_rate": "0.0%",
    "impressions_click_rate_points": [
      { "date": "2026-06-20", "value": "0.0%" },
      { "date": "2026-06-21", "value": "1.2%" }
    ],
    "source_error": {}
  },
  "last_sync_at": "2026-04-22T14:30:00Z",
  "last_sync_error": null,
  "last_sync_success_at": "2026-04-22T14:30:00Z"
}
```

### curl 调用示例

```bash
curl -X GET 'https://video.inboxlinks.top/api/youtube/video/v1/analytics/latest?youtube_video_id=VIDEO_ID' \
  -H 'x-api-key: token'
```

---

## 批量获取视频最新汇总数据

按视频列表批量获取最新汇总数据，支持游标分页。内部复用已上传视频列表接口，对每个视频查询最新汇总数据后合并返回。

- **URL** ： `{服务器域名}/api/youtube/video/v1/analytics/latest/list`
- **Method** ： `POST`
- **Content-Type** ： `application/json`

### Request Body

请求体与 [查找已上传到 YouTube 的视频列表](https://video.inboxlinks.top/api-docs/uploaded-videos/#%E6%9F%A5%E6%89%BE%E5%B7%B2%E4%B8%8A%E4%BC%A0%E5%88%B0-youtube-%E7%9A%84%E8%A7%86%E9%A2%91%E5%88%97%E8%A1%A8) 一致（ `where` 、 `order` 、 `limit` 、 `cursor` 参数相同），用于筛选和分页已上传视频。

### Response Body

```ts
// 游标分页响应
{
  datas: VideoAnalyticsLatest[]; // 每个视频的最新汇总数据（类型同上方 VideoAnalyticsLatest）
  total: number;                 // 符合条件的视频总数
  next: object | null;           // 下一页游标，传入下次请求的 cursor 字段
  prev: object | null;           // 上一页游标
}
```

### curl 调用示例

```bash
curl -X POST 'https://video.inboxlinks.top/api/youtube/video/v1/analytics/latest/list' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: token' \
  --data-raw '{
    "where": null,
    "order": [["youtube_video_id", "desc"]],
    "limit": 10
  }'
```