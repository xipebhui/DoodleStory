# Sprint 144：Native Agent 稳定任务控制面与可恢复单纵向链路

## Status

Draft。用户已明确确认当前没有真实用户和需要保留的生产 Agent 数据，允许删除错误设计并进行
替换式重构；正式实施仍需按本合同逐步验证。

本文是稳定任务改造的第一阶段合同。它不在现有两套 Agent Run/恢复实现上继续叠加，而是先删除
不可达旧控制面和错误 Native Agent 编排层，再建立唯一的 Durable Task Runtime，并把多 Agent
文案链路重建为第一条真实纵向样本。通用并行 DAG、任意 Probe 分支和外部工作流引擎留给后续
Sprint。

## Goal

用替换式重构把当前“两个并存且语义冲突的 Agent 控制面”收敛为“一个具有权威任务状态、明确
续用语义和可恢复执行边界的 Agent 工作流基础”：

1. 删除未挂载的旧 Agent Runtime、不可达前端和错误恢复入口，不保留兼容 API 或双写。
2. 后端数据库成为 Conversation、Workflow Run、Task、Attempt、Checkpoint、Approval 和 Tool
   副作用的唯一状态事实来源。
3. Approve、继续、修改、重试和新目标不再依赖前端猜测或自然语言特判，而是执行明确的控制命令。
4. 前端只展示后端权威投影；Run 已结束时不能继续显示 Function Call“等待执行”。
5. 同一 Conversation 内的新 Run 可以有界继承经过验证的 Memory、Artifact 和父 Run 关系，
   但不能直接复用或污染已结束 Run 的 SDK Session。
6. Writer、Reviewer 和最终审批形成可中断恢复的持久化 Task/Attempt 链；单个子 Agent 失败不能
   被根模型的一段说明文字掩盖成 Workflow 成功。

## Incident Baseline

本 Sprint 必须以 2026-07-30 的真实故障作为回归基线：

- Conversation：`b547d1eff60e47698ae0a0d40db1172a`
- 已批准 Run：`ed979081ea33489ab17d44eaa280aafb`
  - 用户批准选题后，后端把 Run 直接置为 `succeeded/article_approved`。
  - Approval 反馈为“使用第一个选题就可以”，但该决定没有推进后续文案 Task。
- “继续”创建的新 Run：`ddca2d7d76fd45968a0e8820a9514e42`
  - 新 Run 只保存“继续”作为用户输入，没有继承已批准选题 Artifact 或上一 Run 的任务恢复位置。
  - 三次 `write_article` 子 Agent 调用均超时，未生成任何 Artifact。
  - 根模型输出“请重试”后，Runtime 仍把 Run 标记为 `succeeded`。
  - MLflow Trace 正常结束，但前端 Function Call 因没有 Tool 终态事件而持续显示“等待执行”。

本 Sprint 完成后，上述状态组合必须无法再次出现。

这些 ID 只作为本地事故证据。实施前把必要状态时间线保存进测试 fixture 或 QA 记录后，允许在
开发数据库重建时删除原始 Agent Run、Context、Artifact 和 Approval 数据，不为本地测试数据
增加兼容迁移。

## Replacement Decision

仓库当前并存两套 Agent 控制面：

1. 旧 Agent 控制面：
   - `AgentConversation/AgentRun/AgentStep/AgentArtifact/AgentApprovalRequest/AgentEvent`
   - `agent_runner`、`agent_tool_runtime`、`agent_hitl`、`agent_comic_creation`、
     `agent_panel_versions`
   - 未挂载的 `agent_conversations` API
   - 前端不可达的 `AgentView` 和对应 API client/type
2. 当前 Native Agent 控制面：
   - `NativeAgentConversation/NativeAgentRun/NativeAgentStep/NativeAgentEvent`
   - `native_agent_worker`、`native_agent_persistence`、覆盖式
     `workflow_checkpoint_json`
   - `/agent-loop` API 和前端基于 Artifact 猜 Tool 终态的投影

