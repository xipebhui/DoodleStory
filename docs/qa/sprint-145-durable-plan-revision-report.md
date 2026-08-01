# Sprint 145：Durable 后端计划修订 QA 报告

## 范围

本 Sprint 只实现后端的不可变计划修订、局部失效/重试、lease 恢复和受控补充研究分支。现有
`Simple Agent Loop` 页面、Skill 管理、账号管理、`@` 资源交互和 `/agent-loop` 前端请求形状
保持不变。

## 数据库迁移副本

- 迁移链：`o6p7q8r9s0t1 → p7q8r9s0t1u2 → q8r9s0t1u2v3`。
- 新增：`agent_durable_plan_revisions`。
- 保留数据：34 用户、21 Style、18 频道、82 条传统 `generation_tasks`。

## 后端行为

- Workflow 初始化、Task 产物完成、Gate 打开、Gate 批准/修改、lease 过期恢复均追加不可变
  Plan Revision。
- 计划版本保存 Task key、标题、状态、依赖、输入 Artifact、输出 Artifact、来源 Checkpoint 和
  触发原因。
- 选题批准后后续计划显示正文 Task ready；正文修改仅失效正文及下游 Review，已批准选题保持有效。
- Review 明确要求“补充研究”时，仅允许追加一次 `supplement_research`；不允许任意 Task 类型、
  环状依赖或覆盖终态 Task。
- 只读计划接口：`GET /api/v1/agent-loop/runs/{run_id}/plan-revisions`，按 Conversation owner
  隔离。

## 页面回归

- 隔离服务打开原 Agent 页面，确认仍显示 `Simple Agent Loop`、`Skill 管理`、`返回传统工作台`
  和 `@` 资源入口。
- `@` 菜单中的 Style 资源列表、搜索框和现有输入区均保持原交互。
- 本 Sprint 未修改 `frontend/src`。

## 真实文本验证

- 隔离库：`/private/tmp/doodlestory-s145-real.Vw1oG0/runtime.sqlite`。
- 真实 Run：`802937baf304454199b5f6c9df0e13cb`。
- 输入：`请只生成 3 个关于内容创作的候选选题，等待我选择，不要写正文。`
- 只引用 `文案创作团队 · v1`，未选择 Style、图片、语音、字幕或视频资源。
- 真实调用结果：
  - `model_call_count=6`；
  - `image_call_count=0`；
  - `speech_call_count=0`；
  - `subtitle_call_count=0`；
  - `video_call_count=0`。
- Durable Trace：
  1. `research_topics` initial Attempt 成功；
  2. Checkpoint 2 保存候选选题 Artifact；
  3. `topic_selection_gate` 等待用户确认；
  4. 用户确认后，同一 Run 写入 Checkpoint 4 `topic_selection approved`；
  5. `write_draft` initial Attempt 创建并运行，没有重新生成候选选题，也没有创建新 Run。
- 正文阶段实际模型输入包含已批准选题和“只能写正文、不得重新选题/Review/媒体计划”的约束。
  在正文模型返回前主动取消隔离 Run，以避免继续消耗文本调用。
- 真实验证发现并修复两个兼容缺陷：
  - 现有 SSE artifact schema 未包含 `topic_candidates`；
  - 选题确认 adapter 缺少 `NativeAgentContextItem` 导入。
  修复后候选选题审批可正常恢复并推进正文阶段。

## 自动验证

```text
PYTHONPATH=backend backend/.venv/bin/python -m unittest \
  backend.tests.test_durable_agent_runtime \
  backend.tests.test_native_article_workflow \
  backend.tests.test_native_agent_loop
./scripts/check.sh
git diff --check
```

结果：全部通过。完整检查覆盖 346 项后端测试、14 项前端测试、前端生产构建、Remotion 类型检查和
模板测试。
