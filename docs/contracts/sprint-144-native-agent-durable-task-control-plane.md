# Sprint 144–146：Agent Durable Runtime 全量替换计划

## Status

Ready for implementation。全量计划已定义，实施后按 Sprint 144–146 连续推进。

用户已明确：

- 当前没有需要兼容的真实 Agent 用户和生产 Agent 数据。
- 允许删除错误设计、旧表、旧 API、旧前端和本地测试数据。
- 必须一次定义并完成全部核心数据库结构，不能每个 Sprint 再补一部分核心表。
- 可以拆成多个连续 Sprint，每个 Sprint 验证并提交后直接继续，不需要用户逐段确认。
- 最终目标不是修复单一事故，而是完整实现 Task 管理、Chat/Run 恢复、Session Memory、
  多 Agent Task 切分、错误重试和任意局部节点重新执行。

当前编号已经进入 Sprint 144，因此本计划使用 Sprint 144、145、146；不复用历史
Sprint 114–116 编号。

## Program Goal

删除旧 Agent 控制链和当前 Native Agent 的错误控制层，建立一套由数据库驱动的 Durable
Runtime。系统必须把以下状态从聊天历史或进程内存中剥离出来，作为可查询、可校验、可恢复的
持久化事实：

```text
User
└─ Conversation（用户 Session）
   ├─ Message / Memory Snapshot
   └─ Run（一次用户目标）
      └─ Branch（主线或局部重跑候选分支）
         └─ Task State（该分支中的任务状态）
            └─ Attempt（一次真实执行）
               ├─ Model Session / Context Items
               ├─ Tool Call / Tool Effect
               └─ Artifact Version
      ├─ Checkpoint
      ├─ Approval
      └─ Event / Command
```

最终必须支持：

1. 浏览器刷新、SSE 断开、后端重启后恢复同一 Conversation、Run、Task 和等待状态。
2. 用户批准阶段性结果时继续同一 Run，而不是误结束或丢失上下文。
3. 已结束 Run 的后续目标创建新 Run，并有界继承已确认 Memory 和 Artifact。
4. 模型、子 Agent、只读 Tool 或幂等 Tool 失败后，从安全 Checkpoint 创建新 Attempt。
5. 用户可从一个已完成或失败的局部 Task 重新执行；新结果在候选 Branch 验证通过后再原子提升，
   不直接破坏当前主线。
6. 多 Agent 由持久化 Task DAG 调度；每个 Agent 调用都是可定位、可恢复的 Attempt。
7. 前端只展示后端权威 Projection；数据库 Run 已结束时不可能仍显示“等待执行”。

## Incident Baseline

必须把 2026-07-30 事故固化为自动化 fixture：

- Conversation：`b547d1eff60e47698ae0a0d40db1172a`
- 已批准 Run：`ed979081ea33489ab17d44eaa280aafb`
  - 阶段性选题 Approve 被错误实现为 `run=succeeded`。
- “继续”后 Run：`ddca2d7d76fd45968a0e8820a9514e42`
  - 新 Run 没有继承选题 Artifact、Memory 或恢复位置。
  - Writer 三次超时且无 Artifact，根模型的说明文本却让 Run 成功。
  - MLflow Tree 已结束，前端 Function Call 仍显示“等待执行”。

这些 ID 只用于本地取证。保存必要时间线后，可以删除原始 Agent 数据。

## Non-Negotiable Decisions

### 一套控制面

- 旧 `agent_runner`、`agent_tool_runtime`、`agent_hitl`、`agent_comic_creation`、
  `agent_panel_versions`、`agent_conversations` 整体删除。
- 当前 `/agent-loop` 的业务 Tool、Skill 和领域 adapter 保留；Run、Worker、Persistence、
  Checkpoint、API Projection 和前端状态控制层替换。
- 最终只有 `/agent` 一套 API、一套 ORM、一套 Worker、一套状态机和一个 Agent Workspace。
- 不保留旧 API 代理、双写、兼容 Model、compatibility alias、feature flag 或数据搬迁。

### 数据库一次换模

Sprint 144 必须一次创建最终核心 Schema，并在同一个破坏性迁移中：

1. 重接跨域外键。
2. 删除旧 `agent_*` 和 `native_agent_*` 控制表。
3. 创建本计划列出的全部新表、索引、唯一约束和外键。
4. 删除不再使用的旧 ORM、Enum 和关系。

Sprint 145、146 不再以“功能做到哪里”为理由追加核心状态表。实施中若发现目标 Schema
无法表达已在本计划范围内的状态，应先修正 Sprint 144 Schema 和测试，再继续，而不是留下
临时 JSON、第二套表或兼容层。

允许在后续 Sprint 修正字段、约束或索引缺陷，但不允许重新引入第二套身份模型。

