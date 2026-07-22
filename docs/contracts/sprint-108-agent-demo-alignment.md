# Sprint 108：正式 Agent 前端与已调试 Demo 对齐

## Status

Complete（2026-07-22）。正式界面对齐、真实两格链路和指定桌面视口验收均已完成。

## Goal

保留 Sprint 107 已接通的一套正式产品外壳、稳定路由和真实 Conversation、Message、Run、Style、TaskCard 数据，把 `/agent` 内部工作区的结构、视觉层级和已支持交互对齐 Sprint 103 已调试 Demo。此 Sprint 是纯前端整合，不修改 Agent Runtime、数据库或后端业务模型。

## Design direction

- 视觉主张：在现有 DoodleStory 外壳中嵌入安静、平面、全高的 AI 创作工作区，用留白、排版和单一橙色表达行动与状态，移除大圆角后台卡片感。
- 内容计划：全局 Shell 和顶部构建模式保持不变；AI 区域依次由会话列表、当前对话、空白入口或真实消息、真实任务卡片、固定底部输入区组成。
- 交互主张：会话与检查区域采用克制的布局过渡；资源选择按需展开并可搜索；运行状态在原位更新，避免装饰性动效和布局跳动。

## In scope

- 保留现有全局侧边栏、账号、积分、图文任务、风格、角色等正式入口，以及 `/tasks`、`/agent`、`/agent/{conversation_id}`、`/tasks/{task_id}` 路由。
- 保留真实 Conversation、Message、Run、Style、Agent TaskCard API，以及 Agent 任务和同一个 `generation_tasks` 记录的关系。
- 移除 `/agent` 内部大圆角边框工作区和通用后台聊天页结构，把 Demo 的局部会话导航、对话区和固定输入区迁入 AI 构建区域，不复制 Demo 的品牌和账号外壳。
- 会话列表提供新对话、搜索、日期分组、标题、真实摘要、状态和更新时间。
- 空白对话展示“今天想创作什么？”、简短说明、三个只填入输入框而不提交的快捷入口，以及少量真实常用风格。
- 输入区保留 `+` 和 `@` 资源入口；第一版只展示后端真实 active 风格，支持搜索、选择和移除。
- 每个 Conversation 独立保存未发送草稿和已选风格；切换会话后恢复，资源引用不能覆盖已有输入。
- 对话消息、Run 状态和任务卡片继续读取真实数据；任务卡视觉以图片和创作状态优先，技术 ID 降为次级信息，并保留进入同一正式任务详情的入口。
- 只有现有接口已经返回真实 Panel 或图片数据时，才允许实现只读、按需展开查看；不显示没有真实数据支持的操作。
- 完成 1440×900、1280×800、键盘焦点、响应式、加载/运行/等待/失败/完成状态和控制台检查。

## Out of scope

- 不修改 Agent Runtime、后端 API、数据库表或任务业务模型。
- 不展示或伪造角色引用、Panel 重新生成、Panel 版本恢复、接受版本、引用 Panel 后修改、暂停/恢复任务、VL 检查或 Agent 自动修改循环。
- 不实现用户 Memory、自定义 Skill、视频、Remotion、TTS、旧 Pipeline 迁移或通用资源平台。
- 不复制 Demo 的 DoodleStory Logo、Agent Studio、第二套账号区域、Mock 会话、Mock 状态、Mock 图片或 Panel 结果。
- 不添加兜底、占位成功结果、静默错误处理或兼容性回退。

## Done means

