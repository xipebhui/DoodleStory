# Sprint 116：Panel 版本操作、VL 检查与任务控制闭环

## Status

Complete（Closed）。取代未实施的 Sprint 109 Draft；Sprint 115 已 Complete，用户于 2026-07-24 明确授权从其基线继续，Sprint 116 于 2026-07-25 完成实现与验收，并于 2026-07-26 通过独立 QA 复核正式闭合。

## Goal

在稳定的 `@任务/@Panel/@图片版本` 上下文上，完成对同一个 GenerationTask 的局部修改闭环：用户可以生成目标 Panel 的新版本、接受版本、恢复历史版本；Agent 可以调用 `inspect_image` 获取真实视觉证据，在严格预算内建议一次修改或等待用户决定；任务支持持久化暂停/继续，所有动作通过安全事件流和 MLflow 可观察。

## User-visible outcome

- “把第 3 张表情改得更紧张，衣服和场景不变”只创建 Panel 3 的新版本。
- “恢复 v1”只切换当前版本，不调用图片 Provider、不扣积分。
- “接受当前版本”明确记录用户选择。
- Agent 可以检查故事匹配、人物一致性、文字准确性和明显瑕疵。
- Agent 最多自动提出或执行一次受批准的修订，不会无限循环生图。
- 用户可以暂停后续 Agent/Panel 步骤，并继续恢复；已提交 Provider 的请求按现有晚到规则处理。

## In scope

### 1. Atomic Tools

新增模型可见 Tool：

#### `inspect_image`

输入和输出遵循 `docs/design/agent-tool-contracts.md`，至少支持：

- `story_alignment`
- `character_consistency`
- `continuity`
- `text_accuracy`
- `visual_artifacts`

Runtime 必须：

- 校验 image_version 属于授权 Task/Panel。
- 使用真实公网资产或 Provider 支持的安全输入。
- 保存 Tool Call、VL Provider/model、Tool Result、延迟和错误。
- 不把完整原图 URL 或 Provider 原始响应暴露到公共事件。

#### `generate_image`

扩展为已有 Panel 创建新版本：

- 只允许目标 Panel。
- 复用 Task 风格、比例、角色参考和当前最终 Prompt。
- 用户修改指令作为 `revision_instruction` 保存。
- Agent 生成的新 Prompt 必须保持用户未要求改变的约束。
- 每次成功新图扣 1 积分。

版本接受/恢复是 Runtime 确定性命令，不作为模型自由调用 Tool。

### 2. Version state

复用现有：

- `generation_number`
- `is_current`
- `source_type`
- `user_instruction`
- `previous_prompt`

新增最小 migration，明确保存“用户已接受”这一业务事实：

- `generated_images.accepted_at: DateTime | null`
- `generated_images.accepted_by_user_id: String(32) | null`，外键到 `users.id`，用户删除时 `SET NULL`

这两个字段不新增索引；当前版本查询仍按 Panel 和既有版本排序完成，不增加没有查询依据的索引。

恢复行为：

- 在同一数据库事务中把目标成功版本设为 `is_current=true`，同 Panel 其它版本设为 false。
- 不改写 generation_number。
- 不删除后续版本。
- 不调用图片 Provider、不占用或扣除积分。
- 重复恢复同一当前版本幂等。

接受行为：

- 只允许成功且当前版本。
- 重复接受幂等。
- 接受不是删除其它版本。

### 3. APIs

建议新增 Agent 语义 API：

```text
POST /api/v1/agent/conversations/{conversation_id}/tasks/{task_id}/panels/{panel_id}/regenerations
POST /api/v1/agent/conversations/{conversation_id}/tasks/{task_id}/panels/{panel_id}/versions/{image_id}/accept
POST /api/v1/agent/conversations/{conversation_id}/tasks/{task_id}/panels/{panel_id}/versions/{image_id}/restore
POST /api/v1/agent/runs/{run_id}/pause
POST /api/v1/agent/runs/{run_id}/resume
```

所有接口必须使用 Conversation → Task → Panel → Version 归属链校验，不得只按子 ID 操作。

再生成请求必须包含：

```json
{
  "instruction": "表情更紧张，衣服、构图和场景不变",
  "source_image_version_id": "image-id",
  "expected_credit_cost": 1
}
```

前端执行前必须明确确认成本。

### 4. VL decision policy

第一版严格预算：

- 每个新图片版本最多 1 次 `inspect_image`。
- 每个用户修改 Turn 最多自动创建 1 个额外图片版本。
- `inspect_image.verdict=accept`：Agent 建议接受，但不替用户点击接受。
- `revise`：Agent生成明确修改建议；只有用户在本 Turn 已授权一次自动修订时才可再生成，否则进入 `waiting_for_input`。
- `ask_user`：进入 `waiting_for_input`。
- `blocked` 或 VL 失败：明确失败或等待用户，不调用未授权备用 VL。

