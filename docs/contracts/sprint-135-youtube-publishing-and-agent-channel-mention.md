# Sprint 135：YouTube 异步发布与 Agent 频道引用

## Status

Planned。必须在 Sprint 134 完成并验收后实施。

## Goal

让管理员可以从页面或 Native Agent 对话把审核通过的视频发布到明确的 YouTube 频道；异步任务
提交后立即结束当前请求，用户通过频道详情按钮手动获取结果，并能从 YouTube 视频反查最初的
Agent 生成视频。

## In scope

- 新增本地发布任务，关联频道、可发布视频和不可变的 `source_native_agent_video_id` 快照。
- 保存提交时的标题、描述、标签、封面 URL、视频 URL、可见性、AI 合成标记和计划发布时间。
- 调用 `/api/youtube/upload-video/v1/create` 创建异步任务，保存远程任务 ID 后立即返回。
- 创建接口不做网络失败自动重试；远程结果不明确时明确标记，禁止再次自动创建以免重复发布。
- 频道详情展示发布任务，通过“获取状态”按钮查询单个远程任务；不使用 while 循环、定时轮询或
  隐藏后台刷新。
- 将远程 `cancelled` 结合错误信息映射为本地“用户取消”或“发布失败”，不混为同一业务状态。
- 发布成功后保存 `youtube_video_id`、YouTube URL 和完成时间，并同步/关联永久已发布视频记录。
- 已发布视频必须同时保留 `publish_task_id`、`source_native_agent_video_id` 和唯一
  `youtube_video_id`，形成可直接查询的分析链：
  `NativeAgentVideo.id → PublishTask.id → youtube_video_id`。
- Native Agent 对话支持结构化 `@频道`，展示频道别名和远程名称；Runtime 只接受用户明确选择且
  当前可发布的频道 ID，不从普通文本猜测账号。
- 视频必须审核通过；Agent 提交真实发布前展示频道、视频、标题、可见性和时间并要求明确确认。
- Tool 成功提交后返回本地任务 ID 和远程任务状态，Agent 收尾当前对话，不等待 YouTube 完成。
- 计划发布时间遵循 API UTC、界面上海时区的现有时间合同。

## Out of scope

- 自动轮询、Webhook、任务完成提醒和定时数据回收。
- 网络结果不明确时自动重建发布任务。
- Agent 自动选择频道、跳过发布确认或发布未审核视频。
- YouTube 视频删除、评论、改封面、改可见性、改元数据或深度分析。
- 多平台发布、同一发布任务同时投递多个频道。

## Done means

- 页面和 Agent 都通过同一个应用服务创建发布任务，不各自实现第三方 HTTP 逻辑。
- 创建请求立即返回，不阻塞等待远程上传；重复提交保护不会产生第二个本地或远程任务。
- 用户点击“获取状态”后能看到等待、执行中、成功、失败或取消以及远程错误。
- 成功任务能从 `youtube_video_id` 直接查到发布任务、可发布视频和原始
  `NativeAgentVideo.id`，不依赖标题、时间或 URL 猜测。
- `@频道` 使用结构化 ID，重名、别名修改或远程名称变化不会把任务发到错误频道。
- 没有确认、频道异常、视频未审核、视频无公网 URL 时不调用外部创建接口。

## Verification

1. 后端测试覆盖请求映射、权限、审核门禁、重复提交、结果不明确、状态映射和三段 ID 关联。
2. Agent Tool 测试覆盖结构化频道引用、确认门禁、立即返回和同一应用服务复用。
3. 前端真实浏览器验证发布确认、任务列表、手动获取状态、错误恢复和 ID 追踪入口。
4. 使用专门测试视频和测试频道做一次真实发布 smoke；执行前由用户确认真实外部发布。
5. 运行空库 Alembic、后端测试、前端生产构建、`./scripts/check.sh` 和 `git diff --check`。

## Handoff

本 Sprint 完成后即可在独立合同中增加按频道和视频回收基础数据、内容复盘与迭代分析；分析逻辑
必须以 `source_native_agent_video_id` 和 `youtube_video_id` 的真实关联为输入。