### 数据库是状态事实来源

- 进程内 Queue 只运输 `attempt_id`，不保存任务事实。
- OpenAI Agents SDK 负责模型和 Tool Loop，不负责业务状态、恢复或完成判定。
- MLflow 只负责观测，不决定 Run 是否成功，也不作为恢复存储。
- 前端状态、浏览器 Local State 和模型说明文本都不能覆盖数据库状态。

### 没有默认兜底

- 不能在找不到 Checkpoint 时静默创建新 Run。
- 不能在 Tool 结果未知时自动重放。
- 不能在 Memory 构建失败时退回整段聊天历史继续执行。
- 不能因为模型输出“完成”就把未通过 Completion Contract 的 Task/Run 标成功。

## Independent Chain Boundary

静态引用和应用挂载审计结论：

- 生效的 `/agent-loop` 和 `NativeAgentView` 没有调用旧 Agent 控制链。
- 旧 Router 未挂载，旧 `AgentView` 不可达。
- 旧链路仍以 ORM、Migration、后端模块、前端 API/type 和测试残留，必须删除。
- Skill、账号、Style、频道、FileAsset、Provider Client、Observability 和传统媒体执行器属于
  共享产品能力，不属于旧控制链。

允许共享：

- `agent_skills/agent_skill_versions`。
- 用户、账号、Style、频道、文件资产、外部内容和 Provider Client。
- 图片、语音、字幕、视频、发布等领域执行器，通过明确 Tool Adapter 接入。
- 通用日志、Metric 和 Trace 基础设施。

禁止共享：

- 旧 Agent Run/Step/Artifact/Approval/Event Model 或 Service。
- 旧 `/agent/conversations` API 和旧前端 Agent 类型。
- 从新 Runtime 回调旧 Worker、旧恢复逻辑或旧 Tool Executor。
- 为保留旧测试而存在的桥接和双写。

发现间接依赖时，只允许把有价值的纯领域能力提取到中立模块，再删除旧入口。

## Authoritative Identity Model

### Conversation = 用户 Session

Conversation 是长期用户会话容器：

- 一个 Conversation 包含多条 Message、多个 Run 和多个 Memory Snapshot。
- Conversation 不直接表示一次执行，也不持有可变 SDK Session。
- 同一用户可以有多个 Conversation；不同 Conversation 默认不共享 Memory。
- Conversation 归档不删除 Run、Artifact 或 Memory。

### Run = 一次用户目标

Run 是完整 Workflow 实例：

- 创建时固定 Skill Version、模型、账号、Style、频道、资源引用和安全快照。
- `root_run_id` 表示工作族根；`parent_run_id` 表示 Follow-up 来源。
- `continued_from_checkpoint_id` 和 `memory_snapshot_id` 明确继承边界。
- `state_version` 每次权威状态变化递增，用于 CAS 和前端收敛。
- 终态 `succeeded/failed/cancelled` 不可重新打开；后续工作必须创建新 Run。
- Run 成功只能由所有 Required Task、Approval Gate 和 Tool Effect 共同计算。

### Branch = 主线与局部重跑隔离

每个 Run 创建一个初始主 Branch。局部重跑、Probe 或替代方案创建 Candidate Branch：

- Candidate 固定 `base_checkpoint_id`、`parent_branch_id` 和重跑起点 Task。
- Candidate 执行不会覆盖当前 Active Branch 的 Task State 或 Artifact Version。
- Candidate 验证通过后，通过单事务更新 `run.active_branch_id` 并发布新 Checkpoint。
- Candidate 失败或被用户放弃时标记 discarded，主线不变。
- 已产生未知外部副作用的 Candidate 不能自动提升或重放。

### Task = 不可变任务定义

Task 表示 Workflow DAG 中的逻辑节点：

- `task_key` 在 Run 内唯一。
- 保存 Task Type、负责人/Agent Role、输入输出契约、Completion Contract 和 Required 标志。
- 依赖使用关系表，不用 JSON 保存核心 DAG。
- Task 定义发布后不可原地改变；重编译 Workflow 必须创建新 Run。
- Runtime 校验 DAG 无环、依赖可达、Tool/Role 属于固定 Skill Version 的能力范围。

### Task State = Branch 内任务状态

同一 Task 在不同 Branch 有独立 Task State：

- 保存状态、当前 Attempt、输入 Artifact Version、输出 Artifact Version和失效原因。
- 上游 Artifact 被新 Branch 替换时，下游 Task State 标为 `stale`，并按依赖顺序重跑。
- Active Branch 的 Task State 才进入默认前端 Projection。

### Attempt = 一次真实执行

每次模型调用、子 Agent 调用、重试、恢复和局部重跑都创建新的 Attempt：

