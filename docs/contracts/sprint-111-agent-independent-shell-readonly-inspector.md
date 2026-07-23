# Sprint 111：独立 Agent 创作模块与只读任务检查器

## Status

Active。它是最新 Agent 路线的第一步，也是当前唯一允许实施的 Sprint。

## Goal

把正式 `/agent` 从旧任务工作台的内容区中拆出来，恢复为一个独立、会话优先的 Agent 创作模块；同时以真实 `GenerationTask`、`TaskPanel` 和 `GeneratedImage` 数据实现 AI 专属只读任务检查器。此 Sprint 只修正产品信息架构和读取体验，不修改 Agent 创作能力、不增加写操作、不新增数据库表。

## Why now

Sprint 107/108 已经证明真实 Conversation、Run、风格和两格任务链路可用，但当时把 `/agent` 放进旧 `Shell`，并让 Agent 任务跳转旧 `/tasks/{task_id}` 详情。最新产品决定已经改变：

- Agent 是独立创作工作区，不是旧任务后台里的一个 Tab。
- Agent 会话是主导航，旧图文任务、内容提取、风格等后台导航不能常驻抢占 Agent 左侧空间。
- Agent 任务详情要服务“查看进度、选中 Panel、继续对话”，不能直接复用旧 Pipeline 调试抽屉。
- Agent 与传统构建仍共享用户、积分、风格、角色和任务数据，但不共享页面外壳。

历史 Sprint 107/108 保留为真实完成记录；本 Sprint 只声明其 Shell 和旧详情跳转决策被后续产品决策替代。

## User-visible outcome

1. 用户访问 `/agent` 时进入独立 Agent 工作区，左侧只看到新对话、搜索和历史会话。
2. 用户可以新建、搜索、进入和继续真实会话。
3. 对话中的任务卡以紧凑方式展示真实标题、状态、进度、Panel 状态和当前运行信息。
4. 点击任务卡的“查看任务”后，在当前 Agent 上下文中打开 AI 专属只读检查器。
5. 刷新检查器 URL 后仍能恢复同一会话、同一任务和当前草稿；关闭后返回原对话位置。
6. 用户仍能从 Agent 模块低层级入口返回传统工作台，但旧后台导航不常驻在 Agent 页面。

## Preconditions

- Sprint 105–108、110 已完成。
- `agent_runs.task_id` 已关联现有 `generation_tasks.id`。
- 当前 Conversation、Message、Run、TaskCard 和任务详情 API 可读取真实数据。
- 开始实现前必须确认当前分支为 `codex/agent-feature`，并保留用户未跟踪文件。

## In scope

### 1. 路由与模块外壳

- `/agent`
  - 新建或进入空白 Agent 会话。
- `/agent/{conversation_id}`
  - 恢复指定真实会话。
- `/agent/{conversation_id}/tasks/{task_id}`
  - 在同一 Agent 模块中打开指定任务检查器。
- `/agent` 不再渲染旧通用 `Shell`，不显示旧“图文任务/内容提取/风格/角色”等常驻导航。
- 移除 Agent 页面内部的 `传统构建 / AI 构建` 分段切换。
- Agent 模块保留 DoodleStory 品牌、当前用户、积分余额和退出能力。
- 提供一个低层级、明确标注的“返回传统工作台”导航链接，目标为 `/tasks`。
- 旧 `/tasks`、`/tasks/{task_id}` 和其它后台路由保持原样。

### 2. Agent 会话工作区

- 保留 Sprint 108 已验证的会话列表、日期分组、搜索、空白入口、历史恢复和固定输入区。
- 保留真实 Conversation 独立草稿与已选风格的恢复行为。
- 会话切换、浏览器前进/后退、刷新和直接访问必须由 URL 驱动。
- 不把 Demo 的 Mock 会话、资源、图片或状态带入正式页面。
- 本 Sprint 不改变“每次发送必须选择一个真实 active 风格”的现有后端限制。

### 3. 紧凑真实任务卡

- 任务卡必须继续读取当前 Conversation 下真实 Agent Run 关联的同一 `GenerationTask`。
- 卡片至少展示：
  - 任务标题；
  - 任务状态；
  - `progress_current / progress_total`；
  - 每个 Panel 的序号、当前图片缩略图或明确状态；
  - 当前 Run 的用户可理解状态；
  - “查看任务”入口。
