# Sprint 134：YouTube 频道账号与可发布视频基础

## Status

Active（Ready for implementation）。本 Sprint 只建立频道账号、账号知识、可发布视频和手动数据
同步基础，不调用真实发布接口。

## Goal

让管理员在 DoodleStory 内管理 YouTube 频道，维护频道别名、AI 账号定义和对标账号，并把
Native Agent 生成的视频登记成可追踪、可发布的视频资产。

## In scope

- 接入 `YTB_PUBLISH_URL`、`YTB_PUBLISH_API_KEY`，密钥只在后端使用。
- 从 `/api/youtube/channel/v1/list` 手动同步频道并按 `channel_id` 幂等新增或更新本地记录。
- 频道保存远程名称、Handle、头像、状态、同步时间和错误；本地维护别名、账号定位、目标受众、
  阶段目标、AI 说明和运营备注。
- 支持为频道维护多个对标账号，保存平台、名称、主页 URL/平台 ID 和备注。
- 频道列表、详情、账号定义编辑；只有管理员可访问。
- 频道详情通过按钮手动获取频道最新分析数据，不增加定时任务或循环轮询。
- 新增可发布视频登记：必须关联一个当前用户可访问且已成功生成的 `NativeAgentVideo.id`，并保存
  视频 URL、封面 URL、默认标题、描述、标签、计划发布时间、AI 合成标记和审核状态。
- `source_native_agent_video_id` 使用外键和唯一约束固定 Agent 生成视频与可发布视频的关系。
- 按频道手动同步已发布视频和基础数据；视频列表请求必须使用服务端实际接受的
  `where.one.channel_id` 条件，禁止拉取无频道约束的全局视频池。
- 列表使用后端分页和有界摘要，详情单独加载。

## Out of scope

- 创建、取消或自动轮询 YouTube 发布任务。
- Native Agent `@频道`、Agent 发布 Tool 或自动内容分析。
- YouTube OAuth、在 DoodleStory 内绑定新账号或管理 API Key。
- 自动定时同步、Webhook、深度视频分析、评论、修改或删除 YouTube 视频。
- 支持 YouTube 以外的平台账号。

## Done means

- 管理员可以同步并查看 17 个真实频道；重复同步不会产生重复频道。
- 普通用户不能读取或修改频道、账号定义、对标账号和同步数据。
- 频道别名和 AI 账号定义可保存、刷新后仍存在，远程同步不会覆盖本地维护字段。
- 随机频道的最新分析可以通过按钮成功同步，失败时保留上次成功数据并显示本次明确错误。
- Native Agent 视频只能登记一次，并能从可发布视频稳定反查原始 `NativeAgentVideo.id`。
- 已发布视频同步只返回目标频道数据，不混入 API Key 下其他频道的视频。
- 未审核、缺少公网视频 URL 或无权访问的 Native Agent 视频不能进入可发布状态。

## Verification

1. 后端测试覆盖频道幂等同步、本地字段不被覆盖、管理员权限、远程错误和频道过滤请求结构。
2. 数据库测试覆盖频道唯一键、对标账号关系和 `source_native_agent_video_id` 外键/唯一约束。
3. 使用当前 `.env` 做一次真实只读 smoke：频道列表、随机频道分析、该频道已发布视频。
4. 前端验证列表/详情/编辑/加载/空态/错误态和手动同步，不出现隐藏自动轮询。
5. 运行空库 Alembic、后端测试、前端生产构建、`./scripts/check.sh` 和 `git diff --check`。

## Handoff

Sprint 135 只复用本 Sprint 的频道与可发布视频事实来源，不重复建立账号或视频表。真实发布前
必须再次校验频道正常、视频已审核且公网 URL 可用。