- 历史 Attempt 永不覆盖。
- 保存 Attempt Kind、Checkpoint、Model Session、租约、心跳、Trace、Usage、错误和终态。
- Worker 只能原子领取一个 Attempt。
- `unknown` 表示外部结果无法确认，必须停止自动推进。

## Complete Target Database Schema

以下是 Sprint 144 必须一次建完的最终核心表族。

### 会话和输入

#### `agent_conversations`

- `id`, `owner_user_id`, `title`, `status`
- `current_run_id`, `memory_head_snapshot_id`
- `last_message_at`, `created_at`, `updated_at`
- owner + last message 索引

#### `agent_messages`

- `id`, `conversation_id`, 可选 `run_id`, `role`, `content`
- `client_message_id`，用于用户重复提交幂等
- `command_id`, `sequence`, `created_at`
- 唯一 `(conversation_id, sequence)` 和 `(conversation_id, client_message_id)`

#### `agent_run_resources`

- `id`, `run_id`, `resource_type`, `resource_id`
- `snapshot_json`, `content_hash`, `ordinal`
- 固定 Skill、Style、账号、频道、用户引用和输入 Artifact 的创建时事实

### Run、Branch 和 Task

#### `agent_runs`

- `id`, `conversation_id`, `root_run_id`, `parent_run_id`
- `continued_from_checkpoint_id`, `memory_snapshot_id`, `active_branch_id`
- `skill_version_id`, `status`, `state_version`, `event_sequence`
- `expected_input_kind`, `allowed_actions_json`
- `completion_reason`, `error_code`, `error_message`
- `created_at`, `started_at`, `finished_at`, `updated_at`

#### `agent_run_branches`

- `id`, `run_id`, `parent_branch_id`, `base_checkpoint_id`
- `branch_kind`: `main/retry/rerun/probe`
- `status`: `active/candidate/promoted/discarded/failed/blocked`
- `rerun_from_task_id`, `created_by_user_id`, `reason`
- `created_at`, `resolved_at`
- 每个 Run 最多一个 active Branch

#### `agent_tasks`

- `id`, `run_id`, `task_key`, `task_type`, `agent_role`
- `required`, `input_contract_json`, `output_contract_json`
- `completion_contract_json`, `max_attempts`, `timeout_seconds`
- `created_at`
- 唯一 `(run_id, task_key)`

#### `agent_task_dependencies`

- `task_id`, `depends_on_task_id`, `dependency_kind`
- 复合主键；禁止自依赖

#### `agent_task_states`

- `id`, `task_id`, `branch_id`, `status`, `state_version`
- `current_attempt_id`, `input_manifest_hash`, `output_manifest_hash`
- `blocked_reason`, `stale_reason`, `started_at`, `finished_at`, `updated_at`
- 唯一 `(task_id, branch_id)`

#### `agent_attempts`

- `id`, `task_state_id`, `attempt_number`, `attempt_kind`
- `base_checkpoint_id`, `model_session_id`
- `status`, `lease_owner`, `lease_expires_at`, `heartbeat_at`
- `model`, `provider`, `trace_id`, `usage_json`
- `input_hash`, `output_hash`, `error_code`, `error_message`
- `created_at`, `started_at`, `finished_at`
- 唯一 `(task_state_id, attempt_number)`

### Model Session 和恢复上下文

#### `agent_model_sessions`

- `id`, `conversation_id`, `run_id`, `branch_id`, `attempt_id`
- `parent_session_id`, `base_checkpoint_id`
- `provider`, `model`, `status`, `context_version`
- `through_context_sequence`, `created_at`, `closed_at`
- 每个 Attempt 使用独立 Session；恢复 Attempt 从已提交 Context 派生，不共享可变 Session

#### `agent_context_items`

- `id`, `model_session_id`, `attempt_id`, `sequence`
- `item_type`, `role`, `content_json`, `content_hash`
- 可选 `provider_item_id`, `created_at`
- 唯一 `(model_session_id, sequence)`
- 只保存安全重放所需的 Responses Context，不使用 Provider remote conversation 作为事实来源

### Checkpoint、Memory 和分支提升

#### `agent_checkpoints`

- `id`, `run_id`, `branch_id`, 可选 `task_state_id`, `attempt_id`
- `revision`, `parent_checkpoint_id`, `checkpoint_kind`
- `through_event_sequence`, `through_context_sequence`
- `schema_version`, `skill_version_id`
- `state_json`, `state_hash`, `reason`, `created_at`
- 唯一 `(run_id, branch_id, revision)`
- append-only；Run/Branch 只保存当前指针

#### `agent_memory_snapshots`

- `id`, `conversation_id`, `source_run_id`, `source_checkpoint_id`
- `parent_snapshot_id`, `revision`, `summary`, `content_hash`
- `created_at`
- append-only；不能原地修改

#### `agent_memory_items`