两套实现使用同一组状态枚举却有不同的 Session、Checkpoint、恢复和 UI 语义。Sprint 144 不选择
其中一套继续打补丁，目标是删除两套控制面代码后重建唯一实现。

保留边界：

- `agent_skills/agent_skill_versions` 是产品级 Skill 数据，不属于待删除旧控制面。
- `generation_tasks`、图片 Task Worker 和 Video Task Worker 是传统产品域执行器，继续保留。
- 图片、音频、字幕、视频、外部内容和发布结果仍是领域资产；第一阶段只改变 Agent 如何引用和
  调度它们，不删除传统任务产品能力。
- MLflow 继续是可观测性系统，不成为恢复数据库。

不保留边界：

- 不保留旧 `/agent/conversations` 或当前 `/agent-loop` 的兼容代理。
- 不对旧 Run、Context、Checkpoint 或测试 Artifact 做数据搬迁。
- 不让旧 Worker 与新 Durable Worker 双跑。
- 不通过 feature flag 长期维持两套控制面。

## Authoritative Identity Model

### Conversation

新统一 `AgentConversation` 是长期用户会话和 Memory 所属容器，不直接表示一次执行。

- 一个 Conversation 可以包含多个 Workflow Run。
- Conversation 保存用户可见消息、结构化资源引用和有界 Memory Snapshot。
- Conversation Memory 不能直接等同于任意一个 Run 的 SDK Session。

### Workflow Run

新统一 `AgentRun` 表示一次完整用户目标的根工作流，不继承旧 `AgentRun` 或
`NativeAgentRun` 的可变恢复语义。

- 一个 Run 固定 Skill Version、模型、Style、账号和发布上下文快照。
- Run 可以包含多个 Task 和多次执行 Attempt。
- Run 只有在所有必需 Task 达到成功终态、所有 Completion Gate 通过且没有未解决副作用时，
  才能进入 `succeeded`。
- Run 进入 `succeeded/failed/cancelled` 后保持不可变；后续工作创建带来源关系的新 Run，不能
  把已结束 Run 改回 `queued/running`。

新增关系：

- `root_run_id`：根工作流 ID；第一层 Run 等于自身 ID。
- `parent_run_id`：从哪个已结束或父级 Run 派生。
- `continued_from_checkpoint_id`：新 Run 从哪个已确认 Checkpoint 读取上下文。
- `state_version`：每次权威状态变更递增，用于前端投影和乐观并发。

### Task

Task 是 Runtime 可以独立调度、等待、重试、取消和验证的最小工作单元。

第一条纵向链路至少产生：

```text
compile_workflow
→ write_article
→ review_article
→ approve_topic_or_final
→ complete_workflow
```

每个 Task 必须保存：

- 稳定 Task ID、Run ID 和可选父 Task ID。
- `task_key`，在同一 Run 内稳定且唯一。
- `task_type`、负责角色和 Skill 自定义业务标签。
- 状态、依赖、输入 Artifact 引用、输出 Artifact 引用。
- `completion_contract_json`：机器可检查的完成条件。
- 当前 Attempt、最大 Attempt、错误和时间。
- `required`：是否阻塞根 Run 成功。

模型可以建议 Task 拆分和业务顺序，但 Runtime 必须验证：

- Task 类型和角色在固定 Skill Version 允许范围内。
- 依赖形成无环且可执行的图。
- 必需输入 Artifact 已存在且 hash 有效。
- Completion Contract 已满足后才能将 Task 标成成功。
- 必需 Task 未完成时不能提交根 Run 成功。

### Attempt

Attempt 是 Task 的一次真实执行，不覆盖历史执行。

每次模型调用、子 Agent 调用、人工修改后的重做和安全重试都创建新 Attempt，并保存：

- `task_id`
- `attempt_number`
- `attempt_kind`：`normal`、`retry`、`resume` 或后续使用的 `probe`
- `base_checkpoint_id`
- 独立 SDK Session namespace
- 状态、开始/结束时间、模型、usage、Trace ID
- 输入摘要、输出 Artifact、错误
- Worker claim、lease 和 heartbeat

