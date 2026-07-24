# Sprint 114：`idea-to-comic` Skill、方案确认与真实事件流

## Status

Complete。Sprint 113 已 Complete；用户于 2026-07-24 明确要求开始开发，同日完成实现、自动化、真实 Provider 与浏览器验收。

## Goal

用第一个正式运行时 Skill `idea-to-comic` 替换当前固定两格、单次结构化规划后立即生图的硬编码路径。Agent 先根据 Idea 形成可查看的故事与画面方案，等待用户确认后才调用真实 `generate_image`；前端通过持久化 SSE 事件流展示方案、等待确认、Tool 进度和最终结果。

## Product outcome

用户完成以下真实链路：

```text
输入 Idea + @风格
→ Agent 加载 idea-to-comic Skill
→ 补齐并检查故事
→ 生成漫画方案
→ 页面展示方案卡并等待用户确认
→ 用户批准或提出修改意见
→ 批准后才创建 GenerationTask、Panel 和图片 job
→ 页面实时展示生成进度
→ 任务完成后继续在同一对话中交流
```

这一步证明“流程来自 Skill，能力来自 Tool，可靠性来自 Runtime”，而不是再写一套固定 Workflow。

## Preconditions

- Sprint 111 独立 Agent Shell 和检查器已完成。
- Sprint 112 MLflow trace 已完成。
- Sprint 113 SkillRegistry、`load_skill`、ToolRegistry 和 Generic Tool Executor 已完成。
- 当前图片 Provider、积分、GeneratedImage worker 和恢复规则可复用。

## In scope

### 1. 正式 `idea-to-comic` Skill

创建：

```text
backend/app/agent_skills/idea-to-comic/SKILL.md
```

Skill 必须规定方法，不写代码式分支图。至少包括：

1. 理解用户 Idea、已选风格和明确约束。
2. 补齐故事中缺失但创作所需的因果、人物动机和结尾。
3. 检查故事是否自洽、是否可分成连续画面、是否存在重复 Panel。
4. 形成一份用户能读懂的漫画方案：
   - 标题；
   - 一句话故事方向；
   - 每个 Panel 的剧情目标；
   - 每个 Panel 的画面目标；
   - 必须出现的图片文字；
   - 风格和画面比例；
   - 预计图片数与积分。
5. 在生图前调用 Runtime 提供的确认能力。
6. 只有批准后的方案可以驱动 `generate_image`。
7. 用户要求修改时，基于反馈生成方案新版本并再次确认。

第一版图片数量边界：

- 用户明确指定时允许 2–8 张。
- 用户未指定时 Agent 在 2–6 张内决定。
- 超过边界必须向用户解释并等待调整，不能静默截断。

### 2. 漫画方案 schema

替换当前固定 `panel-[12]` 的 `ComicPlan` 限制，定义版本化方案，例如：

```json
{
  "schema_version": 1,
  "title": "被裁员的第七天",
  "story_summary": "隐瞒失业到重新面对生活",
  "aspect_ratio": "3:4",
  "style_ref_id": "style-id",
  "panels": [
    {
      "panel_key": "panel-1",
      "story_beat": "早高峰逆着人群走出地铁",
      "visual_goal": "疲惫但克制",
      "required_text": [],
      "image_prompt": "简洁、可直接生成的单图指令"
    }
  ],
  "estimated_image_credits": 4
}
```

规则：

- Panel key 必须从 `panel-1` 连续编号。
- Panel 数量必须符合 2–8 边界。
- Story beat 不得完全重复。
- `image_prompt` 是 Agent 生成的最终单图要求，不再经过旧最终 Prompt 编译。
- Runtime 使用数据库中的真实风格快照校验 `style_ref_id`，不信任模型返回显示名。
- 方案批准前不创建图片 job、不占用图片积分。

### 3. 持久化 Artifact

新增最小 `agent_artifacts` 表，用于保存用户可见、可版本化的中间产物。

必须字段：

- `id: String(32)`，主键。
- `conversation_id: String(32)`，外键到 `agent_conversations.id`，级联删除。
- `run_id: String(32)`，外键到 `agent_runs.id`，级联删除。
- `artifact_type: Enum`，本 Sprint 只允许 `comic_plan`。
- `version: Integer`，同一 Run 内从 1 递增且大于 0。
- `status: Enum`：`draft/awaiting_approval/approved/rejected/superseded`。
- `content_json: Text`。
- `content_hash: String(80)`，保存 `sha256:<hex>`。
- `created_at / updated_at: DateTime`。

约束和索引：

- `(run_id, artifact_type, version)` 唯一。
- `content_hash` 绑定批准对象，防止批准后内容被替换。
- 索引只覆盖按 Run 读取当前方案的真实查询。
- 大模型原始响应不写入 Artifact；只保存通过 schema 校验的安全结构。

### 4. 持久化 Approval

新增最小 `agent_approval_requests` 表。

必须字段：