- `id`, `snapshot_id`, `memory_type`
- `content_json`, `content_hash`
- `source_message_id`, `source_artifact_version_id`, `source_approval_id`
- `scope`, `confidence`, `ordinal`
- 事实、偏好、约束、用户决定和 Artifact 引用必须保留来源

### Artifact、审批和副作用

#### `agent_artifacts`

- `id`, `conversation_id`, `run_id`, `task_id`
- `artifact_key`, `artifact_type`, `current_version_id`
- `created_at`, `updated_at`
- 唯一 `(run_id, artifact_key)`

#### `agent_artifact_versions`

- `id`, `artifact_id`, `branch_id`, `attempt_id`, `version`
- `status`, `content_json`, 可选 `file_asset_id`
- `content_hash`, `schema_version`, `created_at`
- 唯一 `(artifact_id, version)`；版本不可覆盖

图片、语音、字幕、视频、文案和外部素材统一表示为 Artifact Version。类型专用信息进入版本化
`content_json`，二进制文件继续使用 `file_assets`。

#### `agent_approvals`

- `id`, `conversation_id`, `run_id`, `branch_id`, `task_state_id`
- `artifact_version_id`, `approval_purpose`, `on_approve_action`
- `status`, `requested_hash`, `feedback`
- `requested_at`, `resolved_at`, `resolved_by_user_id`
- 只能批准请求时固定的 Artifact hash

#### `agent_tool_calls`

- `id`, `attempt_id`, `task_state_id`, `tool_name`, `call_key`
- `status`, `arguments_json`, `arguments_hash`
- `result_json`, `result_hash`, `started_at`, `finished_at`
- 唯一 `call_key`；前端 Function Call 状态直接来自这里

#### `agent_tool_effects`

- `id`, `tool_call_id`, `effect_kind`, `idempotency_key`
- `status`: `prepared/submitted/succeeded/failed/unknown/reconciled`
- `provider_request_id`, `provider_receipt_json`, `result_artifact_version_id`
- `created_at`, `updated_at`
- 唯一 `idempotency_key`

### 命令、事件和同步

#### `agent_commands`

- `id`, `conversation_id`, `run_id`, 可选 `task_id`
- `command_type`, `idempotency_key`, `expected_state_version`
- `payload_json`, `status`, `result_projection_json`
- `created_by_user_id`, `created_at`, `completed_at`
- Approve、修改、Retry、Resume、Rerun、Cancel、Promote Branch 都通过命令执行

#### `agent_events`

- `id`, `conversation_id`, `run_id`, `branch_id`
- 可选 `task_state_id`, `attempt_id`, `tool_call_id`
- `sequence`, `event_type`, `state_version`, `payload_json`, `created_at`
- 唯一 `(run_id, sequence)`
- 作为 SSE 可重放日志；不存 chain-of-thought、密钥、内部路径或 Provider 原始敏感响应

### Database Invariants

- 所有核心 ID 使用现有固定长度字符串 ID 规范；时间统一保存 UTC。
- Conversation、Run、Branch、Task、Attempt、Artifact Version 和 Memory 的来源链必须有真实
  FK，不允许只保存无约束字符串。
- `current_*`、`active_branch_id`、`memory_head_snapshot_id` 等反向指针初始允许为空，在依赖表
  建好后补 FK；指针和被指向对象必须在同一事务更新。
- Event sequence 通过 Run 行原子递增分配，禁止 `MAX(sequence) + 1`。
- 所有 revision、version、sequence 和 attempt number 都有正数 Check Constraint。
- Run、Branch、Task State、Attempt、Approval、Tool Call/Effect 的状态值有数据库 Check；
  状态转换只允许通过唯一 Transition/Command Service。
- Durable Runtime 对象不提供普通硬删除 API；用户删除 Conversation 使用归档。测试清理和本次
  破坏性 Migration 按明确 FK 顺序执行。
- Artifact/Memory/Checkpoint/Context/Event 使用 append-only Repository；更新当前指针不修改
  已提交历史行。
- JSON 只保存版本化 Payload、Contract、Snapshot 或 Projection，不保存可被覆盖的唯一任务状态；
  JSON 写入前必须通过对应 Pydantic Schema 校验并保存 schema version/hash。

## Cross-Domain Foreign-Key Rewrite

不能只删除 `native_agent_runs`，必须同时处理当前跨域引用：

- 删除 `native_agent_images/audios/subtitles/videos/external_contents`，对应数据统一进入
  `agent_artifacts/agent_artifact_versions`。
- `youtube_publish_tasks.source_native_agent_video_id` 改为
  `source_agent_artifact_version_id`。
- `youtube_uploaded_videos.source_native_agent_video_id` 同样改为
  `source_agent_artifact_version_id`。