子 Agent 必须先创建 Attempt，再发出模型请求。超时或服务重启后，Attempt 有明确的
`failed/interrupted/unknown` 事实，不能只把错误文本交给 Director 后消失。

## State Machines

### Workflow Run

```text
queued
→ running
→ waiting_for_input | waiting_for_task | retrying
→ running
→ succeeded | failed | cancelled
```

规则：

- `waiting_for_input` 不是终态，必须同时保存 `expected_input_kind` 和 `allowed_actions`。
- `succeeded` 必须由 Runtime 根据 Task/Gate 计算，不能由模型 final output 直接决定。
- 子 Agent Tool 返回失败时，关联 Task 必须失败或重试；根模型的解释性输出不能覆盖这个事实。
- `workflow_phase` 只是展示字段，不能替代 Task 状态。

### Task

```text
pending
→ ready
→ running
→ waiting_for_input | retrying
→ succeeded | failed | cancelled | blocked
```

### Attempt

```text
prepared
→ running
→ succeeded | failed | interrupted | unknown | cancelled
```

`unknown` 表示无法确认外部副作用，只能人工解决或通过 Provider receipt 对账，不允许自动重放。

## Continue、Approve、Retry 与新 Run 判定

后端返回每个 Run 当前允许的结构化操作，前端只能提交其中之一：

```json
{
  "expected_input_kind": "approval_decision",
  "allowed_actions": [
    "approve_and_advance",
    "request_changes",
    "cancel"
  ]
}
```

判定矩阵：

| 场景 | 行为 | Run ID |
| --- | --- | --- |
| 新 Conversation 的第一个目标 | 创建根 Workflow Run | 新 Run |
| Run 正在等待某个 Gate，用户批准 | 解决 Gate，推进下一 Task | 同一 Run |
| Run 等待修改意见，用户提交意见 | 保存输入，创建新 Task Attempt | 同一 Run |
| Task 明确失败且可安全重试 | 创建 retry Attempt | 同一 Run |
| Run 因进程中断但 Checkpoint 可恢复 | 创建 resume Attempt | 同一 Run |
| Run 已成功，用户提出同一成果的后续制作 | 创建带 `parent_run_id` 的 Follow-up Run | 新 Run |
| 用户提出不同目标或更换固定 Skill/Style | 创建新根 Run | 新 Run |
| Run 存在 `unknown` Tool Effect | 阻止自动继续，要求人工处理 | 不创建 Run |

本 Sprint 禁止继续以输入内容是否精确等于“重试”决定核心恢复语义。自然语言输入可以由模型或
命令解析器提出建议，但最终必须映射为后端当前 `allowed_actions` 中的结构化命令。

审批必须增加明确的 `approval_purpose` 和 `on_approve_action`：

- `stage_gate` + `advance_task`
- `artifact_revision` + `resume_task`
- `final_result` + `complete_run`

不能再把所有 Approve 都实现为 `run.status=succeeded`。

## Conversation Memory 与 SDK Session

### 三层上下文

1. Conversation History：用户可见的长期消息事实。
2. Workflow Memory：经过验证、可继承的摘要、决定和 Artifact 引用。
3. Attempt SDK Session：某次模型/子 Agent 执行的原生 Responses Context。

约束：

- SDK Session 继续隔离在 Run/Attempt 范围，不能简单改成全 Conversation 共用，否则并行
  Task、失败重试和不同 Skill 会相互污染。
- 新 Run 不直接复制上一 Run 的全部 SDK Context。
- Run 在稳定 Checkpoint 或终态生成不可变 Memory Snapshot，保存来源 Run、事件范围、
  Artifact ID/hash、用户决定和有界摘要。
- 创建 Follow-up Run 时显式选择 Memory Snapshot，并在 Run 创建事务中固化引用。
- 用户原文、批准决定和 Artifact 是事实；模型摘要不能覆盖它们。
- Compact 只用于控制模型 Context 大小，不作为任务完成或恢复事实。

