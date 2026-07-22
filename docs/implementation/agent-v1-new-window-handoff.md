# Agent V1 新窗口实施交接

> 状态更新（2026-07-22）：本文中的“第二阶段启动提示词”已执行完成，Sprint 106 已 Complete。当前没有 Active Sprint；阶段 3 只有 `docs/contracts/sprint-107-agent-panel-iteration-vl-draft.md`，评审激活前不得实施 VL 或 Panel 迭代。

## 1. 是否应该换新窗口

推荐换新窗口，并继续使用当前仓库与分支 `codex/agent-feature`。

原因不是旧窗口不能继续，而是需求发现、架构讨论和平台验证已经形成完整仓库文档。新窗口能把注意力集中在当前 Sprint；只要严格读取本交接包，历史聊天不再是事实来源。

不要为新窗口再创建一条并行 Agent 实现分支。开始前先确认：

```bash
pwd
git branch --show-current
git status --short
```

预期仓库：`/Users/pengfei.shi/workspace/tmp-project/DoodleStory`。

预期分支：`codex/agent-feature`。

当前以下未跟踪内容属于用户或其它工作，不得加入 Agent 提交、删除或覆盖：

- `.agents/skills/koubo/`
- `content-lab/self-media-scripts/`
- `docs/api_v3.md`
- `docs/api_v4.md`
- `logs/`
- `output/`

## 2. 新窗口必读顺序

主 Agent 必须自己完整阅读，不能只让子 Agent 总结：

1. `AGENTS.md`
2. `README.md`
3. `docs/spec.md`
4. `docs/progress.md`
5. `docs/implementation/agent-v1-implementation-roadmap.md`
6. `docs/contracts/sprint-105-agent-runtime-foundation.md`
7. `docs/product/agent-v1-prd.md`
8. `docs/design/agent-runtime-architecture.md`
9. `docs/design/agent-tool-contracts.md`
10. `docs/testing/agent-model-provider-compatibility-report.md`
11. `docs/evals/agent-v1-evaluation-plan.md`
12. `docs/standards/python.md`
13. `docs/standards/database.md`
14. `docs/standards/backend-workflows.md`

开始正式前端实现的 Sprint 106 时，再额外完整阅读：

- `docs/contracts/sprint-106-agent-comic-creation-vertical-slice-draft.md`
- `docs/contracts/sprint-103-agent-conversation-demo.md`
- `docs/design/agent-conversation-demo/README.md`
- `docs/standards/frontend.md`
- `docs/standards/ui-interaction.md`

## 3. 第一阶段启动提示词

可以把下面内容原样发给新窗口：

> 在 `/Users/pengfei.shi/workspace/tmp-project/DoodleStory` 的 `codex/agent-feature` 分支继续 Agent V1。先完整读取根目录 `AGENTS.md`、`README.md`、`docs/spec.md`、`docs/progress.md`、`docs/implementation/agent-v1-implementation-roadmap.md`、当前合同 `docs/contracts/sprint-105-agent-runtime-foundation.md`，以及合同引用的 Agent 设计、兼容性、Evaluation、Python、数据库和后台工作流标准。只实现 Sprint 105，不提前做 Sprint 106 的 ComicPlan、生图 Tool 或前端。先用真实火苗和 LIO `gpt-5.6-terra` 完成 OpenAI Agents SDK Responses Tool Loop 探测；通过后再实现四张 Agent 表、最小 Conversation/Message/Run API、进程内 Runner、应用侧上下文和火苗到 LIO 路由。保持现有生产生成 Pipeline 不变，运行合同全部验证，更新路线图和进度，并按仓库规范创建详细中文 commit。不要触碰交接文档列出的用户未跟踪文件。

## 4. 第一阶段推荐执行顺序

### 4.1 决策门