- 发布服务必须验证引用的 Artifact Version 类型为视频且属于当前用户允许的 Conversation。
- Run 上的媒体调用计数字段删除，改从 Tool Call/Attempt 聚合。
- Skill、Style、频道等外键和创建时快照写入 `agent_run_resources`；需要高频过滤的
  `skill_version_id` 保留为 Run 直接外键。
- 传统 `generation_tasks/video_tasks/generated_images/file_assets` 继续保留，不并入 Agent
  控制表。

由于用户授权清理本地 Agent 数据，迁移不搬运旧 Run/Context/Artifact/Approval；YouTube
发布测试数据若引用旧 Native Video，一并清理并重建 fixture，不制造虚假映射。

## State Machines

### Run

```text
queued
→ running
→ waiting_for_input | waiting_for_tasks | retrying
→ running
→ succeeded | failed | cancel_requested → cancelled
```

- `waiting_for_input` 必须有 `expected_input_kind` 和 `allowed_actions`。
- Required Task 未完成、Approval 未解决或 Tool Effect 为 unknown 时不能成功。
- 终态不可逆。

### Task State

```text
pending → ready → running
→ waiting_for_input | retrying
→ succeeded | failed | blocked | stale | cancelled
```

### Attempt

```text
prepared → running
→ succeeded | failed | interrupted | unknown | cancelled
```

### Branch

```text
main: active
candidate: candidate → promoted | discarded | failed | blocked
```

## Run ID Decision Rules

| 用户动作/系统状态 | 行为 | Run ID |
| --- | --- | --- |
| 新 Conversation 第一个目标 | 创建根 Run | 新 |
| Run 等待阶段审批，用户批准 | 解决 Gate，推进 Task | 原 Run |
| Run 等待修改意见 | 保存 Message，创建新 Attempt | 原 Run |
| 失败 Task 可安全重试 | 创建 Retry Attempt | 原 Run |
| 服务中断且 Checkpoint 安全 | 创建 Resume Attempt | 原 Run |
| 用户重跑局部 Task | 创建 Candidate Branch 和 Rerun Attempt | 原 Run |
| 已成功 Run 的后续制作 | 创建 Follow-up Run | 新 |
| 用户更换目标、Skill 或固定资源 | 创建根 Run | 新 |
| Tool Effect unknown | 阻止自动执行，等待人工命令 | 不创建 |

“继续”“重试”等自然语言只能被解析成建议命令；后端必须根据当前 `allowed_actions` 验证，不能
再通过字符串特判决定恢复。

## Chat、Model Session 和 Memory

### 三层上下文

1. Conversation History：用户可见 Message，长期保存。
2. Memory Snapshot：经过验证且可继承的事实、偏好、决定和 Artifact 引用。
3. Model Session：单个 Attempt 的完整 SDK 重放上下文。

规则：

- 新 Run 不能直接复用上一 Run 的可变 SDK Session。
- Resume Attempt 从 Checkpoint 固定的 Context Sequence 创建新 Model Session。
- Follow-up Run 只继承显式 Memory Snapshot 和 Artifact Version。
- 用户原文、批准决定和 Artifact hash 是事实；模型摘要不能覆盖。
- Memory Item 必须有来源和 Scope；跨 Conversation Memory 不在本计划中自动发生。
- Compact 只减少模型输入大小，不代表任务完成，也不能删除恢复所需的 Context Item。
- Memory 构建失败必须明确阻止需要该 Memory 的 Follow-up，不得退回整段历史静默执行。

## Checkpoint and Recovery

自动保存边界：

- Workflow 编译并验证后。
- 每个 Required Task 成功、失败或进入等待前。
- Tool Effect 提交前和结果确认后。
- Approval 创建前和解决后。
- Branch 创建、提升或废弃时。
- Run 进入终态前。
- 服务优雅关闭且 Attempt 可安全中断时。

恢复矩阵：

| 中断位置 | 恢复行为 |
| --- | --- |
| Attempt prepared，未调用 Provider | 原 Attempt 可领取 |
| 纯模型调用中断 | 旧 Attempt=interrupted；从 Checkpoint 创建 Resume Attempt |
| 只读 Tool 中断 | 用相同 call key 对账后安全重试 |
| 幂等副作用 Tool 已提交 | 先按 Provider receipt 查询，不重复提交 |
| 非幂等 Tool 结果不明 | Tool Effect=unknown，Run blocked，等待人工 |
| Artifact 已提交、下游未开始 | 复用 Artifact，只调度下游 |
| Approval 等待期间重启 | 保持 waiting，不占 Worker |
| SSE 断线 | 按最后 sequence 补发；缺口时读取 Projection |

Worker 使用 Attempt Lease：