## Checkpoint

新增 append-only `agent_checkpoints`，删除覆盖式 `workflow_checkpoint_json`。

最小字段：

- `id`
- `run_id`
- 可选 `task_id`、`attempt_id`
- `revision`
- `parent_checkpoint_id`
- `through_event_sequence`
- `schema_version`
- `skill_version_id`
- `phase`
- `state_json` 或 `state_artifact_id`
- `state_hash`
- `reason`
- `created_at`

Run 保存 `current_checkpoint_id/current_checkpoint_revision`。发布新 Checkpoint 时使用
`expected_revision` 乐观锁；revision 冲突必须重新读取合并，不能静默覆盖。

第一阶段自动保存边界：

- Workflow Plan 编译并校验后。
- 每个必需 Task 成功或明确失败后。
- 创建人工 Gate 前。
- 人工 Gate 解决后。
- Run 进入终态前。
- 服务优雅关闭且当前 Attempt 可以安全中断时。

`checkpoint.saved` Event 必须包含 Checkpoint ID、revision、parent ID、state hash 和
`through_event_sequence`，使事件、快照和恢复游标可以互相校验。

## Probe Target Semantics

本 Sprint 只固化数据语义和接口边界，不实现通用 Probe 调度器。

后续 Probe 必须是从不可变 Checkpoint 分叉的特殊 Attempt：

```text
base checkpoint C12
→ create probe attempt(base_checkpoint_id=C12)
→ persist evidence artifact

pass:
  创建或提升 C13，记录 gate passed 和 evidence hash

fail:
  废弃 Probe 分支，主线仍指向 C12

unknown side effect:
  停止自动推进，等待人工处理
```

Probe 通过后不能简单恢复到 C12；纯验证 Probe 应创建新的 Gate-passed Snapshot，有状态 Probe
应把经过验证的结果提升为新 Snapshot。只有 Probe 失败或被废弃时才回到 base checkpoint。

## Database Replacement

删除旧 Agent 控制面表：

- `agent_conversations`
- `agent_messages`
- `agent_runs`
- `agent_steps`
- `agent_artifacts`
- `agent_approval_requests`
- `agent_events`
- `native_agent_conversations`
- `native_agent_runs`
- `native_agent_items`
- `native_agent_steps`
- `native_agent_events`
- `native_agent_context_items`
- `native_agent_artifacts`
- `native_agent_article_approvals`

与 Native Run 强绑定的本地测试媒体关联表允许清空并按新外键重建；传统
`generation_tasks/video_tasks/file_assets` 不在删除范围。

重建唯一表族：

- `agent_conversations`
- `agent_messages`
- `agent_runs`
- `agent_tasks`
- `agent_task_attempts`
- `agent_checkpoints`
- `agent_memory_snapshots`
- `agent_context_items`
- `agent_events`
- `agent_artifacts`
- `agent_approvals`
- `agent_tool_effects`

`agent_tool_effects` 第一阶段即进入统一模型，保存稳定幂等键、Task/Attempt、Provider request
ID、prepared/submitted/succeeded/failed/unknown 状态和结果引用。Checkpoint 不能替代副作用
账本。

数据库变更采用显式破坏性 forward migration，并在应用前备份当前本地数据库文件供事故取证。
迁移后允许重建开发数据库和 Agent 测试 fixture；不编写旧 Agent 数据搬迁、兼容 view 或双读。

## Legacy Code Removal

实施时先基于静态引用和测试清单确认边界，然后删除：

- 后端旧 Agent API、Runner、HITL、Tool Runtime、Comic Creation 和 Panel Version 编排代码。
- 当前 Native Agent Worker、Persistence、覆盖式文章 Workflow Checkpoint 和 `/agent-loop`
  控制 API。
- 前端不可达 `AgentView`、旧 Agent API client/type、旧事件文案和旧 Task Inspector。
- 当前 `NativeAgentView` 中依赖 Artifact 猜 Function Call 完成状态、精确“重试”字符串路由和
  本地 active Run 推断的逻辑。
