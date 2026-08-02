---
title: "更新日志 | Video API 文档"
url: "https://video.inboxlinks.top/api-docs/changelog/"
requestedUrl: "https://video.inboxlinks.top/api-docs/changelog/"
siteName: "Video API 文档"
summary: "API 变更记录"
adapter: "generic"
capturedAt: "2026-08-02T03:25:25.287Z"
conversionMethod: "defuddle"
kind: "generic/article"
language: "zh"
---

## 更新日志

记录本 API 服务对第三方调用方有影响的变更（新增/修改/移除字段、接口行为变化等）。按时间倒序排列。

---

## 2026-08-01（不兼容变更 + 新增字段）

**影响接口** ： `GET /api/youtube/video/v1/analytics/latest` 、 `POST /api/youtube/video/v1/analytics/latest/list`

`analytics` 对象的 `video_status_visibility` 字段发生 **不兼容变更** ：

- **变更动机** ：旧的单值格式下，限制类取值会 **覆盖** 基础可见性——只要视频带有年龄限制， `video_status_visibility` 就整个变成 `age_restricted` ，除了 `private` 之外，调用方无法区分该视频到底是【公开】（ `public` ）还是【不列出】（ `unlisted` ）。
- **解决方案** ： `video_status_visibility` 由单值改为 **数组语义** （逗号拼接，与 `video_status_restrictions` / `video_status_quality` 格式一致）。基础可见性与年龄、地区限制取值现在 **同时返回** （如 `"public,age_restricted"` 、 `"unlisted,age_restricted"` ）， `age_restricted` 不再覆盖 `public` 或 `unlisted` ——带限制的视频也能明确读出其基础可见性。
- 调用方应按逗号 split 后处理各个 token，不要再假设该字段只有单个取值。参考取值表见 [视频分析数据](https://video.inboxlinks.top/api-docs/video-analytics/#video_status-%E5%8F%82%E8%80%83%E5%8F%96%E5%80%BC) 。

**新增字段** ： [YouTube 频道](https://video.inboxlinks.top/api-docs/youtube-channels/) 的 `YoutubeChannel` 新增 `avatar_url` （ `string | null` ，频道头像图片 URL）、 `banner_url` （ `string | null` ，频道横幅图片 URL）两个字段，影响接口 `POST /api/youtube/channel/v1/list` 、 `GET /api/youtube/channel/v1/one` 。

---

## 2026-07-23（不兼容变更）

**影响接口** ： `POST /api/youtube/video/v1/list` 、 `GET /api/youtube/video/v1/one`

[已上传视频](https://video.inboxlinks.top/api-docs/uploaded-videos/) 返回体中的 `datas` 字段 **形状变窄** ：服务端不再把原始上传请求体原样存储/透传， `datas` 改为每次请求时由 `title` / `description` / `tags` / `visibility` / `is_made_for_kids` / `contains_synthetic_media` / `has_paid_promotion` 这些类型化字段现场拼出的一个兼容对象，形状仍是 `UploadVideoTaskArgsBody` 的一个子集： `snippet.{title,description,tags}` + `status.{privacyStatus,selfDeclaredMadeForKids,containsSyntheticMedia}` + `paidProductPlacementDetails.hasPaidProductPlacement` 。

详见 [已上传视频 — `datas` 字段说明](https://video.inboxlinks.top/api-docs/uploaded-videos/#%E5%AD%97%E6%AE%B5%E8%AF%B4%E6%98%8E) 。

---

## 2026-07-22（新增接口 + 新增字段）

**新增接口** ： [修改视频信息](https://video.inboxlinks.top/api-docs/uploaded-videos/#%E4%BF%AE%E6%94%B9%E8%A7%86%E9%A2%91%E4%BF%A1%E6%81%AF) — `POST /api/youtube/video/v1/patch` ，批量修改已上传视频的标题/描述/标签/付费推广/面向儿童/合成媒体/成人限制/可见性/关联视频/备注（封面修改仍使用既有的 [修改视频封面](https://video.inboxlinks.top/api-docs/uploaded-videos/#%E4%BF%AE%E6%94%B9%E8%A7%86%E9%A2%91%E5%B0%81%E9%9D%A2) 接口，不在本接口范围内）。

**新增字段** ： [已上传视频](https://video.inboxlinks.top/api-docs/uploaded-videos/) 的 `UploadedVideo` 新增 `title` / `description` / `tags` / `has_paid_promotion` / `is_made_for_kids` / `contains_synthetic_media` / `is_adults_only` / `visibility` / `related_video_id` 九个字段。

**行为变化** ：既有的 [修改视频可见性](https://video.inboxlinks.top/api-docs/uploaded-videos/#%E4%BF%AE%E6%94%B9%E8%A7%86%E9%A2%91%E5%8F%AF%E8%A7%81%E6%80%A7) （ `change-visibility` ）与 [修改关联视频](https://video.inboxlinks.top/api-docs/uploaded-videos/#%E4%BF%AE%E6%94%B9%E5%85%B3%E8%81%94%E8%A7%86%E9%A2%91) （ `change-related-video` ）接口，调用上游成功后现在也会把新值写回本地对应字段（此前只调用上游、不落库）——这两个字段与新增的 `patch_video` 接口写入的是同一份数据。 [修改视频封面](https://video.inboxlinks.top/api-docs/uploaded-videos/#%E4%BF%AE%E6%94%B9%E8%A7%86%E9%A2%91%E5%B0%81%E9%9D%A2) （ `change-thumbnail` ）未受影响，本系统仍不存储封面地址。

以上均为纯新增/行为增强，不影响已有字段的类型和含义，无需修改现有集成代码即可兼容。

---

## 2026-07-21（不兼容变更 + 新增字段）

**影响接口** ： `GET /api/youtube/video/v1/analytics/latest` 、 `POST /api/youtube/video/v1/analytics/latest/list`

`analytics` 对象发生以下 **不兼容变更** ：

- **字段改名** ： `visibility` 改名为 `shorts_analytics_summary_visibility` （ `string | null` ，值可能为 `null` ）。此前该字段的取值优先来自 `video_status.visibility` ，缺失时才退回 `shorts_analytics_summary.visibility` ；现在改名后 **只** 来自 `shorts_analytics_summary` 这一个数据源，不再受 `video_status` 影响，与下方的 `video_status_visibility` 彻底独立。调用方需要把字段名从 `visibility` 改为 `shorts_analytics_summary_visibility` 。
- **取值格式变化** ： `video_status_visibility` 取值从任意展示文本（如 `"Public"` / `"Unlisted"` / `"Private"` / `"18+ only"` / `"Partially blocked"` ）变为上游定义的字符串 token（如 `public` / `unlisted` / `private` / `age_restricted` / `partially_blocked` / `blocked` / `unknown` ，未做强校验，取值集合可能变化）。
- **取值格式变化** ： `video_status_restrictions` / `video_status_quality` 从任意展示文本变为逗号拼接的上游定义 token（数组语义，未做强校验，取值集合可能变化），参考取值表见 [视频分析数据](https://video.inboxlinks.top/api-docs/video-analytics/#video_status-%E5%8F%82%E8%80%83%E5%8F%96%E5%80%BC) 。 **此前 “Copyright claim” 会被归一化成 “Claims” 的规则已废弃** ，上游现在直接返回参考表中的 token（如 `copyright_no_visibility_impact` ），调用方应改为匹配新的取值。

新增字段：

- `video_status_unknown_statuses` （ `unknown[] | null` ）：无法识别的原始状态透传，仅供问题排查参考，不透明、不保证结构稳定，不建议解析。
- `video_type` （ `string | null` ）：视频类型，常见取值 `"shorts"` / `"video"` （上游定义，未做强校验），默认请求或显式包含 `video_status` source 时返回。

详见 [视频分析数据](https://video.inboxlinks.top/api-docs/video-analytics/) 。

---

## 2026-07-13（新增接口 + 新增字段）

**新增接口** ： [设置频道头像](https://video.inboxlinks.top/api-docs/youtube-channels/#%E8%AE%BE%E7%BD%AE%E9%A2%91%E9%81%93%E5%A4%B4%E5%83%8F) — `POST /api/youtube/channel/v1/update_avatar` ，用法与 [设置频道横幅图片](https://video.inboxlinks.top/api-docs/youtube-channels/#%E8%AE%BE%E7%BD%AE%E9%A2%91%E9%81%93%E6%A8%AA%E5%B9%85%E5%9B%BE%E7%89%87) 一致，multipart 字段名同样是 `image` 。

**新增字段** ： [视频分析数据](https://video.inboxlinks.top/api-docs/video-analytics/) 的 `analytics` 对象新增 `video_status_restrictions` / `video_status_quality` 两个字段（均为 `string | null` ），来自上游新增的 `video_status` source：

- `video_status_restrictions` ：限制摘要，多个限制用逗号连接，例如 “Claims, Made for kids”。 **注意：当前实现会把上游的 “Copyright claim” 归一化成 “Claims”** ，按限制类型匹配时请使用 “Claims”，不要匹配 “Copyright claim”。
- `video_status_quality` ：质量摘要，常见值为 SD / HD / 4K；如果有多个 badge，会用逗号连接返回。

以上均为纯新增字段，不影响已有字段的类型和含义，无需修改现有集成代码即可兼容。

---

## 2026-07-11（接口文档补充 + 新增接口）

**新增文档** ：以下三个接口此前已上线但未写入文档，本次补充说明：

- [刷新频道统计数据](https://video.inboxlinks.top/api-docs/youtube-channels/#%E5%88%B7%E6%96%B0%E9%A2%91%E9%81%93%E7%BB%9F%E8%AE%A1%E6%95%B0%E6%8D%AE) — `POST /api/youtube/channel/v1/refresh-stats`
- [刷新视频统计数据](https://video.inboxlinks.top/api-docs/uploaded-videos/#%E5%88%B7%E6%96%B0%E8%A7%86%E9%A2%91%E7%BB%9F%E8%AE%A1%E6%95%B0%E6%8D%AE) — `POST /api/youtube/video/v1/refresh-stats`
- [修改关联视频](https://video.inboxlinks.top/api-docs/uploaded-videos/#%E4%BF%AE%E6%94%B9%E5%85%B3%E8%81%94%E8%A7%86%E9%A2%91) — `POST /api/youtube/video/v1/change-related-video`

上述两个“刷新统计数据”接口均为 **同步阻塞** 调用，耗时约 20 秒，建议客户端超时时间设置为 60 秒以上。

**新增接口** ： [修改视频封面](https://video.inboxlinks.top/api-docs/uploaded-videos/#%E4%BF%AE%E6%94%B9%E8%A7%86%E9%A2%91%E5%B0%81%E9%9D%A2) — `POST /api/youtube/video/v1/change-thumbnail` ，根据公开图片地址修改指定视频的封面。

---

## 2026-07-08

**影响接口** ： `GET /api/youtube/video/v1/analytics/latest` 、 `POST /api/youtube/video/v1/analytics/latest/list`

`analytics` 对象新增以下字段：

- **Shorts 概览** ： `published_date` / `visibility`
- **视频概览趋势点位** ： `video_overview_views_points` / `video_overview_watch_time_hours_points` / `video_overview_subscribers_points` / `video_overview_estimated_revenue_points` （ `DateValuePoint[]` ）
- **点赞/点踩** ： `dislikes` / `likes`
- **展示次数** ： `impressions` / `impressions_points` （ `DateTimePoint[]` ）
- **展示点击率** ： `impressions_click_rate` / `impressions_click_rate_points` （ `DatePercentPoint[]` ）

新增 `how_viewers_find` 数组字段（各来源名称、观看次数及占比 `percent` ），来自 YouTube 的“观众如何找到你的视频”数据。

`views` / `likes` / `comments` / `watch_time_hours` / `subscribers` / `estimated_revenue` 这几个已有字段的 **数据来源更完整** ：现在会聚合 Shorts 概览、视频概览卡片、点赞/点踩等多个上游数据源（ `views` 优先取视频概览卡片的观看数，缺失时退回 Shorts 观看数； `likes` 优先取点赞/点踩来源，缺失时退回 Shorts 点赞数），字段名和类型不变。

以上均为 **新增字段或数据完整性增强** ，不影响已有字段的类型和含义，无需修改现有集成代码即可兼容。详见 [视频分析数据](https://video.inboxlinks.top/api-docs/video-analytics/) 。

**字段移除（不兼容变更）** ： `avg_percentage_view` 、 `four8h_views` 、 `oneh_views` 三个字段已从 `analytics` 对象中 **正式移除** （此前曾短暂标记为弃用，现已彻底删除，不再出现在响应体里）。依赖这三个字段的调用方需要停止读取，改用其他等效数据源或移除相关展示逻辑。

**新增字段** ： `source_error` （ `Record<string, SourceErrorEntry> | null` ）——以 source 名称为 key 的对象，收录本次同步中失败的上游 source，value 为 `{status: "failed", error_message}` ；只收录失败的 source，成功/无数据的不会出现。全部成功时为 `{}` ，从未成功同步过时为 `null` 。纯新增字段，不影响已有字段兼容性。

---

## 2026-07-01

**影响接口** ： `GET /api/youtube/channel/v1/analytics/latest` 、 `POST /api/youtube/channel/v1/analytics/latest/list`

`analytics` 对象结构调整（ **不兼容变更** ）：

- 移除字段： `subscribers` 、 `views` 、 `watch_time_hours` （原字符串格式，如 `"9.9M"` ）、 `estimated_revenue`
- 新增字段：
	- 总量： `total_subscribers` / `total_views` / `total_watch_time_hours` （均为整数）
		- 近 28 天变化量： `total_subscribers_28d` / `total_views_28d` / `total_watch_time_hours_28d`
		- 近 28 天每日点位： `subscribers_28d_daily` / `views_28d_daily` / `watch_time_hours_28d_daily` （ `ChannelOverviewDailyPoint[]` ）

调用方需要将 `subscribers` / `views` / `watch_time_hours` 的读取方式从字符串字段改为对应的 `total_*` 数字字段，并移除对 `estimated_revenue` 的依赖（该字段已不再提供）。详见 [频道分析数据](https://video.inboxlinks.top/api-docs/channel-analytics/) 。