- Queue 只传 `attempt_id`。
- 原子写 `lease_owner/lease_expires_at/heartbeat_at` 后才能执行。
- 启动只扫描 `prepared/interrupted/retrying` 且副作用安全的 Attempt。
- waiting、terminal、unknown 不入队。
- Cancel 每个模型/Tool 边界检查，不能把取消后的 Provider 结果提交为成功。

## Local Rerun and Probe

用户可选择一个 Task 执行 `rerun_task`：

1. Runtime 找到该 Task 之前最近的安全 Checkpoint。
2. 创建 Candidate Branch，复制必要的 Task State 引用，不复制可变 Attempt。
3. 目标 Task 创建 `rerun` Attempt。
4. 依赖目标输出的下游 Task 在 Candidate Branch 标记 stale，并按拓扑顺序重跑。
5. 无关上游和旁支直接复用已验证 Artifact Version。
6. Candidate 全部 Completion Contract 和 Gate 通过后，用户或自动策略执行
   `promote_branch`。
7. 提升事务同时更新 Active Branch、Artifact current version、Memory 和 Checkpoint。
8. Candidate 失败时主线保持不变。

Probe 使用相同 Branch 机制，但 `branch_kind=probe`：

- 纯验证 Probe 通过后生成新的 Gate-passed Checkpoint。
- 有状态 Probe 的结果只有提升后才能成为主线事实。
- Probe 失败或 unknown 时不得污染 Active Branch。

## Multi-Agent Task Management

- Workflow Compiler 产生结构化 Task DAG，而不是只输出自然语言步骤。
- Runtime 校验 Task Type、Role、Tool、依赖、最大节点数、最大并行度和无环性。
- Director、Writer、Reviewer 等每个角色对应 Task；每次 `agent.as_tool()` 调用对应 Attempt。
- 子 Agent 使用独立 Model Session，只接收任务所需 Memory 和 Artifact，不继承 Director 的
  全量可变 Context。
- 子 Agent 输出必须先提交 Artifact、Attempt 终态、Checkpoint 和 Event，再返回给上游。
- 并行 Task 只允许写各自 Artifact；共享状态通过依赖节点合并，不能并发覆盖 Run JSON。
- 任一 Required 子 Task 失败，根 Run 只能 retry/wait/fail，不能被 Director 文本改成成功。
- 第一条验收链为 Compiler → Writer → Reviewer → Approval；同时增加两个独立 Writer
  并行后由 Reviewer 合并的 DAG 测试，证明 Task 模型不是硬编码单链。
- 子 Agent 递归创建无界孙 Agent 不在范围内；需要新节点时由受控 Compiler/Director 请求并由
  Runtime 校验后持久化。

## Backend API and Projection

统一 API：

```text
POST /api/v1/agent/conversations
GET  /api/v1/agent/conversations
GET  /api/v1/agent/conversations/{conversation_id}
POST /api/v1/agent/conversations/{conversation_id}/messages
POST /api/v1/agent/runs/{run_id}/commands
GET  /api/v1/agent/runs/{run_id}
GET  /api/v1/agent/runs/{run_id}/events
GET  /api/v1/agent/runs/{run_id}/checkpoints
GET  /api/v1/agent/runs/{run_id}/branches
```

Command 至少包括：

- `approve_and_advance`
- `request_changes`
- `retry_task`
- `resume_run`
- `rerun_task`
- `promote_branch`
- `discard_branch`
- `cancel_run`
- `create_follow_up`

每个 Command 必须携带 idempotency key 和 expected state version，并返回提交后的完整
Projection。

Projection 同时用于详情 API 和 SSE `run.updated`：

- Run、Branch、Task State、Attempt、Tool Call 的权威状态。
- Checkpoint、Memory、Artifact 和 Approval 引用。
- `expected_input_kind`、`allowed_actions`、完成/阻塞原因。
- `state_version` 和 Event sequence。

SSE 最终规则：

- 每次状态事务提交后发布递增 Event。
- 终态前必须发送最终 `run.updated`。
- 前端忽略旧 state version。
- 发现 sequence 缺口、断线或终态时重新读取一次详情 Projection。

## Frontend Agent Workspace

- 删除旧 `AgentView`、旧 API client/type 和 `/agent-loop` 调用。
- 只保留一个 `/agent` Workspace。
- Conversation 列表、Message、Run、Task DAG、Attempt、Artifact、Approval、Branch 和
  Checkpoint 全部使用统一 Projection。
- Function Call 状态直接来自 `agent_tool_calls`，不通过 Artifact 猜测。
- Run 终态时所有 Task/Attempt/Tool Call 必须显示明确终态，不得继续旋转。
- 用户可以查看失败节点、错误、已复用的上游结果和将被重跑的下游范围。
- Retry 当前失败节点、从任意节点重跑、提升/放弃 Candidate Branch 都使用明确按钮和后果说明。
- 阶段审批按钮显示“批准并继续下一步”；最终审批显示“批准并结束任务”。
- 刷新页面、关闭浏览器再打开或 SSE 重连后，界面从数据库恢复相同状态。
- MLflow 链接只用于排查，不参与页面业务状态计算。