- 只覆盖被删除 Runtime 的测试。

随后用新的统一 `/agent` API、Durable Worker、权威 Projection 和一个 Agent Workspace 重建。
共享 Skill 管理、账号、Style、频道和领域资产能力通过明确 adapter 接回，不能复制第二套状态。

## Worker、Lease 与恢复

第一阶段继续使用当前进程内队列调度 ID，不引入 Redis、Celery、Temporal 或其它外部组件。

但 Worker 必须以 Task Attempt 为领取单位，并把数据库作为调度事实来源：

- 队列只传 `attempt_id`。
- 领取时原子写入 `lease_owner/lease_expires_at/heartbeat_at`。
- Worker 加载 Task、Run、Checkpoint 和 Tool Effect 后再执行。
- 已成功、已取消或 lease 属于其它有效 Worker 的 Attempt 不执行。
- 启动恢复只重新入队安全的 `prepared/interrupted/retrying` Attempt。
- `waiting_for_input` 不占 Worker，也不在启动时自动入队。
- lease 过期不能覆盖 `unknown` 外部副作用。

## Multi-Agent Task Mapping

本 Sprint 把文章团队作为唯一重建样本：

- Director 保持根 Workflow Run 的用户会话控制权。
- Writer、Reviewer 分别对应持久化 Task。
- 每次 `agent.as_tool()` 调用对应一个 Task Attempt 和独立 SDK Session namespace。
- 子 Agent 成功先原子保存 Artifact、Attempt 终态和 Event，再把 Artifact 引用作为 Tool
  Output 交回 Director。
- 子 Agent 超时先保存失败 Attempt；Director 可以请求受控重试，但不能把根 Run 标成功。
- 服务重启后，已成功 Task 直接复用 Artifact；未完成纯模型 Attempt 根据状态创建 resume/retry
  Attempt，不重复覆盖历史 Attempt。

本 Sprint 不允许子 Agent 创建孙 Agent，不实现任意 Skill 动态生成无限 Task，也不实现并行
Writer/Reviewer。后续并行化必须先基于本阶段的 Task、Attempt、Checkpoint 和 lease 语义。

## Backend Projection Contract

Conversation 详情和 SSE `run.updated` 必须返回相同的权威投影：

- Run 状态、`state_version`、当前 Checkpoint。
- `expected_input_kind` 和 `allowed_actions`。
- Task 列表、依赖、当前 Attempt 和 Completion 状态。
- Function Call 与 Task Attempt 的稳定关联。
- Run 成功、失败或等待的机器原因。
- 最后事件 sequence。

每次控制命令返回提交后的完整权威 Run Projection。SSE 事件携带递增 sequence 和
`state_version`；前端收到较旧版本时忽略，发现 sequence 缺口时重新拉取详情。

SSE 进入终态前必须发送最终 `run.updated`。前端收到终态或 SSE 关闭时再执行一次有界详情读取，
以数据库事实收敛，不依赖本地推断终态。

## Frontend State Rules

- 不再通过“存在某种 Artifact”猜 Function Call 是否完成。
- `等待执行/执行中/失败/完成/结果不确定` 直接来自 Task Attempt 或 Tool Step 投影。
- 根 Run 终态时，任何非终态 Function Call 必须显示后端给出的
  `failed/interrupted/unknown`，不能继续旋转。
- Approve 按钮使用后端 `approval_purpose/on_approve_action` 展示真实后果，例如：
  - “批准选题并继续写作”
  - “批准最终稿并结束任务”
- Composer 在存在等待输入的 Run 时，展示该 Run 的 `expected_input_kind` 和允许操作；不能
  静默创建新 Run。
- 新 Run、继续当前 Run和从已完成 Run 创建后续任务必须在界面上有可区分的状态反馈。

## MLflow Semantics

MLflow 只负责可观测性，不驱动恢复。

