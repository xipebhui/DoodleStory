# Sprint 106：对话创建两格真实漫画

## Status

Complete（2026-07-22）。Sprint 105 的 Runtime 契约保持不变；本 Sprint 已完成真实模型、真实图片 Provider、浏览器刷新恢复和全量回归验收。

## Goal

基于已验证的 Agent Runtime，实现第一条真实产品纵向链路：用户在 Agent 页面新建或继续对话，输入漫画 Idea 并选择一个已授权 `@风格`，ComicDirectorAgent 自主输出两格 ComicPlan、调用真实 `generate_image` Tool，并在对话中展示可恢复的任务卡片和真实图片。

## In scope

- 把 Sprint 103 会话 Demo 的新建、历史列表、继续对话、发送消息和任务卡片行为接入真实后端；不复制 Demo 假数据。
- 支持输入区选择一个 `@风格`，前端提交稳定资源 ID，后端校验归属/可见性并保存名称与配置快照。
- 定义最小两格 `ComicPlan` schema；Agent 决定标题、连续 story beat、画面目标和简洁单图 Prompt。
- Runtime 校验完整 ComicPlan 后，复用现有 GenerationTask、Panel 和风格快照作为业务事实，不调用旧故事拆分或最终 Prompt 编译 Pipeline。
- 实现唯一生产 Tool `generate_image`，复用现有图片 Provider、资产、图片 job 和积分基础设施。
- Tool Call 先写 Step 和幂等键，再创建图片 job；图片完成后保存 Tool Output 并恢复 Agent Run。
- 对话展示应用级进度、真实任务状态和两张图片；使用有界轮询，不实现 Token 流。
- 只支持 Idea + 一个风格 + 固定两格，先验证端到端架构和生成质量。

## Out of scope

- 不实现 `inspect_image`、Agent 自动质量检查或自动重试。
- 不实现用户指定 Panel 修改、重试、版本恢复。
- 不支持固定角色、临时角色参考、最后一张真人图片。
- 不支持 `@任务/@Panel/@图片版本`、参考漫画改编、抖音输入、知识方案或现有其它入口迁移。
- 不支持任意图片数量、画布编辑、Token 流、多 Agent或外部队列。
- 不删除旧 Pipeline；本 Sprint 只建立并行的 Agent 真实纵向链路。
- 不通过旧的故事拆分、Storyboard planning 或多层 Prompt 拼接伪装成 Agent Tool。

## Done means

1. 用户可以在真实 `/agent` 产品入口新建和继续 Conversation。
2. 用户可以通过资源选择器绑定一个可访问风格；伪造或跨用户资源 ID 被后端拒绝。
3. 一个真实 Idea 产生结构合法、剧情连续的两格 ComicPlan，并原子保存 GenerationTask 和两个 Panel。
4. Agent 为两个 Panel 调用真实 `generate_image`，最终结果保存为现有图片资产和版本，不返回 Mock 或占位图。
5. 图片 Tool 的 Prompt 来自 Agent 当前上下文和 ComicPlan，不经过旧 Pipeline 的创作 Prompt 编译。
6. 相同 Tool Call 重放不创建第二个图片 job、不重复占用或扣除积分。
7. 页面刷新和服务重启后，对话、任务卡片、Panel、图片和 Agent Run 状态可以从数据库恢复。
8. 图片失败、积分不足和 Provider 错误有明确用户状态，Run 不伪造成功。
9. 至少运行 Evaluation 用例 `idea_to_comic_basic` 的两格变体、`mention_style_resource` 和 `duplicate_tool_call_idempotency`。

## Verification

Sprint 105 Runtime 回归基线：

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest \
  backend.tests.test_agent_model_router \
  backend.tests.test_agent_conversations \
  backend.tests.test_agent_runner_recovery

backend/.venv/bin/alembic -c alembic.ini upgrade head
```

Sprint 106 最低验证集合：

- ComicPlan schema、资源权限、任务原子创建和 Prompt 边界单测。
- `generate_image` Tool 幂等、积分、失败、取消/晚到结果边界测试。
- Agent Run 等待图片 job、Tool Output 后恢复和服务重启恢复测试。
- React 生产构建。
- 浏览器在桌面视口完成“新建对话 → 选风格 → 生成两格真实漫画 → 刷新恢复”的真实回归，控制台无错误。
- 使用真实模型和真实图片 Provider 完成至少一次本地 smoke test，记录 Conversation、Run、Task 和两个图片版本 ID。
- `git diff --check` 和 `./scripts/check.sh`。

## Handoff

阶段 3 已由 Sprint 107 完成正式前端整合；当前 Active 合同是 `docs/contracts/sprint-108-agent-demo-alignment.md`，用于把正式 Agent 内部工作区对齐已调试 Demo。原 Panel 修改、版本恢复和 `inspect_image` 合同已顺延为 `docs/contracts/sprint-109-agent-panel-iteration-vl-draft.md`，尚未激活、尚未实现。

## Assumptions to review when activating

- 已确认 Sprint 105 的最终 SDK/API shape、Router 和四张 Agent 表稳定，并已有 190 个后端测试的全量回归基线。
- 已确认当前图片 job 以 `GeneratedImage` 持久化状态并由独立图片 worker 领取；Sprint 106 需要新增受控的 `generate_image` Tool adapter 复用该边界，禁止调用旧任务创作编排。
- 两格固定数量继续作为架构验证限制，不是最终产品限制。

## Completion record

- `/agent` 已接入真实 Conversation、Message、Run 和任务卡片 API；稳定 URL 支持新建、继续、刷新和重新打开对话。
- 本阶段只解析一个 `style` resource ref。当前 `Style` 是全局风格库、没有 owner 字段，因此“可访问”定义为已登录用户可读取 active、未删除的全局风格；伪造、停用或已删除 ID 均由后端拒绝。本 Sprint 未擅自引入风格所有权迁移。
- 严格 `ComicPlan` 固定包含有序且剧情不同的 `panel-1`、`panel-2`。Runtime 原子创建 GenerationTask、两个 Panel、两个 GeneratedImage job，并把 Agent 的单图 `image_prompt` 原样保存为 `final_prompt`，不进入旧故事拆分或最终 Prompt 编译。
- 每个图片 Tool Call 先保存稳定幂等键，再创建图片 job；恢复时复用 `run.task_id`、既有 job 和积分流水。图片到达终态后各写一次 Tool Result，再恢复最终模型回答。
- 真实 HTTP smoke、纯浏览器提交和中断恢复证据保存在 `docs/testing/agent-comic-vertical-slice-smoke-report.json`；三组证据均为真实模型和真实图片 Provider，不包含 Mock 或占位图。
- Evaluation 映射覆盖 `idea_to_comic_basic` 的 Sprint 106 固定两格变体、`mention_style_resource` 和 `duplicate_tool_call_idempotency`。
- 针对性回归 39 个测试通过；`./scripts/check.sh` 通过，覆盖 196 个后端测试、空库 Alembic `upgrade head` 和前端生产构建；`git diff --check` 通过。
- 浏览器完成“登录 → 新建对话 → 选一个风格 → 提交 Idea → 看到两张真实图片 → 新标签恢复 → 强制刷新恢复”，认证后的 Agent 页面控制台 0 error / 0 warning。
- VL、Panel 修改/重试/版本恢复、角色、抖音和旧 Pipeline 迁移均未实现。