## Destructive Migration Strategy

Sprint 144 执行顺序：

1. 保存事故 fixture，并复制当前本地 SQLite 文件作为只读取证备份。
2. 写一条最终替换 Migration；Migration 中按外键逆序删除旧关联和旧表。
3. 一次创建全部目标表、约束、索引和 FK。
4. 重接 YouTube Publish/Uploaded Video 的来源外键。
5. 删除旧 Model/Enum/Schema 引用并更新 ORM metadata。
6. 新建空库跑全量 Alembic upgrade。
7. 现有结构库跑 replacement upgrade。
8. downgrade 只保证恢复旧空 Schema，不承诺恢复已删除的本地 Agent 数据。
9. 再次 upgrade，并比较最终 Schema inventory。

不允许：

- 先保留旧表，后续 Sprint 再“慢慢迁”。
- 新旧表双写。
- 用 View 或 Alias 伪装兼容。
- 把核心状态塞进一个可覆盖的 `checkpoint_json`。

## Continuous Delivery Plan

用户授权的是完整目标。开始实施后，以下三个 Sprint 连续执行：每段完成后验证、记录
`docs/progress.md`、创建中文 Commit，然后自动进入下一段。除非触发安全、生产数据或不可逆外部
副作用阻塞，不因“一个 Sprint 完成”暂停等待确认。

### Sprint 144：一次性 Schema 与旧链路清除

交付：

- 最终 Migration、全部新 ORM/Enum/Repository。
- 旧 Agent 和 Native Agent 控制表、代码、API、前端旧组件和测试删除。
- 跨域媒体/发布外键重接。
- Run/Task/Attempt/Branch/Checkpoint 状态机和数据库约束。
- 用新 Repository、Command、Projection 和 `/agent` API 跑通当前单纵向文案链的最小完整
  Cutover；当前业务 Tool Adapter 一次接到新身份，不留下无法启动的中间提交。
- 前端在同一 Sprint 切换到 `/agent` 基础 Projection，保证 Conversation、Run、Task、
  Approval 和终态可用；Branch/Checkpoint 的高级操作界面在 Sprint 146 补齐。
- Schema inventory、迁移往返和零旧引用测试。

验收后自动进入 Sprint 145。

### Sprint 145：Durable Runtime、Memory 与局部恢复

交付：

- Command Service、Projection Service、Event Writer。
- Task DAG 调度、Attempt Lease、启动恢复和取消。
- Model Session/Context Replay、Checkpoint CAS、Memory Snapshot。
- Tool Call/Tool Effect Ledger。
- Retry、Resume、Follow-up Run、Candidate Branch、局部 Rerun、Probe 和 Branch Promotion。
- 多 Agent Writer/Reviewer 及并行 DAG 适配。
- 扩充统一 `/agent` API 的 Retry、Resume、Rerun、Probe、Promote/Discard 和 Follow-up
  Command；基础 API 不等到 Sprint 146 才出现。

验收后自动进入 Sprint 146。

### Sprint 146：统一 API、前端状态收敛与故障演练

交付：

- 完整统一 `/agent` API 和 SSE 契约，删除 Sprint 144 基础 Projection 中不再需要的字段。
- 完整单一 Agent Workspace、Task/Attempt/Branch/Checkpoint UI。
- Approve、Retry、Rerun、Promote、Discard、Cancel、Follow-up 交互。
- 浏览器刷新、断线重连、后端重启和真实模型故障注入回归。
- 再次静态确认所有 `/agent-loop` 和旧 Agent 前端引用为零。
- 更新 Spec、设计文档、运维说明和最终 QA 记录。

## In Scope

- 本文全部目标 Schema 和破坏性迁移。
- Task DAG、Attempt、Lease、Checkpoint、Branch、Probe 和局部重跑。
- Conversation Session、Model Session 和 Session Memory。
- 新 Run/旧 Run 判定及 Follow-up Memory 继承。
- 多 Agent Task 切分、并行、恢复和完成判定。
- Tool 幂等与 unknown 副作用边界。
- 统一 API/SSE/Frontend Projection。
- 旧链路、旧数据和兼容代码清理。
- 文章团队端到端真实验收。

## Out of Scope

- Redis、Celery、Temporal、LangGraph 或其它外部 Workflow 引擎。
- 多实例生产 Worker、分布式一致性和跨服务事务。
- 自动重放结果未知的非幂等外部副作用。
- 跨 Conversation、跨用户自动 Memory 共享。
- 无界递归 Agent、自修改 Workflow 和无限动态 fan-out。
- 将传统 `generation_tasks/video_tasks` 内部状态机整体迁入 Agent Runtime。
- 旧 Agent/Native Agent 数据兼容或生产数据迁移。

