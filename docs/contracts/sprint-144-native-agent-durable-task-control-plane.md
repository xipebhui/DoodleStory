# Sprint 144：聊天优先的 Durable Agent Task Runtime

## Status

Draft。本文只定义改造范围和验收标准，尚未授权实施。

## Goal

把当前“一次 Native Agent Run 对应一次模型执行”的错误控制方式，替换为一个聊天优先的
Durable Runtime：

```text
Conversation
└─ Workflow Run：一次完整用户目标
   └─ 动态 Task 图：可调度的业务步骤与人工 Gate
      └─ Attempt：某个 Task 的一次真实执行
         └─ Checkpoint：可恢复的不可变事实快照
```

用户始终在 `/agent` 聊天中创建、理解和推进工作。Task、依赖、Attempt 和 Checkpoint 是数据库
中的执行事实，支撑动态计划、恢复、重试和并行；它们不应把 Agent 页面变成传统任务后台、DAG
编辑器或原始模型 Response 查看器。

首条真实纵向链路为内容创作：

```text
初始计划
→ 选题研究
→ 选题确认 Gate
→ 正文撰写
→ 正文确认 Gate
→ Review
→ Review 确认 Gate
→ 完成
```

## Incident Baseline

2026-07-30 的真实事故必须被本 Sprint 消除：

- Conversation `b547d1eff60e47698ae0a0d40db1172a` 中，Run
  `ed979081ea33489ab17d44eaa280aafb` 生成候选选题后，用户以“使用第一个选题就可以”批准。
- 旧实现将这一选题决定错误处理为“最终文案确认”，直接把 Run 标记为
  `succeeded/article_approved`。
- 用户随后发送“继续”时，新 Run `ddca2d7d76fd45968a0e8820a9514e42` 只保存“继续”，没有
  继承已选选题、Artifact、审批反馈或恢复位置。

完成后，批准非终态 Gate 必须推进同一 Run 的后继 Task；“继续”“重试”等自然语言不再承担
核心恢复协议。

## Product Contract

### 聊天优先的呈现

- `/agent` 主界面继续是会话列表和聊天，不新增任务后台、DAG 画布或用户可编辑工作流。
- Run 启动后，聊天中展示一张简洁“本次计划”卡：说明当前目标、已知阶段与近端确认点。例如：
  “先研究账号和候选选题；你确认选题后，再写正文和审稿。”
- 任务运行时，聊天原位更新阶段摘要或追加有意义的系统消息，例如：
  “候选选题已完成，等待你的确认”“正文 v2 已交给审稿”“Review 建议修改结尾”。
- 用户可展开“查看本次计划”，查看当前已知阶段、自然语言状态、已完成产物与近端依赖。尚未执行
  的后续阶段必须标识为“后续计划”，允许在上游产物、用户决定或 Review 后受控调整。
- Task ID、Attempt、lease、模型 reasoning、Tool arguments、原始 Provider response、完整系统
  Prompt 和 chain-of-thought 不进入聊天主流；仅允许在权限保护的运行详情中提供脱敏诊断。

### 多阶段人工 Gate

- Skill 声明需要人工介入的业务意图，例如 `topic_selection`、`article_draft_review`、
  `editorial_review`，以及可接受的决定、所需反馈和批准后的业务后果。
- Runtime 负责创建 Gate、冻结待审 Artifact hash、保存 allowed actions 与用户决定、发布
  Checkpoint，并解除后继 Task 依赖；不能只由提示词约定。
- “批准”只解决当前 Gate，不能默认结束 Run。只有所有 required Task 的完成契约满足后，Run
  才能 `succeeded`。
- “要求修改”只失效被拒绝 Task 和下游 Task；已批准上游 Artifact 必须继续有效。Runtime 为目标
  Task 创建新的 Attempt 或受控修订 Task，不重新提交整条对话。
- 当前存在 Gate 时，用户输入必须由后端映射为结构化命令，或明确提示当前待处理决定；前端不得
  根据输入精确等于“继续”“重试”猜测恢复行为。

### 动态 Task 计划

- Run 创建时，根据固定 Skill Version、用户目标和已鉴权资源，生成并校验初始 Task 计划。
  初始计划至少覆盖当前可执行 Task、其输入 Artifact 和紧邻 Gate。
- 模型可以建议后续 Task、依赖、并行组和展示摘要；Runtime 只接受当前 Skill Version 允许的
  Task 类型、角色、输入输出契约和最大数量，并验证图无环、依赖有效和输入存在后再持久化。
- 上游产物、Gate 决定和 Review 结果可以发布计划修订，追加、替换或取消未执行后续 Task。
  已终态 Task、Attempt、Artifact 和 Checkpoint 不得覆盖。