- `workflow_run_id` 标识持久化根工作流。
- `task_id/attempt_id` 标识一次可恢复工作。
- 每次 Worker execution attempt 可以产生独立 Trace 或独立根 Span。
- Trace 结束只表示本次执行 Attempt 已结束，不等于 Workflow Run 已成功。
- `waiting_for_input` 可以结束当前 Trace，但数据库 Run 仍保持非终态。
- 页面不能根据 MLflow Tree 状态推断业务任务状态。
- Trace 必须记录最终数据库状态、Checkpoint ID、Task/Attempt ID 和结束原因，便于交叉定位。

## In Scope

- 上述身份、状态机、控制命令和投影契约。
- 删除两套旧 Agent 控制面、不可达前端和对应测试。
- 重建统一 Task、Attempt、Checkpoint、Memory Snapshot、Tool Effect 表和破坏性 migration。
- 文章团队单纵向链路重建。
- Approve 推进/结束语义拆分。
- 同一 Conversation 的 Follow-up Run 与有界 Memory 继承。
- Task Attempt 级 Worker lease、启动恢复和取消检查。
- 前端权威状态投影和“等待执行”事故修复。
- 数据库、SSE、API、前端和 MLflow 关联测试。
- 更新 `docs/spec.md`、相关设计文档和 `docs/progress.md`。

## Out of Scope

- 通用并行 Task DAG 和动态 fan-out/fan-in。
- 通用 Probe 执行器、Probe UI 和 Snapshot 分支提升工具。
- 子 Agent 创建孙 Agent。
- 多 Skill 组合、Workflow DSL 或可视化工作流编辑器。
- LangGraph、Temporal、Celery、Redis、外部消息队列或独立 Worker 服务。
- 把现有图片、语音、字幕、视频和 YouTube 发布全部迁移为新 Task Graph。
- 多实例生产调度、分布式锁和跨服务事务。
- 自动重放结果不确定的 Provider 副作用。
- Deferred Evaluation 和内容质量评分发布门槛。
- 旧 Agent/Native Agent API、数据库记录、前端和测试的兼容保留。
- 旧本地 Agent Run、Context、Artifact 和 Approval 数据搬迁。

## Delivery Sequence

1. 把真实事故时间线固化为 QA 记录和失败测试，备份本地数据库。
2. 删除未挂载旧 Agent 后端、不可达前端、旧表和只服务旧 Runtime 的测试。
3. 删除当前 Native Agent 控制 API、Worker、覆盖式 Checkpoint 和前端状态猜测。
4. 建立统一 schema、状态机、Tool Effect 和权威 Projection。
5. 重建结构化控制命令及前端 allowed actions。
6. 重建 Workflow Compiler、Writer、Reviewer、Approval 的持久化 Task/Attempt 链。
7. 增加不可变 Checkpoint、Memory Snapshot、Follow-up Run、Worker lease 和启动恢复。
8. 运行自动化、强制中断、空库迁移和真实浏览器回归。

每一步完成后更新 `docs/progress.md`。任何一步若需要改变安全副作用边界，必须暂停并单独评审，
不能加入自动兜底或静默降级。

## Deliverables

- 删除清单、破坏性数据库 migration、新 ORM model 和约束。
- Durable Task Runtime service。
- 结构化 Run command API 和权威 Projection API/SSE。
- 文章团队 Task/Attempt adapter。
- Conversation Memory Snapshot builder。
- Checkpoint save/load/CAS 和恢复服务。
- Attempt worker lease 与启动恢复。
- Agent 页面 Task、Attempt、Approval 和终态展示。
- 自动化测试、真实事故回归记录和文档更新。

## Done Means

- 批准阶段性选题时，同一 Workflow Run 从 Gate 推进到下一 Task，不被误标为成功。
- 批准真正最终稿时，全部必需 Task 完成后 Run 才进入成功终态。
- 用户在等待输入时回复“继续”不会静默创建缺少上下文的新 Run。
- 已完成 Run 的后续制作会创建带 parent/checkpoint/memory 引用的新 Run，并能读取经过确认的
  Artifact。