- 卡片不能直接铺成结果画廊，也不能默认展示完整 Prompt、Provider 或调试 JSON。
- 卡片状态原位更新，不为每次轮询重复追加消息。
- 本 Sprint 不展示“在对话中引用”，因为后端尚未接受 `task/panel/image_version` 引用；该入口在 Sprint 115 真实接通后再开放。

### 4. AI 专属只读任务检查器

- 检查器不复用旧 `TasksView`、`task-detail-drawer` 或旧 Pipeline 详情布局。
- 可以复用现有 API client、图片组件、状态组件和基础样式 token。
- 检查器至少展示：
  - 任务标题、状态和整体进度；
  - 按 `panel_order` 排序的 Panel 列表；
  - 当前 Panel 的当前图片、版本号、剧情目标和状态；
  - 任务失败或单图失败的用户安全错误；
  - 关闭检查器并回到原对话的操作。
- Panel 选择只改变检查器当前对象，不产生后端写操作。
- 不显示重新生成、接受、恢复、暂停、继续或 VL 检查等尚未接通按钮。

### 5. 最小 Agent 任务读取 API

新增只读接口：

```text
GET /api/v1/agent/conversations/{conversation_id}/tasks/{task_id}
```

接口必须：

- 校验 Conversation 属于当前用户；Admin 也不能越权读取别人的 Agent 会话。
- 校验该 Task 通过 `agent_runs.task_id` 关联到此 Conversation。
- 校验 Task 的 `owner_user_id` 与 Conversation owner 一致。
- 返回 Agent 检查器需要的有界数据，不返回无界日志或全部调试字段。
- Panel 按 `panel_order` 稳定排序。
- 每个 Panel 只返回当前图片及有界版本摘要；如果当前实现为了只读检查器需要版本列表，最大返回 20 个版本并按版本号倒序。
- 复用现有任务、Panel、图片和资产表；不创建 Agent 专用任务表。
- 不改变旧 `GET /tasks/{task_id}` 的返回契约。

建议响应最小结构：

```json
{
  "task_id": "task-id",
  "conversation_id": "conversation-id",
  "title": "任务标题",
  "status": "running",
  "progress_current": 1,
  "progress_total": 2,
  "panels": [
    {
      "id": "panel-id",
      "panel_order": 1,
      "story_beat": "剧情目标",
      "current_image": {
        "id": "image-version-id",
        "generation_number": 1,
        "status": "succeeded",
        "asset_id": "asset-id"
      }
    }
  ]
}
```

最终字段名可按现有 schema 习惯调整，但不得把旧任务完整调试 payload 原样返回给 Agent 页面。

### 6. 前端状态与可访问性

- 覆盖会话列表、对话详情和任务检查器的 loading、empty、error、running、failed、succeeded 状态。
- 打开检查器时保存对话滚动位置和输入草稿。
- 关闭检查器后恢复触发按钮焦点；浏览器后退等价于关闭检查器。
- 检查器需具备明确标题、关闭按钮 accessible name 和键盘焦点行为。
- 1440×900 与 1280×800 必须可用；不在本 Sprint 做移动端重设计。

## Database and persistence

- 不新增表、不新增列、不创建 migration。
- 继续共享：
  - `agent_conversations`
  - `agent_messages`
  - `agent_runs`
  - `agent_steps`
  - `generation_tasks`
  - `task_panels`
  - `generated_images`
  - `file_assets`
- 如果实现发现现有关系无法可靠证明 Conversation 与 Task 的关联，必须暂停并更新合同，不能通过前端参数或宽松查询绕过。

## Out of scope

- MLflow、Skill Registry、Tool Registry 和 Runtime 重构。
- 方案确认、Human-in-the-loop、SSE 或 Token 流。
- `@任务/@Panel/@图片版本/@角色`。
- Panel 修改、版本接受、版本恢复、再生成、VL 检查。
- 任务暂停/继续、Agent 行动轨迹写入。
- 用户 Memory、自定义 Skill、抠图、Remotion、TTS 或视频。
- 旧任务页重设计或旧 Pipeline 删除。
- 正式 `/agent` 中的 Mock、占位成功结果或禁用但看似可用的假按钮。

