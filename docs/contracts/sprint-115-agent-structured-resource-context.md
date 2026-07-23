# Sprint 115：结构化资源引用与同一任务续作

## Status

Planned。只有 Sprint 114 Complete 后才能激活。

## Goal

把当前只支持一个风格的 `@` 入口扩展为受权限控制的结构化资源上下文，使用户可以在 Agent 对话中引用现有风格、角色、任务、Panel 和图片版本，并让 Runtime 根据资源组合明确区分“创建新任务”和“继续修改已有任务”。本 Sprint 建立真实引用和路由语义，不实现 VL 自动检查或图片版本写操作。

## User-visible outcome

- 用户可以从资源菜单搜索并加入 `@风格`、`@角色`、`@任务`。
- 选中任务后可以继续加入属于该任务的 `@Panel` 和 `@图片版本`。
- 从任务检查器点击“在对话中引用”会把结构化标签加入当前草稿，不覆盖已有文字。
- Agent 能读取引用对象的真实、授权、受控摘要。
- 引用已有 Task/Panel 时，Runtime 识别为续作上下文，不再创建一条无关新任务。
- 用户仍需在后续 Sprint 116 才能真正执行“再生成、恢复、接受、VL 检查”等版本写操作。

## Resource model

继续使用 `AgentResourceRef`：

```json
{
  "kind": "panel",
  "id": "panel-id",
  "display_name": "Panel 3"
}
```

客户端 `display_name` 仅用于即时显示，后端必须用数据库规范数据重写，不得信任。

支持种类：

- `style`
- `character`
- `task`
- `panel`
- `image_version`

## Valid combinations

### Create new comic

- 必须：一个 `style`
- 可选：0–3 个 `character`
- 禁止：`task/panel/image_version`

### Continue existing task

- 必须：一个 `task`
- 可选：一个属于该 Task 的 `panel`
- 可选：一个属于该 Panel 的 `image_version`
- 可选：风格和角色只作为上下文展示，不允许静默替换任务已保存快照

### General discussion

- 可以没有资源。
- 不产生图片副作用。

### Rejected combinations

- 多个 Task。
- Panel 不属于 Task。
- Image Version 不属于 Panel。
- 跨用户对象。
- 已删除/停用且不能用于新任务的 Style。
- 角色不属于当前用户。
- 同时要求创建新任务和修改已有任务但缺少明确目标。

## In scope

### 1. Resource query APIs

为 `@` 菜单提供有界、分类型的真实查询：

```text
GET /api/v1/agent/resources/styles?query=&limit=
GET /api/v1/agent/resources/characters?query=&limit=
GET /api/v1/agent/resources/tasks?query=&limit=
GET /api/v1/agent/resources/tasks/{task_id}/panels
GET /api/v1/agent/resources/panels/{panel_id}/image-versions
```

要求：

- 每个列表后端限制最大数量，默认 20，最大不超过 50。
- 只返回菜单需要的 summary。
- 普通用户只能搜索自己的 Task/Character；Style 按现有全局 active 规则。
- Panel/Image Version 必须通过父资源路径或后端归属校验。
- 不允许前端拉取所有任务后本地搜索。

### 2. Resource resolver

新增统一 `AgentResourceResolver` 或等价 service：

- 解析 Turn 中的 refs。
- 按 kind 批量读取。
- 校验所有权、父子关系、状态和组合规则。
- 生成规范 display name。
- 构造模型可见的安全上下文。
- 构造 Runtime 内部授权上下文。
- 在消息保存前完成解析；任一引用失败时整条消息不入队。

模型上下文示例：

```json
{
  "resource_context": {
    "task": {
      "id": "task-id",
      "title": "被裁员的第七天",
      "status": "succeeded"
    },
    "panel": {
      "id": "panel-id",
      "panel_order": 3,
      "story_beat": "收到消息后强忍紧张"
    },
    "image_version": {
      "id": "image-id",
      "generation_number": 2,
      "is_current": true
    }
  }
}
```

不向模型提供 owner_user_id、内部存储路径、API key 或无关任务数据。

### 3. Context replay

- `build_agent_input()` 必须读取并注入每条消息已保存的规范资源引用，不能继续只传文本。
- 重放时重新校验当前用户与资源关系，或使用创建 Turn 时保存的安全快照；具体策略必须在实现前写入代码注释与测试。
- 为防止资源后续删除导致历史对话无法解释，消息至少保存规范 display name 和必要安全摘要。
- 本 Sprint 优先在现有 `resource_refs_json` 中保存受控结构；没有真实查询需求前不拆通用 resource_ref 表。

### 4. Same-task continuation routing

Runtime 根据解析结果路由：

- 无 Task + 有 Style：进入 `idea-to-comic` 新任务 Skill。
- 有 Task：加载任务上下文，进入“继续讨论/准备修改”语义，不创建新 GenerationTask。
- 无资源：普通创作讨论，不创建图片任务。

本 Sprint 对已有任务只能：

- 回答当前任务/Panel/版本的状态与摘要。
- 生成修改建议或修改方案 Artifact。
- 等待 Sprint 116 的写操作。

如果用户明确要求“重新生成/恢复/接受”：