不允许：

- 无限 VL → 生图循环。
- 因低分自动生成多次。
- VL Provider 失败时静默跳过检查并标记通过。

### 5. Pause and resume

- `pause` 作用于 Agent Run 的后续步骤和尚未提交的图片 Tool。
- 已经发给同步图片 Provider 的请求不能保证物理终止；返回后按当前取消/晚到合同保存或丢弃，具体语义必须在 UI 明示。
- paused Run 不被启动恢复扫描自动执行。
- `resume` 幂等地重新入队，从持久化 checkpoint 继续。
- terminal Run 不能暂停或继续。
- 本 Sprint 不把旧 GenerationTask cancel 重新命名为 Agent pause。

### 6. Public activity events

在 Sprint 114 `agent_events` 上增加：

- `panel.revision_requested`
- `image.version_created`
- `image.inspection_started`
- `image.inspection_completed`
- `image.version_accepted`
- `image.version_restored`
- `run.paused`
- `run.resumed`

事件展示用户安全事实，不展示隐藏推理或完整 Prompt。

### 7. Frontend inspector

Sprint 111 只读检查器升级为真实操作界面：

- Panel 列表和当前选择。
- 当前图片与历史版本。
- Agent/VL 检查摘要。
- “再生成一个版本”。
- “接受当前版本”。
- “恢复此版本”。
- “在对话中引用”。
- 任务/Run 顶部暂停或继续。

交互规则：

- 再生成前确认复用哪些资源、将创建新版本、旧版本保留、预计扣 1 积分。
- 生成期间旧当前版本仍可查看。
- 新版本成功后是否自动设 current 必须在实现前固定；建议成功后设为 current，但不自动标记 accepted。
- 恢复和接受后原位更新，不关闭检查器。
- 所有失败保留输入指令并给出恢复操作。

## Out of scope

- 多次自动修订、复杂质量评分优化。
- 用户自定义 VL 规则。
- Reference comic、抖音资源。
- TTS、Remotion、抠图、视频。
- 多 Agent。
- 删除历史版本。
- 把 MLflow trace 直接展示给普通用户。

## Deliverables

- `inspect_image` Tool 和真实 VL adapter。
- Panel 新版本 Tool 路径。
- 接受/恢复持久化与 API。
- Pause/resume 状态机和恢复。
- 活动事件与 MLflow trace。
- 完整 Agent 任务检查器写操作。
- Evaluation case、自动化和真实浏览器/Provider 证据。

## Recommended implementation order

1. 固定 VL Provider/API shape 和真实 smoke。
2. 实现版本接受/恢复的确定性 service 与测试。
3. 实现 Panel 再生成的幂等 Tool 路径。
4. 实现 `inspect_image` 与严格预算。
5. 实现 pause/resume。
6. 扩展事件和检查器。
7. 做取消、晚到、重启和重复投递故障注入。

## Done means

1. 修改一个 Panel 不改变其它 Panel 的图片、Prompt 或版本状态。
2. 同一再生成 Tool Call 重放不重复创建版本或扣费。
3. 恢复旧版本不调用 Provider、不扣积分。
4. 接受/恢复只允许当前用户、正确 Task/Panel 下的成功版本。
5. VL 输入、结果、Agent 决策和版本变化可以从 AgentStep、Event 与 MLflow 对齐追踪。
6. 单 Turn 自动修改次数不超过 1。
7. 暂停后不启动新步骤，继续后从 checkpoint 恢复。
8. 取消或过期 Run 的 Provider 晚到结果不复活 Run、不重复扣费。
9. 页面刷新和服务重启后恢复当前 Panel、版本、检查结论和运行状态。

## Verification

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest \
  backend.tests.test_agent_runner_recovery \
  backend.tests.test_agent_comic_creation