- `id: String(32)`，主键。
- `conversation_id: String(32)`，外键到 `agent_conversations.id`，级联删除。
- `run_id: String(32)`，外键到 `agent_runs.id`，级联删除。
- `artifact_id: String(32)`，外键到 `agent_artifacts.id`，级联删除并唯一。
- `artifact_hash: String(80)`。
- `approval_type: Enum`，本 Sprint 只允许 `comic_plan`。
- `status: Enum`：`pending/approved/changes_requested/cancelled`。
- `requested_at: DateTime`。
- `resolved_at: DateTime | null`。
- `decided_by_user_id: String(32) | null`，外键到 `users.id`，删除用户时 `SET NULL`。
- `feedback: Text | null`。

约束：

- 一个 Artifact 只能有一个 Approval Request。
- 只有 Conversation owner 可以决策；Admin 不得替其他用户批准。
- `approved` 必须绑定与当前 Artifact 完全一致的 hash。
- 重复提交同一决策必须幂等。
- `changes_requested` 必须包含非空反馈。

Run 状态：

- 方案等待用户时为 `waiting_for_input`。
- 批准后重新进入 `queued/running`。
- 请求修改后基于反馈生成新 Artifact 版本，再次进入 `waiting_for_input`。
- 取消 Conversation/Run 时 pending approval 进入 `cancelled`。

### 5. Approval API

新增：

```text
GET  /api/v1/agent/conversations/{conversation_id}/artifacts
POST /api/v1/agent/approvals/{approval_id}/decisions
```

Decision 请求：

```json
{
  "decision": "approve"
}
```

或：

```json
{
  "decision": "request_changes",
  "feedback": "结尾不要和解，改成主角独自开始新生活。"
}
```

接口必须完成归属校验、状态校验、Artifact hash 校验、幂等和 Run 恢复入队。

### 6. 生成副作用门禁

`generate_image` Tool Executor 必须拒绝以下请求：

- 没有 approved comic plan；
- approval 的 artifact hash 与当前方案不一致；
- Panel key 不属于已批准方案；
- 预计图片预算超过已批准数量；
- Run 已取消、失败或暂停。

该门禁是 Runtime 内部规则，不把 approval token 暴露给模型。

### 7. 持久化用户安全事件

新增最小 `agent_events` 表，作为前端事件流和断线恢复的事实来源。

必须字段：

- `id: String(32)`，主键，同时作为 SSE event ID。
- `conversation_id: String(32)`，外键到 `agent_conversations.id`，级联删除。
- `run_id: String(32)`，外键到 `agent_runs.id`，级联删除。
- `sequence: Integer`，Run 内从 1 递增且大于 0。
- `event_type: Enum`，只允许本合同列出的公共事件。
- `public_payload_json: Text`。
- `created_at: DateTime`。

约束：

- `(run_id, sequence)` 唯一。
- 事件只保存用户安全信息，不保存 chain-of-thought、完整 Prompt、API key 或原始 Provider 响应。
- 事件类型必须为受控枚举。
- Conversation + created_at/sequence 有真实查询索引。

第一版事件：

- `run.started`
- `skill.loaded`
- `artifact.created`
- `approval.requested`
- `approval.resolved`
- `tool.started`
- `tool.progress`
- `tool.completed`
- `tool.failed`
- `assistant.message`
- `run.completed`
- `run.failed`

### 8. SSE API

新增：

```text
GET /api/v1/agent/conversations/{conversation_id}/events
```

要求：

- `text/event-stream`。
- Conversation owner 鉴权。
- 支持 `Last-Event-ID` 或明确 `after` cursor，从数据库补发漏掉事件。
- 每次查询有界，避免把整段历史无限重放。
- 心跳只保持连接，不作为业务事件写库。
- 断线重连不重复执行 Tool，不改变 Run 状态。
- 本 Sprint 的 Agent 页面以 SSE 更新新事件；不能用 Mock event。
- 如果 SSE 不可用，页面显示连接错误并允许用户手动重连；未经授权不增加隐藏轮询兜底。

### 9. Frontend

- 对话中新增真实方案卡：
  - 标题与故事方向；
  - Panel 数量和每格摘要；
  - 风格、比例、预计积分；
  - “确认并开始生成”；
  - “提出修改”及反馈输入。
- 明确区分：
  - 草稿方案；
  - 等待确认；
  - 已批准；
  - 已被新版本替代。
- 批准是有成本副作用前的确认，按钮必须明确写出预计图片数和积分。
- 事件流用用户可理解的活动文本展示，不展示隐藏推理。
- SSE 重连后不能重复插入同一事件。
- 方案确认期间保留输入草稿；Run 等待用户时允许操作方案卡。

## Out of scope

- `@任务/@Panel/@图片版本/@角色`。
- 修改已有任务或 Panel。
- `inspect_image` 和自动 VL 修改循环。
- 用户 Memory、自定义 Skill。
- TTS、Remotion、抠图、媒体提取 Tool。
- 直接编辑 JSON 方案或无限画布。
- Token 级 chain-of-thought。
- 旧传统入口迁移。

