# Sprint 147：Agent 统一控制命令与恢复收敛

## Status

Active。依赖 Sprint 144–146 的 Durable Runtime、动态计划、文章 Gate、媒体 Task 和图片质量
Gate。2026-08-01 根据真实全媒体验收结果，将原 Draft 收紧为一次可完成、可验证的控制与恢复闭环；
Follow-up Run 和 Probe 分支移交后续 Sprint。

## Goal

让当前 Durable Run 的批准、修改、Task 重试、取消、恢复和 unknown Effect 人工处理只通过一个
带 owner、幂等键和 Checkpoint state version 校验的命令入口执行；修复文章 Review Gate 与非文案
媒体 Run 的终态阻塞，并保证刷新、SSE 重连和后端重启后页面收敛到数据库权威状态。

## In Scope

### 1. 统一控制命令

- 实现统一命令：`approve_gate`、`request_changes`、`retry_task`、`cancel_run`、`resume_run`、
  `resolve_unknown_effect`。
- 每个命令校验 Conversation owner、Run/Task/Gate 当前状态、`allowed_actions`、Checkpoint
  `state_version` 与 Tool Effect 状态。
- 命令使用客户端 `idempotency_key`；相同 key 与相同 payload 返回原结果，不同 payload 明确冲突。
- 旧文案审批、媒体 Gate、Panel 重跑和取消入口保留，但统一委托给同一命令服务，避免双状态机。

### 2. 恢复、取消与终态收敛

- `waiting_for_input`、终态 Task、有效 lease、unknown Tool Effect 和取消中的 Run 不得被启动恢复。
- `retry_task` 只重试明确失败/中断且无 unknown Effect 的 Task；`resume_run` 只恢复有安全 Attempt 的
  failed Run。
- `cancel_run` 取消未开始的下游 Task/Attempt，阻止新的外部副作用；已 submitted 的 Effect 转为
  unknown，等待人工明确处理。
- `resolve_unknown_effect` 只允许用户明确标记为 `failed` 或提供可核验结果引用后标记 `succeeded`。
- SSE 使用 event sequence 和 workflow state version；刷新、重连、终态与 cursor 缺口均重新拉取有界
  Conversation Projection，前端不保留本地猜测状态。

### 3. 真实链路阻塞修复

- `article_review` Approval 必须映射到 `editorial_review_gate`，不能再次创建
  `article_draft_review` Gate。
- 只有文案 Workflow Skill 才初始化 ARTICLE_TASKS；纯媒体 Skill 不得因无关文案 Task 无法结束。
- 字幕失败后的重试复用已成功音频，不得重新调用 TTS；同一音频的失败重试必须有上限。
- Skill 要求图片检查时，`inspect_image` 成功前不得渲染视频。

### 4. 聊天控制与可见等待状态

- 页面只展示当前 `allowed_actions` 允许的操作，并携带当前 `state_version`。
- 按钮文案说明真实后果；重复、过期、越权、unknown Effect 和不可恢复状态显示明确错误。
- 长 Tool 等待展示 Tool 名、已等待时间、单次超时和当前/最大尝试次数；SSE heartbeat 不伪装成业务进度。

### 5. 故障验收与操作文档

- 覆盖 Gate 重启、失败 Task 重试、unknown Effect、取消、SSE cursor 缺口和终态刷新。
- 更新运行时操作文档：数据库备份/迁移、Attempt 恢复、unknown Effect 人工处理、Run/Task/
  Checkpoint/Tool Effect 定位与回滚边界。
- 保存真实 Conversation/Run/Task/Attempt/Checkpoint/Gate/Effect ID 和浏览器证据。

## Out of Scope

- Follow-up Run、`parent_run_id`、`continued_from_checkpoint_id`。
- `create_probe`、Probe Artifact 采纳或分支预算。
- 跨项目/跨用户 Memory、团队审批、审批 SLA、通知中心。
- 自动发布、外部工作流引擎、生产多实例调度或新的媒体类型。

## Deliverables

- 统一 Durable Command 表、服务、owner-scoped API 和旧入口 adapter。
- 控制命令幂等/并发/过期 revision、恢复/取消/unknown Effect 和 SSE 收敛实现。
- Review Gate、纯媒体终态、字幕重试复用和图片检查顺序修复。
- 聊天状态驱动操作与长 Tool 等待信息。
- 故障矩阵、操作手册、浏览器验收记录和 Sprint QA 报告。

## Done Means

- 用户可在聊天中完成：选题确认 → 正文确认 → Review 确认 → 图片方案确认 → 图片质量确认 →
  终态；刷新、SSE 断开或后端重启不会丢失当前状态或重复执行副作用。
- 六类控制命令均由后端 `allowed_actions + state_version` 决定；重复请求、过期请求、越权请求和
  unknown Effect 均有明确结果。
- 非文案媒体 Run 成功生成最终资产后可正常结束；失败字幕不会触发重复 TTS；要求图片检查的 Skill
  不会跳过检查直接渲染。
- 终态 Run 不显示等待执行，取消/失败/unknown 状态可理解且可恢复或人工处理。

## Verification

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest \
  backend.tests.test_agent_control_commands \
  backend.tests.test_durable_agent_runtime \
  backend.tests.test_native_agent_loop \
  backend.tests.test_agent_runner_recovery
npm --prefix frontend test
npm --prefix frontend run build
./scripts/check.sh
git diff --check
```

Required fault drills:

- 选题、正文、Review、图片质量 Gate 等待时重启。
- 失败/中断 Task 重试、unknown Effect 阻止重试及人工处理。
- 取消 queued/running Run，确认未开始 Task 不再执行。
- 重复命令、并发命令、过期 state version、SSE cursor 缺口与终态刷新。
- 纯媒体 Run 完成、字幕失败重试复用音频、图片检查先于视频渲染。

Browser QA:

- 在真实前后端完成一次文章到图片质量控制链路，验证状态驱动按钮、刷新与 SSE 重连。
- 使用无费用 fixture 验证重试、取消、unknown Effect 和长 Tool 等待展示。
- 浏览器控制台不得有新增 error/warning；保存截图和关键 ID。

## Handoff

下一 Sprint 单独设计 Follow-up Run 与受控 Probe：终态引用、隔离 Attempt、只读预算、Artifact
采纳和主线计划修订。之后进入 Deferred Evaluation 合同，构建回归数据集并给出内部开放结论。
