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