## Deliverables

- 正式 `idea-to-comic` Skill v1。
- 可变 2–8 Panel 的 ComicPlan schema。
- Artifact、Approval、Event 模型与 migration。
- Approval 与 SSE API。
- 方案确认门禁和 Run 恢复。
- 方案卡、活动流和真实生成 UI。
- MLflow Skill/Artifact/Approval/Tool spans。
- 自动化、真实 Provider 和浏览器证据。

## Recommended implementation order

1. 先落 schema、migration、约束和 repository/service 测试。
2. 实现 Artifact/Approval 状态机与 API。
3. 实现安全事件写入和 SSE 断点续传。
4. 编写 `idea-to-comic` Skill 与可变 ComicPlan。
5. 把正式 Agent 从 `_invoke_comic_plan` 切到 Skill/Tool Loop。
6. 增加 approved artifact 门禁后接真实生图。
7. 实现方案卡和活动流。
8. 完成两条真实链路：批准生成、修改方案后再批准。

## Done means

1. 正式 Agent 会加载并记录 `idea-to-comic` Skill 版本/hash。
2. 用户未确认前不创建 GenerationTask 图片 job、不占用图片积分。
3. 用户批准后生成的 Task/Panel/Prompt 与批准 Artifact 一致。
4. 请求修改会产生新 Artifact 版本，旧版本标记 superseded，不覆盖历史。
5. 重复批准不会重复入队或重复生图。
6. 服务重启后 `waiting_for_input` Run 和 pending approval 可恢复。
7. SSE 断线后可从最后事件继续，不丢失、不重复副作用。
8. 页面展示真实 Skill/方案/Tool 进度，但不泄露隐藏推理。
9. 火苗/LIO 路由、图片积分、取消和晚到结果规则无回归。

## Verification

### Automated

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest \
  backend.tests.test_agent_conversations \
  backend.tests.test_agent_runner_recovery \
  backend.tests.test_agent_comic_creation
backend/.venv/bin/python -m compileall backend/app
npm run build --prefix frontend
git diff --check
./scripts/check.sh
```

新增测试至少覆盖：

- 2、6、8 Panel 合法；越界和不连续 key 拒绝。
- 未批准不能执行 generate_image。
- artifact hash 被改动后批准失效。
- approve / request_changes 权限和幂等。
- 重启恢复 waiting_for_input。
- Event 顺序、cursor、鉴权和去重。
- SSE 断线重连。
- 取消 Run 后 approval 和后续 Tool 行为。

### Real browser and provider

1. Idea + 风格生成方案，确认没有提前扣积分。
2. 提出一次方案修改，看到 v2 且 v1 保留。
3. 批准 v2，真实生成至少 2 张图片。
4. 生成过程中断开再连接 SSE，确认进度恢复。
5. 刷新页面和重启后端，确认等待确认/生成状态恢复。

## Handoff

完成证据：

- Conversation `d62f8c260a1241de876ebe64e4d15607`、Run `3bbb19b4725c47e8a93221b78b254654` 先生成 v1，修改后保留 v1 并生成 v2；批准前 `task_id` 为空、`image_call_count=0`、余额 30、占用 0。
- 批准 v2 后创建 Task `e429bdabef884e24b8337c717c2df78c` 和两个 Panel/图片 job，两张真实 `gpt-image-2` 图片成功，最终余额 28、占用 0。
- 后端断开时页面显示活动流连接错误和手动重连；重连后从 cursor 补齐 Panel/Run 完成事件，未重复创建 Tool 副作用。
- 针对性 30 项测试、全量 223 项后端测试、空库 Alembic、Python compileall、前端生产构建、`git diff --check` 和 `./scripts/check.sh` 通过。

- Sprint 114 Complete 后才激活 Sprint 115。
- 记录旧固定 `_invoke_comic_plan` 和相关 schema 是否已经无调用方；只有确认无调用方后才删除。
- 下一 Sprint 只扩展资源上下文和同一任务续作，不提前加入 VL 自动循环。

## New-window start prompt

> 请实施 Sprint 114。先完整阅读项目基线、路线图、`docs/contracts/sprint-114-idea-to-comic-skill-hitl-event-stream.md`、Skill/Tool Runtime、MLflow、Agent 架构/Tool 契约和前后端/数据库/工作流/UI 规范。按合同实现正式 `idea-to-comic` Skill、可变 ComicPlan、Artifact、Approval、Event、SSE、方案卡和批准后生图门禁。正式 `/agent` 不得使用 Mock；未批准前不得创建图片副作用。不要实现资源引用、VL、Panel 修改、TTS 或 Remotion。完成 migration、恢复/幂等/权限测试、真实 Provider 与浏览器验收，更新文档并创建中文详细 commit。