backend/.venv/bin/python -m compileall backend/app
npm run build --prefix frontend
git diff --check
./scripts/check.sh
```

新增测试至少覆盖：

- Panel/Version 归属和越权。
- 局部修改与其它 Panel 不变。
- generation_number、is_current、accepted 行为。
- 恢复不调用 Provider/积分 service。
- 再生成幂等和积分。
- VL verdict 四种分支和预算上限。
- pause/resume/terminal 状态。
- 重启、重复投递、取消、晚到结果。

### Real browser and provider

1. 引用一个真实 Panel，生成一个新版本。
2. 查看真实 VL 检查结果。
3. 接受新版本。
4. 恢复旧版本并确认没有扣积分。
5. 生成期间暂停和继续。
6. 刷新、断开 SSE、重启后端后恢复。

## Implementation result

- 新增 `accepted_at/accepted_by_user_id` 最小 migration，并以 Conversation → Task → Panel → Version 完整归属链实现接受、恢复和目标 Panel 再生成；新版本成功后成为 current，旧版本保留，接受/恢复均幂等，恢复不调用 Provider 或积分服务。
- `generate_image` 扩展为面板修订原子 Tool；沿用现有图片队列执行长任务，不新增 Workflow 引擎。纯视觉修改会确定性保留原图片文字和布局，只有指令明确涉及文字、旁白、对白、标题或排版时才允许改动文字计划。
- 新增真实多模态 `inspect_image` adapter，严格校验 JSON schema，保存 Tool Call/Result、Provider、model、延迟和失败；每个版本最多检查一次。`accept/revise/ask_user/blocked` 四种裁决均有确定状态，VL 失败不降级、不假定通过。
- 每轮图片预算为 2：用户版本之外只有显式勾选授权时才允许一次自动修订，且不会替用户接受版本。图片 Worker 完成后使用线程安全非阻塞通知唤醒 Agent，避免 VL 长调用反向阻塞图片任务并误改成功状态。
- Agent 检查器提供当前/历史版本、检查摘要、成本确认、再生成、接受、恢复、引用，以及 Run 暂停/继续；失败保留修改指令。暂停只阻止后续步骤，UI 明示已提交 Provider 的请求仍可能按既有晚到规则完成。
- 公共事件已覆盖 `panel.revision_requested`、版本创建/接受/恢复、检查开始/完成和 Run 暂停/继续；刷新、SSE 断线与服务重启后均从数据库恢复。

## Verification result

- 针对性：`backend.tests.test_agent_panel_versions backend.tests.test_agent_runner_recovery`，18 项通过。
- 全量：`python -m unittest discover -s backend/tests`，240 项通过。
- `python3.11 -m compileall backend/app`、空 SQLite `alembic upgrade head`、`npm run build --prefix frontend` 和 `git diff --check` 均通过。
- 真实浏览器/Provider：在本地隔离数据库中创建两格漫画并生成真实 `gpt-image-2` 图片；对 Panel 1 创建 v2，余额 28→27。真实 `gpt-5.4` VL 返回 `accept`，分数为故事匹配 0.98、人物一致性 0.90、连续性 0.95、文字准确性 1.00、明显瑕疵 0.93。随后接受 v2、恢复 v1，余额保持 27；刷新和后端重启后 current/accepted/VL 摘要及事件仍存在。暂停/继续也在生成期间通过。
- 首次真实验收暴露“同步等待 Agent 通知会在 VL 较慢时把成功图片误标失败”，已改为非阻塞线程安全入队并补回归。用户确认慢生图不是当前关键路径，因此修复后没有重复调用图片 Provider；复用了该次已经真实生成且真实检查的测试资产完成接受、恢复和刷新验收，正式产品代码未加入 Mock、占位成功或兼容兜底。

## Handoff

- Sprint 116 Complete 后才能激活 Sprint 117。
- 原 `sprint-109-agent-panel-iteration-vl-draft.md` 标记 Superseded，不再实施。
- 下一阶段按 `sprint-117-pluggable-skill-management-agent-loop.md` 实现 Skill CRUD、发布版本、
  `@Skill` 和通用内容创作 Agent Loop。
- Evaluation 已顺延到全部计划功能完成后的最终阶段，不在 Sprint 117 实施。

## Contract closure

- QA 报告：`docs/qa/sprint-116-agent-panel-version-vl-loop-report.md`
- QA verdict：`PASS`
- 复核命令：`SESSION_SECRET=... ./scripts/check.sh`
- 复核结果：240 项后端测试、Python compileall、空库 migration 和前端生产构建全部通过。
- 阻塞项：无。
- 未纳入本合同：生产部署与 `GO_INTERNAL/NO_GO`，由 Deferred 的最终 Evaluation 阶段负责。

## New-window start prompt

> 请实施 Sprint 116。先完整阅读项目基线、路线图、`docs/contracts/sprint-116-agent-panel-version-vl-loop.md`、Agent Tool 契约、当前资源引用、图片版本、积分、取消/晚到和后端工作流规范。按合同实现真实 `inspect_image`、目标 Panel 新版本、接受/恢复、严格一次自动修订预算、pause/resume、事件和检查器操作。所有写操作必须走 Conversation→Task→Panel→Version 权限链；恢复不得调用 Provider或扣积分；不得无限自动循环。完成 migration（如确有需要）、自动化、故障注入、真实 Provider 与浏览器验收，更新文档并创建中文详细 commit。
