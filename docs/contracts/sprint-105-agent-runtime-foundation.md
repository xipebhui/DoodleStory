# Sprint 105：可持久化 Agent Runtime 基础

## Status

Active。该 Sprint 是 Agent V1 全局路线的阶段 1；完成前不得实现 Sprint 106 的漫画生图链路。

## Goal

在不接入漫画生图 Tool、不修改现有生产生成 Pipeline 的前提下，实现一条真实、可持久化、可恢复并支持火苗到 LIO 备用切换的 Agent 文本 Turn：用户能够通过后端 API 创建会话、发送消息、异步获得 Agent 回答，并在服务重启后继续读取同一会话和运行记录。

## In scope

### 1. SDK 与 API 形态决策

- 安装并锁定一个明确版本的 OpenAI Agents SDK 及兼容的 OpenAI Python client。
- 新增独立兼容性脚本，使用更新后的火苗、LIO API key 和统一模型 `gpt-5.6-terra`，分别验证 SDK 的 Responses Function Calling、Tool Output 续写和应用侧完整输入重放。
- SDK 探测零跨 Provider fallback，分别保存两个平台的脱敏结论。
- 两个平台均通过 SDK Responses Tool Loop 后，正式 Runtime 使用 Responses 模型形态；任一平台失败时暂停实现，更新本合同和架构决策，不静默换成 Chat Completions。

### 2. Agent 专用配置

- Agent 使用现有 `TEXT_FALLBACK_BASE_URL/API_KEY` 作为火苗主平台，使用现有 `LIO_BASE_URL/API_KEY` 作为 LIO 备用平台。
- 新增 Agent 专用模型配置，默认/本地目标为 `gpt-5.6-terra`，不要求修改旧 Pipeline 当前使用的模型字段。
- 底层 SDK/OpenAI client 自动重试关闭；Runtime 统一拥有重试和切换次数。
- 不打印、持久化或返回 API key。

### 3. 最小数据模型

- `agent_conversations`：用户会话和列表排序。
- `agent_messages`：规范化用户/assistant/system event 消息，包含受控资源引用 JSON 字段但本 Sprint 不解析具体资源。
- `agent_runs`：一次用户 Turn 的异步运行状态、预算计数和错误。
- `agent_steps`：模型调用、fallback 和最终消息 checkpoint。
- 增加必要外键、唯一约束以及已知列表/恢复查询所需索引。
- 使用一条可审阅 Alembic migration，不创建通用事件仓库或阶段 2 之后的资源表。

### 4. 最小 API 与权限

- 创建 Conversation。
- 分页列出当前用户的 Conversation。
- 读取当前用户的 Conversation 详情和有界消息历史。
- 向 Conversation 发送用户消息并创建一个 Run。
- 查询 Run 当前状态和用户安全错误。
- 普通用户只能访问自己的 Conversation、Message 和 Run；Admin 不在本 Sprint 获得跨用户 Agent 会话入口。

### 5. Runner、恢复和模型路由

- 使用当前项目的进程内队列调度 `run_id`，数据库是状态事实来源。
- 第一版 `ComicDirectorAgent` 只完成文本理解与回答，不调用漫画 Tool，不创建 GenerationTask。
- 每次模型调用从应用数据库构造可重放输入，不使用 Provider `previous_response_id` 或远程 conversation 作为唯一上下文。
- 火苗只对连接、超时、429 和语义明确的临时 5xx 做一次有界重试；仍失败且尚未输出结果时切换一次 LIO。
- 401/403、请求 schema、内容策略、`invalid_request`、`model_not_found`、模型/API 不支持等永久错误不重试、不切换。
- 暂不实现熔断器、Provider 健康评分或多区域路由。
- Worker 在模型响应和最终消息的完整 step 边界 checkpoint；启动时恢复没有完成的安全 Run，不重复已经成功的模型 step。

### 6. 可观测性

