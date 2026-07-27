# Sprint 123：Native Agent 可恢复执行与持久化事件流

## Status

Complete（Closed）。用户要求一次完成已确认的第 1–4 阶段，并明确暂不实施 Worker lease。
正式 Evaluation 继续保持 Deferred。

## Goal

在不重写 OpenAI Agents SDK Tool Loop 的前提下，为 Native Agent 增加最小可靠运行层：

1. 使用 `Runner.run_streamed()` 消费 SDK 原生模型、文本和 Tool 生命周期事件。
2. 数据库分别保存 Run 事实、Step 状态、SDK 模型上下文和面向 UI 的结构化事件。
3. 服务重启后，只在数据库和 SDK Session 能证明没有不确定外部副作用时恢复执行。
4. 生图 Tool 使用稳定 `tool_call_id` 派生幂等键，明确区分准备、执行、成功、失败和不确定状态。
5. SSE 使用持久化事件序号和 `Last-Event-ID` 补发遗漏事件，前端实时展示模型输出和工具进度。

## Scope

- 新增 Native Agent Step、Event 和 SDK Context Item 数据表与迁移。
- Step 覆盖模型调用、工具调用和最终输出；Tool Step 保存 `tool_call_id`、幂等键、attempt、
  输入摘要、输出引用、错误和时间。
- Run 创建、启动、模型响应、文本增量、Tool 状态、checkpoint 和终态写入有序 Event。
- `generate_image` 在 Provider 调用前提交 prepared/running 状态；成功时在同一事务保存图片、
  Tool Step、Tool Result 和 Event。
- 已成功的同一 Tool 幂等键再次执行时直接返回已有图片，不重复调用 Provider。
- 使用 Agents SDK Session 接口保存完整模型上下文；恢复前核对已成功 Tool 的 SDK Tool Output。
- SSE 支持查询参数 `after` 和请求头 `Last-Event-ID`，按 Run 内单调 sequence 补发事件。
- 前端基于持久化事件展示实时模型文本、模型轮次、Tool 进度、图片和终态。

## Out of scope

- Worker lease、heartbeat、多实例并发领取或外部消息队列。
- 人工审批、Workflow DSL、多 Skill、MCP、脚本 Tool 或新媒体 Tool。
- 修改故事创作阶段、Style 注入时机或 Skill Instructions。
- 自动重放状态不确定的图片 Provider 调用。
- Deferred Evaluation、评分器与发布门槛。

## Recovery boundary

- queued Run 正常重新入队。
- 只有模型调用中断，且不存在未确认 Tool 副作用时，可以从 SDK Session checkpoint 继续。
- Tool Step 为 succeeded 且 SDK Session 中存在对应 Tool Output 时，可以继续后续模型轮次。
- Tool Step 为 prepared/running，或 succeeded 但 SDK Session 缺少对应 Tool Output 时，标记
  unknown 并让 Run 明确失败；不得自动重新生图。

## Verification

1. 自动化确认使用 `Runner.run_streamed()`，并消费模型文本、模型完成和 Tool 语义事件。
2. 自动化覆盖 Tool 幂等命中、prepared/running/succeeded/failed/unknown 状态。
3. 自动化覆盖安全恢复与不确定 Tool 拒绝重放。
4. 自动化覆盖 SSE 游标补发、owner 隔离和终态关闭。
5. 前端生产构建、空库 migration、Python compileall 和相关后端测试通过。

## Verification result

- 针对性 11 项 Native Agent 测试通过，覆盖真实 Function Tool、稳定 Tool Call 幂等复用、
  SDK Context Session、模型文本 delta、Step/Event 落库、纯模型安全恢复、运行中 Tool unknown
  阻断、SSE Event ID 和 owner 隔离。
- `./scripts/check.sh` 通过 263 项后端测试、Python compileall、从空 SQLite 升级到 head 和前端
  TypeScript/Vite 生产构建。
- `git diff --check` 通过。
- 本次验证没有调用真实模型或图片 Provider；正式 Evaluation 继续 Deferred。
- 闭合后的轻量修正移除了 Tool Description 中重复的 Style 快照；前端改为携带会话凭证并逐条
  消费 `native.event`。真实失败记录证明 Provider 与 Tool 已完成，后续模型视觉 Review 无法
  下载 OSS URL；Tool 图片现从已保存资产编码为 Responses API 支持的 Base64 data URL。修正后
  11 项定向测试、前端构建、真实资产编码和带 Cookie 的 SSE 请求通过。
- 后续核查发现 Style 原先只有 Tool Description 一条模型输入路径，移除后真实 Run 从所选
  “极简线稿情绪漫画风”漂移成“真实电影感”。Style 已迁移到只约束图片规划、Prompt 和 Review
  的 `image_generation_context`。当前中转站实测不返回官方 reasoning summary 事件，因此 UI
  改为展示模型主动输出的可核查创作决策和每次 Tool Call 实际 Prompt，Runtime 状态降为辅助；
  不把系统日志或伪造内容标成模型思考。修正后 12 项定向测试和前端构建通过。

## Done means

- 用户提交后实时看到模型与 Tool 执行，而不是轮询猜测状态。
- 刷新或 SSE 重连不会丢失已落库事件。
- 服务重启不会重复执行无法确认结果的生图调用。
- Agents SDK 继续负责模型 Tool Loop，Runtime 只负责可靠执行边界。
- 文档、进度、规格、实现和验证一致，并创建中文详细 commit。
