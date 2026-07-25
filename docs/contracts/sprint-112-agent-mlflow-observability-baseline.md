# Sprint 112：Agent MLflow 可观测性基线

## Status

Complete。2026-07-24 已完成兼容性 spike、生产 tracing、脱敏、查询 smoke、自动化测试和三类真实验收。火苗凭据恢复后，`gpt-5.5` 直接成功 trace 已补齐，Sprint 112 全部 Done means 通过。

## Goal

在不改变 Agent 业务状态机和 Provider 路由契约的前提下，将当前真实 Agent 模型调用、平台切换、Tool/等待步骤和 Run 结果接入 MLflow Tracing，形成可查询、可关联、可比较的观测基线。数据库继续是业务事实来源，MLflow 只承担观测与 Evaluation 输入。

## User and operator outcome

- 开发者可以从一个 `agent_run_id` 找到完整 MLflow trace。
- 可以看见火苗/LIO 的实际 Provider、模型、attempt、fallback、延迟、usage、错误分类和结果状态。
- 可以区分模型调用、Tool Call、Tool Result、等待图片和最终响应。
- 关闭或未配置 MLflow 时，系统行为明确；启用但配置错误时启动或测试明确失败，不静默假装已观测。
- 当前 Agent 的用户体验和生成结果不因本 Sprint 改变。

## Preconditions and decision gate

实施第一步必须使用当前锁定版本做一次兼容性 spike：

- `openai-agents==0.18.3`
- `openai==2.45.0`
- 当前计划安装的 MLflow 版本
- 火苗与 LIO 的 OpenAI-compatible base URL

Spike 至少验证：

1. `mlflow.openai.autolog()` 或官方当前推荐方式能否捕获 Agents SDK 的模型调用。
2. 自定义 `AsyncOpenAI` client 和自定义 base URL 是否能保留 Provider/model/usage。
3. Agent 现有 `RunConfig(tracing_disabled=True)` 对 MLflow 自动观测的实际影响。
4. Tool Call/Tool Output 是否需要显式 span。
5. trace ID 如何稳定取得并用 `agent_run_id` 检索。

如果官方集成不能可靠捕获当前 SDK 路径，必须在合同中记录结论并暂停评审；不得偷偷换成另一套 APM、假 trace 或无声手工日志兜底。

### 2026-07-24 spike 结论

- `mlflow==3.14.0` 官方 OpenAI autolog 可以捕获 `openai-agents==0.18.3` 经自定义 `AsyncOpenAI/base_url` 发出的 Responses 调用。
- `RunConfig(tracing_disabled=True)` 不阻断 MLflow 捕获。
- LIO 真实成功路径保留 model、usage 和 provider request ID。
- 当前业务 Tool/等待不通过 Agents SDK function tool 执行，必须在既有 `AgentStep` 边界显式建 span。
- `agent_run_id` 根 trace tag 可以稳定唯一检索，不需要新增 `mlflow_trace_id` 列。
- 轻量 `mlflow-tracing` / `mlflow-skinny` 不能同时满足本地 SQL 查询和 OpenAI autolog，依赖锁定完整 `mlflow==3.14.0`。
- 详细证据见 `docs/testing/agent-mlflow-compatibility-spike.md`。

## In scope

### 1. 配置

新增明确配置，命名可按现有 Settings 习惯微调：

```text
MLFLOW_TRACING_ENABLED=false
MLFLOW_TRACKING_URI=
MLFLOW_EXPERIMENT_NAME=doodlestory-agent-local
MLFLOW_TRACE_CONTENT=false
```

规则：

- 默认不开启，避免未配置环境产生外部写入。
- `MLFLOW_TRACING_ENABLED=true` 时，Tracking URI 与 Experiment 必须通过启动校验。
- `MLFLOW_TRACE_CONTENT=false` 时不发送用户原文、完整 Prompt、图片 URL、API key 或 Provider 原始响应。
- API key、Authorization、完整资源 URL 和内部文件路径始终禁止进入 MLflow。
- 环境变量示例和本地启动说明同步更新。