- 本 Sprint 的文章链路按顺序执行；数据模型、调度器和 Projection 必须支持多个 ready Task 和
  依赖关系，但不在本 Sprint 落地图片并行或任意动态 DAG 执行器。

## In Scope

### 1. 唯一 Durable Runtime 数据模型

- 建立新的统一 Agent 运行时表和破坏性迁移，至少覆盖：
  - Workflow Run；
  - Task；
  - Task Dependency；
  - Task Attempt；
  - append-only Checkpoint；
  - Artifact；
  - Approval / Gate；
  - 用户安全 Event；
  - Tool Effect 账本。
- Run 固定 Skill Version、模型、账号、Style、频道及资源快照；Run 表示一个完整用户目标，而不是
  一次模型调用。
- Task 保存稳定 `task_key`、业务类型、用户可读标题、负责角色、状态、依赖、输入/输出 Artifact
  引用、完成契约、是否阻塞 Run 完成、错误与时间。
- Attempt 是 Task 的一次真实执行，保存输入 Checkpoint、SDK Session namespace、lease、心跳、
  开始/结束、模型/Tool 使用、错误与结果引用；历史 Attempt 不得覆盖。
- Checkpoint append-only，保存 Task 图版本、可用 Artifact ID/hash、用户决定、有界恢复上下文、
  事件游标、父 Checkpoint、原因与 state hash。Run 只引用当前 Checkpoint；不再使用覆盖式
  `workflow_checkpoint_json` 作为恢复事实。
- Gate 保存 purpose、目标 Task、待审 Artifact/hash、预期输入、allowed actions、
  `on_approve_action`、决定、反馈、审批人和时间。
- Tool Effect 单独保存幂等键、Task/Attempt、Provider request ID、状态和结果引用；Checkpoint
  不能替代外部副作用账本。

### 2. 调度、恢复与控制命令

- 继续使用进程内队列，队列消息只传 `attempt_id`；数据库是调度、恢复和权限事实来源。
- Worker 原子领取 Attempt lease 后加载 Run、Task、Checkpoint、Artifact 和 Tool Effect；
  已成功、已取消或被有效 lease 持有的 Attempt 不得执行。
- `waiting_for_input` 不占 Worker。服务重启只恢复安全的 prepared/interrupted/retrying Attempt，
  不自动执行等待人工决定的 Gate。
- 新建 Run、批准 Gate、提交修改意见、重试、取消使用显式 API 控制命令。每个命令返回提交后的
  权威 Run Projection。
- 子 Agent 或 Tool 失败必须让其关联 Attempt 明确失败或重试；根 Agent 的解释文字不能把未完成
  或失败的 required Task 标记为成功。

### 3. 文章团队纵向链路

- 为现有 `article-creation-team` 实现第一条 Task 化链路，而不是为某个 Skill 增加专用页面。
- 初始计划至少创建 `research_topics`、`select_topic_gate` 及其正文/Review 后续计划摘要。
- 选题批准后，在同一 Run 从批准后的 Checkpoint 释放正文 Task；选题和用户选择结果成为不可变
  Artifact 与 Checkpoint 事实。
- 正文和 Review 均产出版本化 Artifact，分别拥有 Gate，均支持批准和要求修改。
- 正文批准后释放 Review；Review 退回时只重做正文及其下游 Review；Review 批准后才完成 Run。
- 每个恢复 Attempt 从 Checkpoint 的事实和最小必需 Artifact 重建模型输入。SDK Session 只限
  Task Attempt 的模型上下文，不能把整个 Conversation 当作可变会话状态。

### 4. 聊天式权威 Projection 和 SSE

- Conversation 详情与 SSE 返回同一版本的权威投影，包括：
  - Run 摘要、当前用户可读阶段和当前 Checkpoint；
  - 当前 Gate、允许动作、按钮文案及其批准后果；
  - 用户可读的计划摘要、阶段卡、进度摘要和产物预览引用；
  - Task 的用户安全状态和最后 Event sequence。
- 前端只根据 Projection 渲染聊天、计划卡和 Gate 卡，不能从 Response、Artifact 是否存在或
  Function Call 猜测状态。
- SSE 事件带递增 sequence 与 state version；刷新、断线重连或发现缺口时，前端重新读取详情并
  按后端投影收敛。
- Run 已终态时页面不存在持续旋转或“等待执行”；等待 Gate、批准后继续、Task 失败和终态在聊天
  中均有简洁、准确且可恢复的表达。

### 5. 替换边界

- 迁移前只备份明确的本地数据库文件；保留用户、Skill、Style、频道、FileAsset、传统生成任务
  和传统资产数据。
- 删除当前 Native Agent 的错误控制层：覆盖式文章 Checkpoint、整 Run SDK Session 恢复语义、
  `/agent-loop` 控制 API、基于原始 Response 的主界面投影及精确字符串“继续/重试”路由。
