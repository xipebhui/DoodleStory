# Sprint 148：显式 Follow-up Run

## Status

Completed。承接 Sprint 147 的统一控制与恢复闭环。本 Sprint 只实现从成功终态 Run 显式创建隔离的
Follow-up Run；受控 Probe 和 Artifact 采纳留给 Sprint 149。

## Goal

用户可以在同一聊天中明确选择一个已成功 Run，基于其固定 Checkpoint、最终输出和已确认产物提出
新目标。后端创建新的 Run、Workflow、Task 与 Attempt，继承父 Run 已固定的 Skill Version、Style
和账号上下文，但不恢复或覆盖父 Run，也不靠“继续”自然语言猜测来源。

## In Scope

### 1. Follow-up 关系与不可变上下文

- `NativeAgentRun` 增加 `parent_run_id`、`continued_from_checkpoint_id`、Follow-up 创建幂等键、请求
  hash 和只读 continuation context snapshot。
- 父 Run 必须属于同一 owner/Conversation、状态为 `succeeded`，并拥有 Durable Workflow 当前
  Checkpoint；failed/cancelled Run 必须使用 Sprint 147 的恢复/重试，而不是 Follow-up。
- snapshot 只引用父 Run ID、Checkpoint ID/hash、最终输出和父 Run 已批准或完成的 Artifact
  ID/type/version/hash/content；超过明确大小上限时请求失败，不静默裁剪。
- 父 Run 和父 Artifact 不被修改；子 Run 使用新的 Workflow、Task、Attempt、Checkpoint、事件序列
  和 Tool Effect。

### 2. Owner-scoped 幂等 API

- 新增 `POST /agent-loop/runs/{parent_run_id}/follow-ups`，请求包含新目标和客户端
  `idempotency_key`。
- 相同 owner、parent、key 与相同 payload 返回同一子 Run；同 key 不同 payload 返回 409。
- Follow-up 固定继承父 Run 的 Skill Version、Style 快照、创作账号 Context 以及发布频道/视频的
  只读引用；父 Run 的发布确认和确认时间不继承，第一版也不允许在 Follow-up 创建请求中替换资源。
- 同一 Conversation 存在 active Run 时拒绝创建；成功创建后通过现有 in-process Worker 入队。

### 3. Runtime 注入与终态语义

- 普通 Agent 和多 Agent 文案角色都收到 `<follow_up_context>`，明确区分父 Run 事实与本轮新目标。
- Follow-up 是新目标，不复用父 SDK Session，不重放父 Attempt，也不把父成功 Tool Step 当作当前
  Run 已执行；只有模型在新目标下明确调用 Tool 时才产生新副作用。
- 文案 Skill 为子 Run 初始化新的 ARTICLE_TASKS；非文案 Skill 初始化空 Durable Workflow。两者都
  使用父产物作为只读输入，而不是覆盖父产物。
- Run Projection 和 SSE 返回 parent/checkpoint 元数据，刷新后保持关联。

### 4. 聊天交互

- 成功终态 Run 展示“基于此结果继续”；点击后在原输入区显示父 Run、Skill/Style 固定提示和取消
  入口，不打开工作流编辑器或内部 Checkpoint 选择器。
- Follow-up 模式保留用户输入；提交时显示 busy 并阻止重复请求，失败后保留文本与父 Run 选择。
- 子 Run 卡片显示“续接自上一结果”，可定位父 Run；active、失败、取消或仍等待 Gate 的 Run 不展示
  Follow-up 操作。

## Out of Scope

- `create_probe`、Probe 的只读 Tool 预算、Probe Artifact 和主线采纳。
- 从 failed/cancelled/waiting Run 创建 Follow-up；这些继续走 retry/resume/resolve 命令。
- 跨 Conversation、跨 owner、跨 Skill Version 续接。
- 多级分支树可视化、合并两个父 Run、修改父 Artifact、自动发布或新的媒体 Provider。
- Deferred Evaluation 与内部发布结论。

## Deliverables

- Follow-up Run 字段、约束和 Alembic migration。
- continuation snapshot 服务、幂等 owner-scoped API、Runtime instructions 注入和 Projection/SSE 字段。
- 聊天 Follow-up 选择、提交、取消、父子关联展示和错误状态。
- API/Runtime/前端回归、浏览器验收、进度与 QA 文档。

## Done Means

- 用户从成功 Run 显式创建 Follow-up 后得到同 Conversation 的新 Run；父 Run 与父 Workflow 所有
  状态、Artifact、Attempt 和 Effect 均未改变。
- 子 Run 固定继承父 Skill/Style/账号上下文，并能在模型 instructions 中读取带 hash 的父终态产物。
- 刷新或 SSE 重连后父子关系仍存在；重复提交返回同一子 Run，过期/越权/active/非成功父 Run
  明确失败。
- 文案和非文案 Follow-up 均建立独立 Durable Workflow；取消或失败子 Run 不影响父 Run。
- 页面只对成功 Run提供 Follow-up，输入失败不丢失，控制台无新增 error/warning。

## Verification

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest \
  backend.tests.test_native_agent_follow_up \
  backend.tests.test_native_agent_loop \
  backend.tests.test_durable_agent_runtime
npm --prefix frontend test
npm --prefix frontend run build
./scripts/check.sh
git diff --check
```

Browser QA：

- 使用无费用 fixture 完成成功父 Run → 选择 Follow-up → 输入新目标 → 创建子 Run。
- 刷新验证父子标签、固定 Skill/Style 提示和子 Run 状态；验证 active/failed Run 没有 Follow-up 按钮。
- 验证重复提交、取消 Follow-up 模式、API 错误后保留输入；Console 0 error / 0 warning。

## Risks / Notes

- continuation snapshot 进入模型上下文，必须有明确 schema 和大小上限；不允许静默截断。
- 继承发布资源不等于继承发布授权；Follow-up 清除父 Run 的发布确认，不能调用发布 Tool。
- 多级 Follow-up 允许形成线性 parent 链，但本 Sprint 不加载整条祖先链，只注入直接父 Run snapshot。

## Handoff

Sprint 149 实现受控 Probe：从固定 Checkpoint 创建只读、有限模型预算、无副作用 Tool 的隔离分支，
保存 Probe Artifact，并由显式采纳命令生成新的主线 Plan Revision。