## Deliverables

- 独立 `AgentModuleShell` 或等价模块边界。
- 更新后的 Agent 路由解析与导航。
- 紧凑真实任务卡。
- AI 专属只读任务检查器。
- Agent 任务读取 schema 和 API。
- 权限、路由和前端关键行为测试。
- 浏览器验收记录与必要截图。
- 更新后的规格、进度和路线状态。

## Recommended implementation order

1. 先补后端只读 API、schema、权限和测试。
2. 从顶层路由拆出独立 Agent 外壳，保持旧页面不动。
3. 迁移并收敛 Sprint 108 会话区，删除 Agent 内模式切换。
4. 重做紧凑任务卡。
5. 实现稳定检查器路由和只读 Panel 选择。
6. 完成真实浏览器回归与文档收尾。

## Done means

1. `/agent` 不再被旧通用 Shell 包围，也不显示旧后台常驻导航或模式切换。
2. 新建、搜索、切换、刷新和重新打开真实 Conversation 全部可用。
3. Agent TaskCard 与传统任务列表仍引用同一 `generation_tasks.id`。
4. `/agent/{conversation_id}/tasks/{task_id}` 可以刷新恢复，关闭后回到原对话并保留草稿和滚动上下文。
5. 任务检查器只展示真实数据和真实可用操作，没有跳转旧详情、Mock 数据或假按钮。
6. 越权 Conversation、未关联 Task、跨用户 Task 均返回 404 或明确禁止，不泄露对象存在性。
7. 传统 `/tasks` 及其它工作台页面无回归。
8. 自动化检查和两个桌面视口浏览器验收通过。

## Verification

### Automated

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest \
  backend.tests.test_agent_conversations
npm run build --prefix frontend
git diff --check
./scripts/check.sh
```

需要新增或扩展测试覆盖：

- Conversation owner 可以读取关联 Task。
- 其他用户与 Admin 不能读取不属于自己的 Agent Conversation Task。
- Task 不属于指定 Conversation 时拒绝。
- Panel 排序和 current image 选择正确。
- 路由解析可以区分 Conversation 页面与任务检查器页面。

### Browser regression

在 1440×900 和 1280×800 真实浏览器完成：

1. 登录后直接访问 `/agent`，确认没有旧后台导航和模式切换。
2. 新建会话、搜索并切换历史会话。
3. 进入一条真实完成任务的会话，确认紧凑卡片状态和图片。
4. 打开任务检查器，选择不同 Panel，关闭后草稿和滚动位置仍在。
5. 直接刷新检查器 URL，确认同一会话和任务恢复。
6. 使用浏览器前进、后退验证 URL 与检查器状态一致。
7. 返回 `/tasks`，确认旧工作台和任务详情未回归。
8. 检查键盘焦点和认证后控制台 error/warning。

## Failure handling

- API 返回失败时检查器显示真实错误并允许重试读取，不跳转旧详情作为兜底。
- 任务或会话无权限时返回安全错误，不尝试只按 `task_id` 读取。
- 真实数据缺失时显示明确空态或数据损坏错误，不生成占位 Panel。

## Handoff

- Sprint 111 完成后才能激活 Sprint 112。
- 将本合同状态改为 Complete，更新 `docs/progress.md` 和全局路线图。
- 在 `docs/testing/` 保存浏览器验收报告。
- 下一阶段不再继续扩展前端写操作；Sprint 112 先建立 MLflow 观测基线。

## New-window start prompt

> 请实施 Sprint 111。先完整阅读根目录 `AGENTS.md`、`README.md`、`docs/spec.md`、`docs/progress.md`、`docs/implementation/agent-v1-implementation-roadmap.md`、`docs/contracts/sprint-111-agent-independent-shell-readonly-inspector.md`、`docs/standards/frontend.md`、`docs/standards/ui-interaction.md`、`docs/standards/python.md` 和 `docs/standards/database.md`。只按 Sprint 111 实现独立 `/agent` Shell、紧凑真实任务卡、AI 专属只读检查器和最小只读 API；不要实现 Mock、资源引用、Panel 写操作、VL、Skill、MLflow 或 Runtime 重构。完成全部自动化与真实浏览器验收，更新进度并创建中文详细 commit。