### 2. Trace 层级

每个 Agent Run 对应一个根 trace，至少包含：

```text
agent.run
├── agent.model_call
├── agent.skill_load（当前尚无真实 Skill 时可不出现）
├── agent.tool_call
├── agent.tool_wait
├── agent.tool_result
└── agent.finalize
```

Sprint 112 只观测当前已存在的步骤，不虚构 Skill span。

根 trace 标签至少包含：

- `agent_run_id`
- `conversation_id`
- `turn_id`
- `task_id`（存在时）
- `run_status`
- `agent_model`
- `app_environment`
- `git_commit`（运行时可取得时）

模型 span 至少包含：

- provider：`huomiao` 或 `lio`
- model
- API shape
- attempt
- fallback_from / fallback_reason
- latency_ms
- provider_request_id
- token usage（Provider 返回时）
- error_code 和脱敏错误摘要

Tool/等待 span 至少包含：

- tool name
- AgentStep ID
- idempotency key 的安全摘要
- task/panel/image job 的稳定 ID
- queued/running/succeeded/failed
- 等待时长
- 图片调用数量与积分变化摘要

### 3. 与现有持久化的边界

- `agent_runs` 与 `agent_steps` 继续是业务状态、恢复、幂等和用户可见结果的事实来源。
- MLflow trace 不参与 Run 恢复、Tool 重放、权限、预算或取消判断。
- 不把完整 MLflow trace JSON 回写数据库。
- 本 Sprint默认不新增数据库列。MLflow trace 必须使用 `agent_run_id` 标签反查。
- 如果 spike 证明必须持久化外部 trace ID 才能稳定检索，先更新本合同并评审一个 nullable `mlflow_trace_id`；未经更新不得直接加 migration。

### 4. 错误行为

- 开启 MLflow 时，启动配置错误必须明确失败。
- 运行期间 trace 上报失败必须记录结构化 `observability_error`，包含 `agent_run_id` 和脱敏原因。
- trace 上报失败不得把已经成功的图片或 Agent Run 回滚，也不得改写业务错误；这是观测隔离，不是 Provider fallback。
- 不允许 `except Exception: pass`。

### 5. 最小观测验证工具

- 提供一个本地 smoke 命令或脚本，创建/运行一个受控 Agent Turn，并输出：
  - agent_run_id；
  - 是否找到根 trace；
  - span 数；
  - provider/model；
  - 是否发生 fallback；
  - trace 页面或查询标识。
- 输出必须脱敏，不写 API key 或完整用户内容。
- 在 `docs/testing/` 保存兼容性与 smoke 结果。

## Out of scope

- Prompt Registry 作为运行时依赖。
- MLflow 驱动业务状态或前端进度。
- 用户可见的 trace/debug 页面。
- 新 Skill、HITL、SSE、资源引用和 Panel/VL。
- 计算精确人民币成本；Provider 未返回定价信息时只记录 token/图片调用数量。
- OpenTelemetry、LangSmith 或其它观测平台并行接入。
- 自动质量 Judge 和完整 Evaluation 排行；已按后续规划顺延到 Deferred 的最终发布阶段。

## Deliverables

- MLflow 依赖和受版本约束的集成代码。
- 配置、启动校验与脱敏策略。
- Agent Run/model/tool/wait/final spans。
- 兼容性 spike 与真实 smoke 报告。
- 单元测试和必要的集成测试。
- 更新后的环境变量示例、规格、路线和进度。

## Recommended implementation order

1. 独立运行官方集成兼容性 spike，不先改生产 Runner。
2. 固定 MLflow 版本并记录选择依据。
3. 实现 tracing 初始化和脱敏配置。
4. 在 Agent Runner/Router 的现有 Step 边界增加 span。
5. 增加 trace 查询 smoke 和故障测试。
6. 用火苗成功、火苗到 LIO fallback、永久错误三类路径验收。

