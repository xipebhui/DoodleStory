# Durable Agent Runtime 操作手册

## 适用范围

用于定位和处理 `NativeAgentRun` 关联的 Durable Workflow、Task、Attempt、Checkpoint、Gate、
Tool Effect 与控制命令。所有人工操作必须先确认 Conversation owner 和准确 ID；不得仅凭页面文案
或自然语言“继续”推断状态。

## 发布前备份与迁移

SQLite 部署先停止写入并复制数据库文件，再执行：

```bash
backend/.venv/bin/alembic current
backend/.venv/bin/alembic upgrade head
backend/.venv/bin/alembic current
```

Sprint 147 目标 revision 为 `s0t1u2v3w4x5`，新增 `agent_durable_commands`。迁移失败时保留原库和
失败库，不继续启动 Worker；修正明确原因后从备份重新执行。不要在有业务写入时用 downgrade
回滚，因为控制命令及其审计记录会丢失。

## 定位权威状态

按以下顺序确认事实：

1. `native_agent_runs.id`：页面 Run 状态、错误与终态时间。
2. `agent_durable_workflows.native_run_id`：`state_version`、当前 Checkpoint/Gate、期望输入。
3. `agent_durable_tasks.workflow_id`：失败、阻塞、运行和等待 Task。
4. `agent_durable_attempts.task_id`：Attempt 状态、lease owner/expiry、错误。
5. `agent_durable_tool_effects.attempt_id`：外部副作用是 prepared、submitted、succeeded、failed
   还是 unknown。
6. `agent_durable_commands.workflow_id`：用户命令、幂等键、目标、期望版本和已返回结果。
7. `agent_durable_checkpoints.workflow_id` 与 `agent_durable_plan_revisions.workflow_id`：恢复基线和
   不可变计划历史。

页面控制状态使用 owner-scoped
`GET /api/v1/agent-loop/runs/{run_id}/control-state`；人工操作使用统一
`POST /api/v1/agent-loop/runs/{run_id}/commands`，必须携带当前 `state_version` 和新的
`idempotency_key`。不要直接修改业务表来代替正常控制命令。

## Attempt 恢复

- `prepared` Attempt 可由恢复扫描重新入队。
- `running` 且 lease 未过期时不得抢占；lease 过期后恢复扫描将原 Attempt 标为 interrupted，并
  追加 resume Attempt。
- `waiting_for_input` Workflow、pending Gate、终态 Workflow 和 unknown Effect 不会自动恢复。
- `retry_task` 只接受 failed/blocked Task，且 Task 下不能存在 unknown Effect。
- `resume_run` 只选择安全的 failed/blocked Task；API 返回 409 时先重新读取控制状态，不重复猜测。

## unknown Effect 人工处理

unknown 表示 Provider 可能已经产生费用或资产，但本地没有可确认终态。处理前应使用
`provider_request_id` 与 Provider 后台、资产表和日志对账：

- 确认没有成功结果：发送 `resolve_unknown_effect`，`resolution=failed`，随后页面才允许重试。
- 确认成功：必须提供可核验 `result_ref`，再用 `resolution=succeeded`；不得填写占位引用。
- 无法核验：保持 unknown，不得自动重放或直接把 Task 改成 failed。

Native 图片 Effect 的人工结论会同步关联 Native Tool Step，避免 Workflow 已终态但页面仍显示
Tool 正在运行。

## 取消边界

`cancel_run` 会取消未开始的 Task/Attempt，并阻止新的外部副作用。已 submitted 的 Effect 转为
unknown，必须按上一节人工处理。取消不保证撤回 Provider 已接收的请求，也不保证退还已发生费用。

## SSE 与刷新

事件以 `native_agent_events.sequence` 为游标。浏览器重连时使用 `Last-Event-ID`；后端发现 cursor
缺口或游标超前会发送 `run.resync_required`，页面重新读取完整有界 Conversation Projection 和
控制状态。heartbeat 只表示连接存活，不代表模型或 Provider 有新进度。

## 回滚边界

- 可以回滚应用代码，但新旧版本必须理解当前数据库 revision；不允许让旧代码写入新状态机。
- Checkpoint、Plan Revision、Command 和 Tool Effect 是审计事实，不删除、不覆盖。
- Artifact 新版本通过追加产生；不得覆盖已经 Gate 审批的 hash。
- Provider 结果、积分和资产仍由各自领域表负责，Durable Runtime 只记录引用和执行事实。
- 需要恢复备份时必须整体停写并恢复同一时点数据库；不能只回滚单张 Durable 表。
