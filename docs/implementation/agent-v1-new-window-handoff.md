# Agent V1 新窗口实施交接

> 状态更新（2026-07-22）：Sprint 105、106、107、108 已 Complete。当前没有 Active Sprint；Panel/VL 合同已顺延为 `docs/contracts/sprint-109-agent-panel-iteration-vl-draft.md`，仍为 Draft，评审前不得实施。

## 1. 新窗口目标

新窗口只实现 Sprint 108：保留 Sprint 107 已接通的统一正式工作台和真实 Agent 数据，把 `/agent` 内部工作区对齐 Sprint 103 已调试 Demo。

本次不扩展 Agent 后端能力。完成后用户应能在一套全局侧边栏中，通过顶部 `传统构建 / AI 构建` 切换 `/tasks` 和 `/agent`，并从 Agent 任务卡片打开同一个 `/tasks/{task_id}` 任务详情。

## 2. 仓库与分支

```bash
cd /Users/pengfei.shi/workspace/tmp-project/DoodleStory
git branch --show-current
git status --short
```

预期分支：`codex/agent-feature`。

当前以下未跟踪内容属于用户或其它工作，不得加入 Sprint 108 提交、删除或覆盖：

- `.agents/skills/koubo/`
- `content-lab/self-media-scripts/`
- `docs/api_v3.md`
- `docs/api_v4.md`
- `logs/`
- `output/`

如果开始时工作树出现其它已跟踪修改，先确认来源，不得覆盖用户改动。

## 3. 主 Agent 必读顺序

主 Agent 必须自己完整阅读，不能只让子 Agent 总结：

1. `AGENTS.md`
2. `README.md`
3. `docs/spec.md`
4. `docs/progress.md`
5. `docs/implementation/agent-v1-implementation-roadmap.md`
6. `docs/contracts/sprint-108-agent-demo-alignment.md`
7. `docs/contracts/sprint-107-agent-frontend-workspace-integration.md`
8. `docs/contracts/sprint-103-agent-conversation-demo.md`
9. `docs/design/agent-conversation-demo/README.md`
10. `docs/design/agent-conversation-demo/index.html`
11. `docs/design/agent-conversation-demo/styles.css`
12. `docs/design/agent-conversation-demo/app.js`
13. `docs/standards/frontend.md`
14. `docs/standards/ui-interaction.md`

随后检查真实实现，不要仅根据 Demo 猜正式代码：

- `frontend/src/main.tsx`
- `frontend/src/styles/app.css`
- `frontend/src/api/client.ts`
- `backend/app/schemas/agent.py`
- `backend/app/api/agent.py`

如实际文件结构不同，使用 `rg --files frontend backend/app` 确认，不创建重复模块。

## 4. 可直接粘贴到新窗口的启动提示词

> Sprint 108 已按以下范围完成：保留 Sprint 107 的全局 Shell、稳定路由和真实 Conversation、Message、Run、Style、TaskCard 数据，把 `/agent` 内部工作区对齐 Sprint 103 已调试 Demo；未复制 Demo 品牌、账号、Mock 数据、角色、Panel 操作、版本、暂停或 VL。复现范围与证据见 `docs/contracts/sprint-108-agent-demo-alignment.md` 和 `docs/testing/agent-demo-alignment-browser-report.json`。

## 5. 推荐实施顺序

### 5.1 现状确认

1. 确认 `/tasks`、`/tasks/{task_id}`、`/agent`、`/agent/{conversation_id}` 的现有路由行为。
2. 确认正式 Agent 页和独立 Demo 的代码边界；Demo 只作视觉与交互参考。
3. 确认 Agent Task Card 已提供真实 `task_id`，任务列表 API 会返回 Agent 创建的 GenerationTask。
4. 记录当前 1440×900 与 1280×800 截图或布局，避免整合时破坏传统页面。

### 5.2 全局信息架构

1. 从全局一级导航移除独立 `漫画 Agent` 的产品语义。
2. 让 `/tasks` 和 `/agent` 都归属左侧 `图文任务`。
3. 实现共享顶部 `传统构建 / AI 构建` 分段控件。
4. 使用真实导航链接或现有路由方法切换 URL，不使用只能保存在内存的 mode 状态。

### 5.3 AI 工作区整合

1. 保留 Agent 会话历史作为 AI 模式内部侧栏。
2. 移除 Demo 风格的第二套品牌和全站导航。
3. 接入真实新建会话、历史切换、详情、消息提交和轮询。
4. 只保留当前真实可用的一个风格引用；隐藏未接通的角色、Panel 和版本操作。
5. 完成空白、加载、运行、失败和完成状态，保留输入草稿。

### 5.4 共享任务验证

1. 从 Agent 任务卡片导航到 `/tasks/{task_id}`。
2. 在传统任务列表找到同一 task ID。
3. 不复制任务数据，不新增 Agent 专用任务表或任务详情。
4. 检查浏览器后退、前进和刷新后模式、会话与任务 URL 正确。

### 5.5 收尾

1. 只做实现所需的小组件拆分，不顺手全量重构 `main.tsx`。
2. 运行合同全部 Verification。
3. 把真实实现、浏览器验收、未验证内容和下一步写入 `docs/progress.md`。
4. Sprint 108 全部 Done means 满足后，将合同标记 Complete、路线图阶段 4 标记已完成；Sprint 109 仍保持 Draft，不能自动开始。
5. 创建符合仓库规范的详细中文 commit。

## 6. 验收重点

- 正式产品只剩一套全局 Shell，不出现“双侧边栏代表两个产品”的混乱。
- `传统构建 / AI 构建` 在两个页面位置和语义一致，选中状态由 URL 决定。
- 正式 Agent 页无 Demo 假数据、Mock 图片或未实现的角色/Panel 操作。
- 真实会话可新建、切换、刷新和重新打开。
- 真实风格选择和 Sprint 106 两格生成链路没有回归。
- Agent 任务卡与传统任务详情使用同一个 task ID。
- 传统任务创建、列表、筛选、详情及其它主导航页面无回归。
- 1440×900 与 1280×800 可用，键盘焦点清晰，控制台 0 error。

## 7. 明确延后

以下内容不需要在当前架构中提前实现“开放入口”：

- 用户维度 Memory、创作习惯和规则。
- 自定义 Skill 或通用 Tool 平台。
- 抠图、Remotion、文字转语音和视频解说。
- 固定角色及其它资源引用。
- Panel 修改、版本恢复和 VL。

等漫画 Agent V1 的当前路线完成并有真实使用反馈后，再为这些能力单独讨论产品与合同。