- Agent 必须说明该能力尚未在当前 Sprint 开放。
- 不得调用旧 Task edit API 作为隐藏兜底。

### 5. Character context

- 新任务可引用当前用户最多 3 个现有 Character。
- Runtime 读取角色名称、描述和参考图 asset ID，加入计划上下文。
- 创建 Task 时复用现有固定角色快照/人物参考基础设施。
- 不允许模型按角色名字自行搜索。
- 若当前 `idea-to-comic` 生图链路尚不能安全传递角色参考图，本 Sprint 必须在实现前评审；不得只展示 `@角色` 标签却不让其影响真实生成。

### 6. Frontend resource menu

- `@` 菜单按风格、角色、任务分组。
- 搜索走后端有界 API，提供 loading/empty/error。
- 选中 Task 后，检查器和资源菜单允许继续选 Panel/图片版本。
- 标签可移除，多个标签不覆盖输入草稿。
- 不允许不合法组合；禁用时解释原因。
- 任务卡和检查器开放“在对话中引用”。
- 引用 Panel 时自动携带父 Task；引用 Image Version 时自动携带 Task + Panel。
- URL、会话草稿和选择状态切换后保持一致。

## Database and migration

默认不新增数据库表：

- `agent_messages.resource_refs_json` 继续保存规范 refs 和安全摘要。
- Task/Panel/Image Version 使用现有关系。
- Character/Style 使用现有资产与快照基础设施。

如果发现 JSON 无法保证必要完整性，必须用真实失败案例更新合同后再设计 migration，不能提前创建通用多态资源表。

## Out of scope

- Panel 再生成、接受版本、恢复版本。
- `inspect_image` 和 VL 自动修改。
- 任务暂停/继续。
- 用户 Memory 或用户自定义 Skill。
- 参考漫画/抖音内容提取资源。
- TTS、Remotion、抠图。
- 全局资源搜索 Tool；资源由用户显式选择。

## Deliverables

- 有界 Resource query API。
- Resource Resolver、组合校验和安全上下文。
- 多资源消息持久化与模型重放。
- 新任务/续作/普通讨论路由。
- 真实角色上下文进入新任务生成。
- 前端多类型资源菜单、标签和检查器引用。
- 权限、父子关系、重放和浏览器测试。

## Recommended implementation order

1. 定义组合矩阵和 resolver 单测。
2. 实现有界查询 API 与权限测试。
3. 扩展消息保存和 `build_agent_input()`。
4. 实现新任务/续作/讨论路由。
5. 接入真实 Character 快照与生图参考。
6. 扩展前端菜单与检查器引用。
7. 用新任务角色引用和历史任务引用各跑一条真实链路。

## Done means

1. 用户可以真实搜索并引用 Style、Character、Task、Panel、Image Version。
2. 后端拒绝跨用户、伪造和父子关系错误的引用。
3. 引用 Panel/Image Version 时模型收到正确结构化上下文。
4. 引用已有 Task 不创建新的 GenerationTask。
5. 新任务引用 Character 后，Task 角色快照和图片参考链路真实生效。
6. 从检查器引用对象不会覆盖草稿，刷新和会话切换后可恢复。
7. 未实现写操作不展示成可用按钮，也不调用旧编辑接口兜底。
8. 资源列表有界，不发生 N+1 初始详情请求。

## Verification

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest \
  backend.tests.test_agent_conversations \
  backend.tests.test_agent_comic_creation
backend/.venv/bin/python -m compileall backend/app
npm run build --prefix frontend
git diff --check
./scripts/check.sh
```

新增测试至少覆盖：

- 每一种资源的 owner/status 校验。
- Task → Panel → Image Version 父子关系。
- 组合矩阵。
- 规范 display name 覆盖客户端伪造值。
- build_agent_input 包含资源上下文。
- 引用 Task 不创建新任务。
- Character 参考图进入 Task snapshot 和 image request。
- 列表 limit、搜索和 summary payload。

### Browser regression

1. `@风格 + @角色` 创建新任务并真实生成。
2. 从历史任务检查器引用 Task/Panel/Image Version。
3. 切换 Conversation 后恢复各自草稿和标签。
4. 尝试不合法组合并看到明确解释。
5. 引用已有任务继续讨论，确认没有新增 Task。

## Handoff

- Sprint 115 Complete 后才能激活 Sprint 116。
- 下一阶段将在这些稳定引用之上增加版本写操作和 VL，不重新设计引用格式。
- 参考漫画、抖音和其它媒体资源仍留到漫画 V1 内部开放之后。

## New-window start prompt

> 请实施 Sprint 115。先完整阅读项目基线、路线图、`docs/contracts/sprint-115-agent-structured-resource-context.md`、当前 Agent schema/API/Runner、任务/角色/风格模型与前后端/数据库/UI 规范。按合同实现有界真实资源查询、统一 resolver、组合/权限/父子校验、资源上下文重放、新任务与同一任务续作路由，以及真实前端 `@` 菜单。正式 UI 不得展示未接通写操作；引用 Task 不得创建新 Task；`@角色` 必须真实进入生成参考链路。不要实现 VL、版本修改、Memory、TTS 或 Remotion。完成自动化、真实浏览器和 Provider 验收后更新文档并创建中文详细 commit。