这些项目不影响本计划在单进程 SQLite 环境中完成完整的用户级持久化和恢复能力。

## Done Means

### 数据和代码

- 目标核心表一次建全；仓库只剩一套 Agent ORM、状态机和 API。
- `agent_*` 新 Runtime 对旧控制模块、旧 Model、旧表和旧前端类型零引用。
- `native_agent_*` 控制表和运行模块全部删除。
- YouTube 发布和媒体来源不再依赖 `native_agent_video_id`。

### Task 与恢复

- Writer 成功、Reviewer 未开始时杀进程，重启后只执行 Reviewer。
- 模型调用中断产生 interrupted Attempt 和新的 Resume Attempt，不覆盖历史。
- Tool unknown 时停止自动推进。
- Approval 等待期间重启不占 Worker，批准后继续同一 Run。
- Required 子 Task 失败时根 Run 不会成功。

### Session 与 Memory

- 刷新或重新打开 Conversation 能恢复 Message、Run、Task、Approval 和允许操作。
- Follow-up Run 继承固定 Memory Snapshot 和 Artifact Version，不复用旧可变 SDK Session。
- Memory Item 可追溯到 Message、Artifact 或 Approval。

### 局部重跑

- 用户可从任一允许的 Task 创建 Candidate Branch。
- 上游安全结果被复用，目标及受影响下游重跑。
- Candidate 失败不污染主线；成功提升后主线、Artifact、Memory 和 Checkpoint 原子切换。

### 前后端一致性

- API、SSE、数据库和页面对同一 Run 的状态一致。
- Run 终态时没有仍显示“等待执行”的 Function Call。
- MLflow Trace 结束不会改变数据库 Run 状态。

## Verification

每个 Sprint：

```bash
./scripts/check.sh
git diff --check
```

Sprint 144 必测：

1. 空库 Alembic 全量 upgrade。
2. 旧结构库 replacement upgrade。
3. replacement downgrade → upgrade。
4. Schema inventory 与本文目标表一致。
5. 所有 FK、唯一约束、状态 Check 和级联行为。
6. `rg` 检查旧模块、旧 Router、旧前端类型和旧表名零引用。
7. YouTube 发布来源 FK 指向 Artifact Version。

Sprint 145 必测：

1. Run、Task State、Attempt 和 Branch 状态机非法跳转被拒绝。
2. Command idempotency 和 state version 冲突。
3. DAG 无环校验、依赖调度和 bounded parallel。
4. Lease 领取、过期、Heartbeat、取消和启动恢复。
5. Checkpoint append-only、hash、revision CAS。
6. Model Context 顺序和 Resume Session 派生。
7. Memory 来源、Scope、Follow-up 继承。
8. Retry/Resume/Rerun/Probe/Promote/Discard。
9. Tool Call 幂等、Provider receipt 对账和 unknown 阻塞。
10. 多 Agent 任一 Required Task 失败时 Run 不成功。

Sprint 146 必测：

1. 事故 fixture：“批准选题 → 继续写作”保持同一 Run。
2. SSE sequence 缺口和断线后的 Projection 收敛。
3. 前端刷新、重新登录和后端重启恢复。
4. Writer/Reviewer 之间强制杀进程。
5. Approval 等待期间关闭浏览器和后端。
6. 局部重跑 Candidate 成功提升和失败回滚。
7. 并行 Writer → Reviewer 合并。
8. Run 终态下 Task、Attempt、Tool Call 全部终态。
9. Owner 隔离、跨 Run Memory/Artifact 权限。
10. 真实模型 Smoke，并保存 Run/Task/Attempt/Checkpoint/Trace ID 与截图。

## Risks and Guardrails

- 这是一次破坏性控制面替换；实施期间不能并行合并其它 Agent Runtime 改造。
- 用户授权删除的是本地 Agent 测试数据和错误控制设计，不包括用户、Skill、Style、频道、
  FileAsset 和传统生成任务数据。
- 迁移前必须创建明确路径的数据库备份；不能对宽泛目录执行删除。
- SQLite 足以完成当前单进程 Durable Runtime；不能据此宣称已支持生产多实例。
- 任何需要自动处理 unknown 外部副作用的需求都必须单独评审，不能静默兜底。

## Handoff

Sprint 146 完成后交付：

- 最终 Schema 图和 Migration 记录。
- Agent Runtime 状态机与恢复矩阵。
- API/Projection/SSE 契约。
- 故障注入、真实浏览器和真实模型 QA 报告。
- 已知限制只允许保留在 Out of Scope 中，本文 In Scope 不得以“后续 Sprint”名义顺延。
