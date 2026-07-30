# Sprint 138：YouTube 频道研究 Tool

状态：完成

## Goal

把 YouTube Data API v3 的公开频道研究能力接入同级多平台 Import 服务，并在
DoodleStory Native Agent 中提供一个模型可参数化调用的只读 Tool。

## In Scope

- Import 服务新增 YouTube 官方 API adapter 和
  `POST /api/v1/youtube/channel-insights`。
- 输入支持频道 URL、`@handle`、handle 文本和 `UC...` Channel ID。
- 接口返回频道资料与统计、最近公开视频资料与播放/点赞/评论数，以及每条视频的顶级评论。
- 频道头像和每条视频最高可用分辨率的封面必须真实下载到 Import 任务目录；响应同时返回
  原始图片 URL 和本地文件路径。
- 视频结果包含标题、完整描述、标签、发布时间、时长、公开状态与封面信息。
- Import 接口开放 `video_limit`（1–10）、`comments_per_video`（0–20）和
  `comment_order`（`relevance` / `time`）。
- DoodleStory 新增 `inspect_youtube_channel` Native Agent Tool；模型可根据任务决定
  频道标识、最近视频数量、评论数量和排序。
- Agent Tool 使用更窄的上下文边界：最多 5 条视频、每条最多 10 条评论。
- DoodleStory Tool 将视频封面作为视觉 Tool Output 提供给模型，文字结果保留标题和描述。
- Tool 进入 Skill 管理白名单目录，未勾选时不向模型暴露。
- 修正 YouTube 发布 Tool 绕过 Skill 白名单的问题。
- Compose 把现有 `YTB_DATA_API_V3_KEY` 注入 Import 服务，但不记录或返回 Key。

## Out of Scope

- OAuth、YouTube Analytics API 和账号私有指标。
- 评论回复分页、全部评论导出、按点赞数遍历全量评论后排序。
- 搜索关键词、频道推荐、视频下载、字幕或音频提取。
- 定时同步、数据库快照和趋势计算。
- 自动重试、备用抓取源或非官方 YouTube 数据源。

## Done Means

- 使用 `.env` 中的 Key 可通过 Import 服务读取 `@HistoryEagle-u9d` 的频道信息、最新
  视频统计和评论。
- 非法频道标识、缺少 Key、Google API、评论读取或封面下载错误均明确失败，不返回伪造或
  部分结果。
- Native Agent 只在固定 Skill Version 勾选 `inspect_youtube_channel` 时暴露该 Tool。
- 模型看到参数用途和边界，可以为单视频快速查看或 3–5 条近期对比选择不同参数。
- `publish_youtube_video` 同时要求白名单授权和已确认的结构化发布上下文。

## Verification

- Import 服务单元测试覆盖频道解析、请求参数、响应映射、头像/封面下载和错误处理。
- DoodleStory 测试覆盖客户端映射、Tool 参数边界和 Runtime 白名单。
- 使用用户给定频道执行一次真实 Import 接口 smoke。
- 两仓库测试、DoodleStory `./scripts/check.sh`、Compose 配置展开通过。

实际结果：

- Import 服务 17 项测试通过。
- DoodleStory `./scripts/check.sh` 通过 328 项后端测试、空库迁移、8 项前端测试、
  前端生产构建、Remotion 类型检查与 5 项测试。
- 使用 `https://www.youtube.com/@HistoryEagle-u9d` 完成真实接口与 Agent Tool smoke：
  成功取得频道资料、最新视频标题、完整描述、标签、播放/点赞/评论数和 2 条评论，并下载
  `800×800` 频道头像与 `1280×720` 视频封面；Tool 输出包含 1 份文字结果和 2 份视觉结果，
  未暴露服务端文件路径。

## Handoff

下一 Sprint 再决定是否将研究结果落为长期频道快照，并基于多次快照计算视频表现趋势；本
Sprint 只提供实时、只读的公开数据 Tool。