- 删除未挂载旧 Agent 控制面及其重复的类型、测试、前端不可达代码；不保留旧 API、旧表、双写、
  compatibility adapter、占位实现或静默 fallback。
- 共享 Skill 管理、资源解析、账号/Style/频道快照、领域 Tool adapter、传统图片/视频任务及
  observability 基础设施，只能通过新 Runtime 的明确接口接回。

## Out of Scope

- 图片方案确认、图片并行生成、逐图质量 Gate、局部图片重跑、Probe Branch 和多 Agent 并行调度。
- 用户可编辑 DAG、工作流画布、传统任务后台或展示原始模型执行记录的聊天页面。
- Redis、Celery、Temporal、Inngest、独立 Worker 服务。
- 任意 Skill 无限生成 Task、多 Skill 同时运行、用户自定义代码/MCP Tool、跨 Run 自动 Memory 推断。
- 传统 `/tasks`、图片/视频任务产品域控制面的重写。
- 真实 YouTube 发布、额外收费模型能力或未授权生产副作用。

## Deliverables

- 新的 Alembic migration、唯一 Durable Runtime ORM/Schema/API/Worker。
- `article-creation-team` 的初始计划、三个人工 Gate、Checkpoint 恢复和局部修订链路。
- `/agent` 的聊天式计划卡、阶段摘要、Artifact/Gate 卡、SSE 收敛和折叠式运行详情。
- 事故回归 fixture、Task/Attempt/Checkpoint/Gate/lease/API/SSE/前端测试。
- 更新 `docs/spec.md`、`docs/progress.md`、运行时操作说明与 QA 报告。

## Done Means

- 用户在同一 Conversation 发起“先给选题，确认后写正文并审稿”后，聊天出现初始计划与选题 Gate；
  用户批准一个选题时，Run 不结束，正文在同一 Run 从批准 Checkpoint 继续。
- 正文和 Review 分别拥有独立 Artifact、Task、Attempt 和 Gate。每个 Gate 的批准、退回修改、
  重试、刷新和后端重启恢复均不丢失已确认事实。
- 用户刷新、SSE 重连或重启后端后重新进入同一 `/agent/{conversation_id}`，能看到准确聊天、当前
  计划摘要、当前 Gate 和权威状态；等待 Gate 不自动消耗 Worker。
- Review 退回只重做正文与下游 Review；选题不重跑。只有 Review Gate 批准且所有 required Task
  成功后，Run 才进入 `succeeded`。
- 计划可在上游结果后调整，但用户只通过聊天中的“后续计划”渐进感知，不需要理解 Task、Attempt、
  DAG 或 Checkpoint。
- 2026-07-30 事故 fixture 中“使用第一个选题就可以”推进正文，不再直接 `succeeded`；
  后续“继续”不会创建缺少已选选题上下文的新 Run。

## Verification

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest \
  backend.tests.test_agent_runtime \
  backend.tests.test_agent_runtime_recovery \
  backend.tests.test_agent_article_workflow
npm --prefix frontend test
npm --prefix frontend run build
./scripts/check.sh
git diff --check
```

Database and recovery checks:

- 从 Sprint 144 前开发库副本执行迁移，核对用户、Skill、Style、频道、FileAsset 与传统生成任务的
  数量和关键外键不变。
- 执行事故 fixture：选题批准、正文 Gate、正文修改、Review Gate、Review 批准。
- 分别在选题 Gate 等待、正文执行、Review Gate 等待时重启后端，验证只恢复安全 Attempt，
  不自动执行人工 Gate。
- 验证重复 Approve、过期 Checkpoint revision、lease 过期与 unknown Tool Effect 都按明确状态
  收敛，不重复外部副作用。

Browser QA:

- 在真实前后端完成：创建会话、查看本次计划、选题批准、正文批准、Review 退回并修订、Review
  批准、刷新、SSE 重连和后端重启恢复。
- 记录真实 Conversation、Run、Task、Attempt、Checkpoint、Gate ID 和必要截图到 QA 报告；
  浏览器控制台不得有 error/warning。

## Risks / Notes

- 这是控制面替换。实施前必须重新确认当前工作区、数据库文件和运行服务，避免混淆测试库与用户
  开发库。
- 动态计划必须由固定 Skill Version 允许的 Task 类型、数量和依赖规则约束；不能把模型输出的
  任意 DAG 当作可执行代码。
- 用户可读摘要可以由模型辅助生成，但状态机、Task、Gate、Artifact、Checkpoint 和恢复事实只能
  由 Runtime 写入。

## Handoff

下一 Sprint：在此 Runtime 上增加受控动态计划修订、聊天中的计划演进投影和更多业务阶段；图片
计划、并行生成和质量 Gate 继续留待 Sprint 146。