- 每个模型 Step 记录 `conversation_id/turn_id/run_id/step_id`、provider、model、API shape、attempt、fallback、延迟、usage、Provider request ID、状态和脱敏错误。
- 不保存 Chain of Thought。
- 结构化日志可以从 Run 追踪到 Step；数据库仍是业务状态事实来源。

## Out of scope

- 不实现 `ComicPlan`、`generate_image` 或 `inspect_image`。
- 不创建 GenerationTask、Panel、图片 job 或积分交易。
- 不接正式前端页面，不复制 Sprint 103 Demo 的假数据到产品代码。
- 不解析 `@风格/@角色/@任务/@Panel/@图片版本`。
- 不实现 Panel 修改、图片重试、版本恢复、取消或 VL 检查。
- 不修改现有故事切分、Prompt 编译、内容提取或生图 Pipeline。
- 不引入 LangChain、LangGraph、多 Agent、Redis、Celery、Temporal、外部队列、Token 流或熔断器。
- 不返回 Mock Agent 回答；开发和验收必须调用真实火苗/LIO 模型。

## Done means

1. SDK 兼容性脚本证明两个平台 `gpt-5.6-terra` 的同一 Responses Tool Loop 可用，并保存脱敏报告。
2. 创建会话、分页列表、读取详情、发送消息和读取 Run API 均有认证、归属校验和稳定响应 schema。
3. 一个真实用户消息会创建持久化 Message/Run/Step，通过进程内 worker 调用火苗并写入真实 assistant 消息。
4. 同一 Conversation 的第二个 Turn 能读取第一轮上下文；输入从应用数据库重放，不依赖 Provider continuation ID。
5. 故障注入证明临时错误按上限重试后切 LIO，永久错误不切换；fallback 后只有一个最终 assistant 回答。
6. 重启恢复测试证明安全的未完成 Run 可以继续，已完成模型 step 和最终消息不会重复。
7. 数据库 migration 可从空库升级，Conversation 列表和 Run 恢复查询有对应约束/索引。
8. 日志和 API 响应不包含 API key、完整 Authorization 或未脱敏第三方错误。
9. 现有生产生成、图片、积分和内容提取测试不回归。

## Verification

实现窗口需要把新增测试纳入 `scripts/check.sh`，并至少运行：

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest \
  backend.tests.test_agent_sdk_compatibility \
  backend.tests.test_agent_model_router \
  backend.tests.test_agent_conversations \
  backend.tests.test_agent_runner_recovery

backend/.venv/bin/python scripts/check_agent_sdk_compatibility.py \
  --provider all \
  --model gpt-5.6-terra \
  --output /tmp/doodlestory-agent-sdk-provider-report.json

backend/.venv/bin/alembic -c backend/alembic.ini upgrade head
backend/.venv/bin/python -m compileall backend/app scripts
git diff --check
./scripts/check.sh
```

如果实际文件名因实现结构调整，必须在合同和 `docs/progress.md` 中同步最终命令。真实 SDK Provider 探测不得用单元测试替代。

## Handoff

Sprint 105 完成后：

- 将 `docs/implementation/agent-v1-implementation-roadmap.md` 的阶段 1 标记为已完成。
- 在 `docs/progress.md` 记录 SDK/API shape 最终决策、migration、API、真实 fallback 和恢复验证结果。
- 评审并激活 `docs/contracts/sprint-106-agent-comic-creation-vertical-slice-draft.md`；不得直接扩大 Sprint 105 范围。
- Sprint 106 只能复用已验证的 Runtime 和状态契约，不重新引入 Provider 远程上下文依赖。

## Assumptions to review

- 本地 `.env` 已配置更新后的火苗与 LIO API key；实现和测试不得输出密钥。
- 两个平台的 Agent 模型统一为 `gpt-5.6-terra`。
- 当前是单进程/少实例本地开发，进程内队列满足阶段 1。
- Sprint 105 可以新增 Agent 专用配置，避免改变旧 Pipeline 当前模型行为。