- Writer/Reviewer 超时或失败时，Task Attempt 有明确失败事实，Run 不会因 Director 返回说明
  文本而成功。
- 服务在 Writer 成功、Reviewer 未开始时重启，恢复后复用 Writer Artifact，只执行 Reviewer。
- 服务在等待用户审批时重启，不占 Worker、不自动推进；用户操作后从同一 Checkpoint 继续。
- Run 终态时前端没有仍显示“等待执行”的 Function Call。
- API 详情、SSE 最终 Snapshot、数据库状态和前端展示一致。
- MLflow Trace 结束不改变数据库 Workflow Run；数据库可以通过 Run/Task/Attempt 定位 Trace。
- 仓库只剩一套 Agent Conversation、Run、Task、Checkpoint、Worker、API 和前端状态实现。
- 旧 Agent 和 Native Agent 的本地测试数据已按合同删除，不存在兼容层或双写路径。

## Verification

```bash
./scripts/check.sh
git diff --check
```

必须新增自动化场景：

1. 静态检查确认旧 Agent/Native Agent 控制模块、路由和不可达前端已经删除。
2. 空数据库迁移后只存在一套 Agent Conversation/Run/Task/Checkpoint 表族。
3. `stage_gate` Approve 推进下一 Task，Run 不结束。
4. `final_result` Approve 在所有必需 Task 完成后结束 Run。
5. waiting Run 的继续命令复用同一 Run 和 Checkpoint。
6. terminal Run 的 follow-up 创建新 Run，并固定 parent、Checkpoint 和 Memory Snapshot。
7. Writer 超时产生 failed Attempt，根模型说明不能把 Run 改成 succeeded。
8. Writer 成功后的进程中断恢复不重复生成 Artifact。
9. Checkpoint revision 冲突明确失败并重新合并，不丢更新。
10. lease 过期恢复只领取安全 Attempt。
11. unknown Tool Effect 阻止自动恢复。
12. SSE sequence/state_version 缺口触发详情收敛。
13. Run 终态时所有前端 Task/Function Call 均为终态。
14. Conversation owner 隔离和跨 Run Artifact/Memory 引用权限。

真实回归：

- 使用独立测试 Conversation 复现“先给选题 → 批准其中一个 → 继续写作”。
- 在批准后确认数据库仍是同一 Workflow Run，下一 Task 已创建。
- 在 Writer 和 Reviewer 之间重启后端，确认只恢复未完成 Task。
- 在审批等待期间关闭浏览器和后端，再启动并完成审批。
- 对比数据库、API、SSE、页面和 MLflow 中的 Run/Task/Attempt/Trace 关系。
- 保存测试 ID、状态时间线和截图，不修改 2026-07-30 原始事故记录。

## Risks / Notes

- 这是跨数据库、Worker、SDK Session、API、SSE 和前端投影的控制面改造，实施期间不能与其它
  Native Agent Runtime 重写并行合并。
- 用户已确认当前没有真实用户，允许删除本地 Agent 测试数据和错误设计；传统任务、Skill、
  Style、账号、频道和领域资产能力不因此获得删除授权。
- SQLite 可以支撑本阶段单进程纵向验证，但 lease、并行合并和生产多实例能力不能据此宣称完成。
- Agents SDK 继续负责模型 Tool Loop；Durable Task、Memory、Checkpoint、恢复和业务终态由
  DoodleStory Runtime 负责。
- 不引入“发生异常就创建新 Run”“找不到状态就重新执行 Tool”之类兜底。

## Handoff

本 Sprint 完成后再评审第二阶段：

1. 通用多 Agent Task DAG、并行 fan-out/fan-in 和全局 Provider 并发。
2. Probe Attempt、Snapshot 分支、证据 Gate 和通过后的 Snapshot 提升。
3. 图片、语音、字幕、视频和发布 Tool 的 Task 化。
4. PostgreSQL、多实例 Worker 或 Temporal/LangGraph 等持久化编排方案的成本收益。