1. 检查当前 `backend/requirements.txt` 和 OpenAI client 使用点。
2. 选择并锁定 Agents SDK 版本，不使用浮动依赖。
3. 编写 SDK 兼容性脚本和离线测试。
4. 分别真实测试火苗、LIO 的 Responses Function Call → Tool Output → final response。
5. 两边均通过才继续；任一失败必须更新合同并报告，不静默改用另一 API shape。

### 4.2 Runtime 实现

1. 设计一条 Alembic migration，只创建合同中的四张表。
2. 增加 SQLAlchemy models、Pydantic schemas 和有界列表/详情 API。
3. 实现 Agent 专用配置，复用两个平台的 base URL/key，但使用统一 `gpt-5.6-terra`。
4. 实现单 Agent、应用侧消息重放和最小 Router。
5. 接入进程内 `run_id` 队列、step checkpoint 和启动恢复。
6. 增加权限、fallback、永久错误、重复执行和恢复测试。
7. 运行真实两轮对话 smoke test。

### 4.3 第一阶段验证与收尾

- 执行 Sprint 105 的全部 Verification。
- 检查 migration 可从空库升级。
- 检查日志、报告、API 和 git diff 不含 API key。
- 更新 `docs/progress.md`、路线图阶段状态和任何实际变化的契约。
- 记录真实 SDK 报告路径、Provider/model/API shape 和 smoke IDs。
- 创建详细中文 commit。
- 只有 Done means 全部满足，才把 Sprint 106 Draft 改为 Active。

## 5. 第二阶段启动提示词

Sprint 105 完成后，可以在同一实现窗口继续，也可以再次开新窗口。若开新窗口，使用：

> 继续 `/Users/pengfei.shi/workspace/tmp-project/DoodleStory` 的 Agent V1。先读取 `AGENTS.md`、`README.md`、`docs/spec.md`、`docs/progress.md`、全局路线图、已完成的 Sprint 105 合同和进度记录，再读取并评审 `docs/contracts/sprint-106-agent-comic-creation-vertical-slice-draft.md`、Agent PRD/Runtime/Tool 设计、Sprint 103 Demo 说明以及前端、UI、数据库、后台工作流标准。确认 Sprint 105 的 SDK、Router、migration、API 和恢复验证全部通过后，把 Sprint 106 Draft 更新为 Active，只实现“Idea + 一个 @风格 → 两格 ComicPlan → 两次真实 generate_image → 对话任务卡片”的纵向链路。不实现 VL、Panel 重试、角色、抖音、画布或旧 Pipeline 迁移。使用真实模型和真实图片 Provider 验收，运行全量检查，更新路线图/进度，并创建详细中文 commit。

## 6. 第二阶段开发与验证重点

### 开发重点

- 前端行为以 Sprint 103 Demo 为参考，不能把 Demo 假数据带入正式代码。
- 资源选择提交稳定 style ID；后端负责权限和快照。
- Agent 输出 ComicPlan，Runtime 只校验和保存，不重新创作。
- `generate_image` 复用低层图片 job、资产和积分，不调用旧故事/Prompt Pipeline。
- Run 等待图片 job 时 checkpoint，Tool Output 持久化后再继续模型。

### 验证重点

- 真实 Idea、真实风格、真实模型、真实图片 Provider，不能用占位图完成验收。
- 两格剧情连续，Prompt 简洁且未混入旧 Pipeline 多层模板。
- 重复 Tool Call 不重复生图/扣费。
- 跨用户 style ID 被拒绝。
- 图片失败、积分不足、刷新和服务重启状态正确。
- 浏览器实际走完创建、生成、刷新恢复，控制台无错误。

## 7. 何时留在同一窗口，何时再换

- 同一个 Sprint 内尽量留在同一窗口，避免实现中途重新建立局部上下文。
- 一个 Sprint 完成、验证、更新文档并 commit 后，是最适合换窗口的边界。
- 不要在阶段中途因为上下文变长而重新解释需求；先把新发现写回合同/进度，再换窗口。
- 如果实现与合同发生冲突，先停下来修改合同并说明原因，不让聊天中的临时决定覆盖仓库事实。