1. 正式产品仍只有一套全局 Shell 和顶部 `传统构建 / AI 构建` 切换，`/tasks` 与 `/agent` 往返、刷新和直接访问稳定。
2. `/agent` 内部呈现 Demo 已确认的平面全高结构，不再是大圆角后台聊天卡片；会话列表、空白入口、真实消息和固定输入区层级清晰。
3. 三个快捷入口只填写草稿；`+` 与 `@` 只选择真实 active 风格，支持搜索、添加和移除，不出现角色或其它假资源。
4. 切换 Conversation 后分别恢复其草稿与风格；引用资源不覆盖已有输入。
5. 真实消息、Run 状态、任务图片和 TaskCard 正常恢复；卡片可进入同一个 `/tasks/{task_id}`，没有 Mock 数据或未接通操作。
6. 1440×900 和 1280×800 的真实浏览器验收可用，关键控件可键盘访问，认证后控制台无新增 error。
7. 前端生产构建、`git diff --check` 和 `./scripts/check.sh` 通过，进度和浏览器证据已记录。

## Verification

### Automated

```bash
npm run build --prefix frontend
git diff --check
./scripts/check.sh
```

### Browser regression

在 1440×900 和 1280×800 真实浏览器覆盖：新建空白对话；三个快捷入口；`+` 选择真实风格；`@` 搜索真实风格；移除风格；历史会话切换及独立草稿/风格恢复；一次真实 Agent 创作；运行态、完成任务卡和真实图片；从卡片进入同一传统任务详情；传统/AI 模式往返；页面刷新；键盘焦点与控制台。

真实模型或图片 Provider 如果因外部状态无法完成，不得改用 Mock 或占位结果；记录阻塞与已有真实证据。

## Handoff

- 完成后将本合同标记 Complete，并同步 `docs/progress.md` 与 Agent V1 路线图。
- 下一阶段是 Sprint 109 Draft：`docs/contracts/sprint-109-agent-panel-iteration-vl-draft.md`。
- Sprint 109 评审前不得提前实现 Panel 版本操作、任务暂停或 VL。

## Assumptions reviewed

- Sprint 107 的正式 Shell、稳定 URL、真实 API 和 GenerationTask 关联已经通过真实浏览器验收，本 Sprint 不重做数据链路。
- 当前 Agent 只支持一个真实风格引用；角色与其它资源不显示为可选项。
- Demo 是 `/agent` 内部视觉与交互事实来源，但其外层品牌、Mock 数据和未接通能力不是生产需求。

## Completion record

- `/agent` 内部已改为平面、全高的三段结构：真实会话列表、当前对话工作区和固定底部输入区；移除大圆角工作区与通用后台聊天页外观，正式产品 Shell 和顶部模式切换保持不变。
- 会话列表按日期分组并展示真实消息摘要、Run 状态和更新时间；最多为最近 12 个会话补充真实详情元数据，失败会显示明确错误，不伪造状态。
- 空白页三个快捷入口只填写草稿；`+` 与输入 `@` 打开仅含真实 active 风格的可搜索资源菜单，风格可选择和移除且不会覆盖输入。
- Conversation 的未发送草稿和风格按会话保存在浏览器 session；运行期间允许继续准备草稿但锁定提交。传统/AI 模式切换会回到最近 Conversation，刷新、会话往返和模式往返均恢复草稿与风格。
- 真实 Conversation `3aa7454244754acda99f9475433195e5`、Run `e89097e4d0294e01b27e40dd7f2f71bb` 和 Task `c59151ece9a34b47a32042aeafcfbc04` 使用真实风格 `粗线条暖色` 成功生成两个图片版本 `22dec874850045ed906428471781f1a8`、`8538ef7bd44f4291adae88738fc9caef`，积分从 30 降到 28。
- Agent 卡片、传统任务列表与正式任务详情确认引用同一 Task；卡片以真实图片和状态为主，任务 ID 降为次级信息，没有加入角色、Panel 操作、暂停、VL、Mock 或占位能力。
- 1440×900、1280×800、快捷入口、资源搜索/移除、独立草稿/风格、运行态、完成态、任务详情、模式往返、刷新和键盘焦点均已验收；认证后的新页面控制台 0 error / 0 warning。证据保存于 `docs/testing/agent-demo-alignment-browser-report.json`。
- `npm run build --prefix frontend`、`git diff --check` 和 `./scripts/check.sh` 通过；全量检查覆盖 196 个后端测试、空库 Alembic migration 和前端生产构建。