## Done means

1. 可用 `agent_run_id` 在 MLflow 找到唯一根 trace。
2. 正常模型调用可以看到真实 provider、model、attempt、latency 和 usage。
3. 受控火苗临时错误可以在同一 trace 中看到火苗失败与 LIO 成功。
4. 永久错误不触发 LIO，trace 与数据库 AgentStep 结论一致。
5. Tool Call、图片等待和 Tool Result 的关键 ID 与状态可关联。
6. 默认脱敏策略下不出现 API key、Authorization、完整 Prompt、用户全文或完整图片 URL。
7. MLflow 未启用时不产生连接；启用但配置错误时明确失败。
8. 当前 Agent 功能、数据库恢复和 Provider 路由测试无回归。

## Verification

### Automated

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest \
  backend.tests.test_agent_model_router \
  backend.tests.test_agent_runner_recovery
backend/.venv/bin/python -m compileall backend/app
git diff --check
./scripts/check.sh
```

新增测试至少覆盖：

- disabled 时不初始化 MLflow。
- enabled 且配置缺失时明确失败。
- trace 标签与 AgentRun/AgentStep ID 一致。
- fallback 两次 attempt 属于同一个根 trace。
- 永久错误不创建备用平台成功 span。
- 脱敏器拒绝敏感字段。
- MLflow 上报异常被明确记录但不改写已提交的业务状态。

### Real integration smoke

至少保存三条脱敏证据：

1. 火苗直接成功。
2. 故障注入后火苗允许重试/切 LIO 成功。
3. 永久错误明确失败且不切 LIO。

## Risks

- 官方自动集成对自定义 OpenAI client/base URL 的字段捕获可能不完整。
- MLflow 包可能显著增加依赖体积和启动时间，必须记录安装体积与启动影响。
- Trace 内容采集可能泄露用户创作内容，默认必须关闭内容记录。

## Handoff

- Sprint 112 Complete 后才能激活 Sprint 113。
- Sprint 113 新增 Skill/Tool span 时复用本 Sprint trace API，不另建第二套日志体系。
- 完成后更新路线图、进度和 `docs/testing/` 证据。

## Completion evidence

- 火苗直接成功：Agent Run `c3c1dd54fa0f4d0e807786cc89ee5ac2`，MLflow trace `tr-7cc99632fd625cb4abe72b729fcc91be`；唯一根 trace，`huomiao/gpt-5.5`、attempt 1、无 fallback，Run 与 trace 均成功。
- 模型 span 保存 `requests=1`、input/output/total tokens `121/31/152`、延迟 `2381ms`；provider request ID 与数据库 AgentStep 一致。
- 受控临时错误后 LIO 成功、永久错误不 fallback 的证据继续通过。
- 完整 trace 扫描未出现受控用户正文、模型回复、邮箱、Authorization/Bearer、HTTP(S) URL、`/Users/` 或 `/tmp/` 路径。
- 开发与生产环境只接受 HTTP(S) Tracking Server；直接 SQLite/file URI 会明确失败，防止 MLflow 系统 artifact 标签暴露内部路径。
- `./scripts/check.sh` 通过：209 项后端测试、空库 Alembic migration、Python compileall 和前端生产构建均成功。

## New-window start prompt

> 请实施 Sprint 112。先阅读 `AGENTS.md`、`README.md`、`docs/spec.md`、`docs/progress.md`、Agent V1 路线图、`docs/contracts/sprint-112-agent-mlflow-observability-baseline.md`、Python/数据库/后端工作流规范，以及当前 Agent Runner、Router、AgentStep 实现。第一步必须先做当前 Agents SDK、自定义火苗/LIO client 与 MLflow 官方集成的真实兼容性 spike；如果不兼容就记录阻塞并暂停，不得引入未授权替代平台或假 trace。只做观测，不改业务状态机、Provider fallback 或用户界面。完成验证、文档和中文详细 commit。
