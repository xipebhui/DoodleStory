# Sprint 144：Durable 后端 Runtime QA 报告

## 范围

本 Sprint 仅替换 Agent 的后端任务、审批、恢复和终态控制事实。现有 `Simple Agent Loop`
页面、Skill 管理、账号管理、`@` 资源选择、会话侧栏和 `/agent-loop` 前端请求形状保持不变。

## 数据库迁移副本

- 来源库：Sprint 144 前的本地 `doodlestory.db` 副本。
- 迁移：`o6p7q8r9s0t1 → p7q8r9s0t1u2`。
- 新增 Durable 后端表：7 张。
  - `agent_durable_workflows`
  - `agent_durable_tasks`
  - `agent_durable_attempts`
  - `agent_durable_checkpoints`
  - `agent_durable_artifacts`
  - `agent_durable_gates`
  - `agent_durable_tool_effects`
- 保留数据：34 用户、21 Style、18 频道、82 条传统 `generation_tasks`。

## 后端验证

- 现有 Native Run 创建时只初始化一个 Durable Workflow。
- 候选选题审批即使仍由现有页面的 `final_article` 容器展示，后端也会按内容识别为
  `topic_selection` Gate。
- 用户批准“使用第一个选题就可以”后，Durable Workflow 不进入成功终态，而是准备同一 Run 的
  `write_draft` Attempt，并把批准反馈写入现有持久化模型上下文。
- 正文、Review 和最终 Review 分别受独立 Durable Gate 控制；旧 Loop 在任一 required Task 或
  Gate 未完成时不能写入 Run 成功终态。
- Worker 在迁移后的库中会把原 `run_id` 入队请求解析为当前 Durable `attempt_id`；等待用户输入
  的 Gate 不会在启动恢复时自动执行，lease 过期 Attempt 会生成 `resume` Attempt。

## 页面回归

- 使用隔离服务打开保留的原 Agent 页面。
- 已验证页面仍显示 `Simple Agent Loop`、`Skill 管理`、`返回传统工作台` 和 `@` 资源按钮。
- 已验证 `@` 菜单保留 `文案创作团队` Skill、Style 资源列表和资源标签选择/移除交互。
- 本 Sprint 未重构或替换任何前端组件。

## 自动验证

```text
PYTHONPATH=backend backend/.venv/bin/python -m unittest \
  backend.tests.test_durable_agent_runtime \
  backend.tests.test_native_article_workflow \
  backend.tests.test_native_agent_loop
./scripts/check.sh
git diff --check
```

结果：全部通过。完整检查覆盖 343 项后端测试、14 项前端测试、前端生产构建、Remotion 类型检查和
模板测试。
