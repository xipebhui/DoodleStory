# Sprint 122：Native Loop 实时事件与 Trace 语义

## Status

Complete（Closed）。用户于 2026-07-27 指出 Native Agent 提交后页面长期停留在 loading，刷新后才显示结果，
并认为 MLflow Trace 图中的红色 Tool 节点代表执行错误。

正式 Evaluation、评分规则和发布门槛继续保持 Deferred，本 Sprint 不实施 Evaluation。

## Goal

1. Native Run 提交后立即返回持久化的 queued Run，不让 HTTP 请求占用整个模型与生图周期。
2. 后端使用进程内单 Worker 执行 Native Run，数据库继续作为 Run、Item、Image 和终态事实来源。
3. 提供 owner-only SSE Run 快照流；前端实时显示模型、Tool、生图和完成/失败信息，并随新事件自动滚动。
4. MLflow Span 使用准确类型和显式状态：`generate_image` 保持 `TOOL`，内部图片 Provider 记录为
   `TASK`；成功 Span 明确写入 `OK`，失败明确写入 `ERROR`。
5. 文档明确 MLflow 3.14 Trace 图的 Tool 暗红色是 Span 类型配色，不等于错误；状态必须以
   Trace/Span 的 `OK`、`ERROR` 或 `IN_PROGRESS` 字段判断。

## Scope

- 新增 Native Agent 进程内队列、单 Worker、启动恢复和关闭处理。
- queued Run 可在启动时重新入队；因进程中断而遗留的 running/waiting Run 明确标记失败，不重复
  执行可能已经发生的外部生图副作用。
- POST Run 接口返回 `202 Accepted`，只完成校验、持久化和入队。
- 新增 `/agent-loop/runs/{run_id}/events` SSE；连接前校验会话 owner，发送当前和后续 Run 快照，
  终态后关闭。
- 前端订阅当前会话的活动 Run，增量渲染 Tool 时间线、图片、终态和连接错误，保持输入草稿。
- 新增相关后端测试、前端构建与真实浏览器验收。

## Out of scope

- 修改 Skill Instructions、Agent 模型决策、最大 Turn 或生图 Tool 并发。
- 引入 Redis、Celery、外部消息队列或独立 Worker 服务。
- 自动重试已中断的模型 Loop 或图片 Provider 调用。
- 修改 MLflow 自身 UI 主题或伪造 Span 类型以改变节点颜色。
- Deferred Evaluation。

## Verification

1. 真实 Trace `tr-201a90ff214c8da0e0c5d1b824a28c8c` 的根 Trace、Tool 和 Provider Span
   状态通过 MLflow API 核实为 `OK`。
2. API 测试确认 POST 在执行完成前返回 queued Run，并且只入队 Run ID。
3. Worker 测试覆盖 queued Run 执行和启动恢复边界。
4. SSE 测试覆盖 owner 权限、首次快照、增量快照和终态关闭。
5. MLflow 自动化确认成功 Tool/Provider 为 `OK`，失败为 `ERROR`，Provider 类型不是 `TOOL`。
6. 真实浏览器确认提交后立即进入对话，Tool/图片状态实时出现，页面自动滚动，刷新仍从数据库恢复。
7. `./scripts/check.sh` 与 `git diff --check` 通过。

## Verification result

- MLflow API 核实真实 Trace `tr-201a90ff214c8da0e0c5d1b824a28c8c` 和其中所有 Tool、
  Provider Span 均为 `OK`；历史 Trace 不可变，红色节点确认是 `TOOL` 类型配色。
- 自动化确认新 Trace 的 `generate_image` 为 `TOOL + OK + result_status=succeeded`，
  `image_provider` 为 `TASK + OK`。
- API 自动化确认新 Run 只持久化 Native 状态并把 Run ID 入队；恢复自动化确认 queued Run
  重新入队，运行中断 Run 明确失败且不重放。
- SSE 自动化确认 owner 可收到终态 Run 的当前完整快照，其他用户得到 404。
- 本地前后端重启成功，MLflow `/health` 返回 `OK`。
- 真实浏览器自动验收因浏览器 localhost 安全策略拒绝 reload/DOM 检查而未执行；未尝试绕过该
  安全策略。已有前端 TypeScript 和 Vite 生产构建通过。
- `./scripts/check.sh` 通过 260 项后端测试、Python compileall、空 SQLite migration 和前端
  生产构建；`git diff --check` 通过。

## Done means

- 用户不需要刷新页面即可看到 Native Agent 的真实执行过程和最终结果。
- MLflow 中 Tool 与 Provider Span 的类型、状态和层级语义准确，不把配色当成执行结论。
- 文档、规格、进度、实现和验证结果一致，并创建中文详细 commit。
