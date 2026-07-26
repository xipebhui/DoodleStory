# Sprint 120：Native Loop MLflow 与 Agent UI 一致性

## Status

Complete（Closed）。用户于 2026-07-26 要求拉起本地 Docker MLflow，把 Sprint 119 最小原生 Agent Loop
接入模型调用查看与后续评估基础，同时修复 `/agent` 页面与 Skill 管理页面色调不一致及输入框
黑底问题。

正式 Evaluation、评分规则和 GO/NO-GO 仍为 Deferred，本 Sprint 只交付可观测数据基础。

## Goal

1. 提供可重复拉起的本地 MLflow 3.14.0 Docker Tracking Server，并让本地开发后端显式连接。
2. 每个 Native Agent Run 产生一条可用 `native_agent_run_id` 唯一检索的根 Trace。
3. 根 Trace 下覆盖模型 Loop、`generate_image` Tool、图片 Provider 执行和 Run 终态。本地开发
   为模型调用查看与评估显式记录输入、输出、Skill 和 Prompt；密钥、Authorization、图片 URL、
   内部路径和 Provider 原始敏感字段仍必须脱敏。仓库示例与非本地环境继续默认关闭内容记录。
4. `/agent` 与 `/agent/skills` 使用同一套深色 Agent Studio 视觉系统；输入、选择、状态和焦点
   具备明确对比。

## Scope

- 新增独立本地 MLflow Compose 文件，固定官方 `ghcr.io/mlflow/mlflow:v3.14.0` 镜像、
  localhost 端口、SQLite metadata 与本地 artifact 持久卷。
- 本地 `.env` 启用 MLflow；`.env.example` 和 README 记录启动、停止、访问与健康检查方式。
- Native Loop 使用现有 `agent_observability` 脱敏层，不引入第二套追踪库；本地 `.env`
  显式设置 `MLFLOW_TRACE_CONTENT=true`，`.env.example` 保持 `false`。
- 新增 Native 根 Span 和模型/Tool/图片子 Span；记录 ID、模型、状态、调用次数、尺寸、延迟和
  Provider request ID 等安全元数据。
- 调整 Agent Shell、Skill 管理和 Native Loop CSS，解决深浅主题混用与 textarea 黑底问题。
- 增加自动化，覆盖根 Trace 标签、Span 层级、成功/失败状态与脱敏。

## Out of scope

- 正式 Evaluation 数据集、评分器、阈值、自动回归门禁。
- 生产 MLflow 部署、认证、TLS、远程对象存储或多人权限。
- 修改 Agent Loop、Skill 业务方法、生图并发或 Provider 路由。
- 暗色/浅色模式切换器。

## Verification

1. Docker MLflow `/health` 成功，UI 可从 `http://127.0.0.1:5000` 打开。
2. 后端重启后确认 `MLFLOW_TRACING_ENABLED=true` 且 Tracking Server 初始化成功。
3. 自动化创建 Native Run Trace，并用 `native_agent_run_id` 唯一检索。
4. `MLFLOW_TRACE_CONTENT=false` 的自动化确认正文和 Prompt 被移除；所有模式都确认 URL、密钥
   和本地绝对路径被移除。
5. 真实浏览器检查 `/agent`、`/agent/skills`、textarea 输入文字、select、hover、focus 和响应式。
6. `./scripts/check.sh` 与 `git diff --check` 通过。

## Verification result

- 官方 `ghcr.io/mlflow/mlflow:v3.14.0` 镜像已拉取；默认 4 worker 在当前 2GB Colima 中明确
  OOM，Compose 固定 1 worker 后容器保持 healthy，`/health` 返回 `OK`。
- 本地后端读取 `MLFLOW_TRACING_ENABLED=true`、实验 `doodlestory-agent-local` 和
  `MLFLOW_TRACE_CONTENT=true` 后启动成功。
- 本地 Trace `tr-feb7cf66a2b0fff48f93f7879baedaff` 可由
  `native_agent_run_id=local-content-smoke-26dc4f4f00` 唯一检索；内容标记可用于评估，受控 URL
  和 Authorization 标记未进入序列化 Trace。
- 自动化确认 Native Trace 包含 `native_agent.run`、`native_agent.model_loop`、
  `native_agent.generate_image` 和 `native_agent.image_provider`，关闭内容记录时正文、Skill、
  Prompt 和输出均被移除。
- 全新认证浏览器会话确认 `/agent` 与 `/agent/skills` 均为 0 console error；textarea 实际计算
  样式为浅色文字 `rgb(244, 240, 232)`、深色背景 `rgb(17, 19, 22)`、橙色 caret
  `rgb(255, 153, 72)`。
- `./scripts/check.sh` 通过 257 项后端测试、Python compileall、空 SQLite migration 与前端生产
  构建；`git diff --check` 通过。

## Done means

- 本地 MLflow 容器和 DoodleStory 开发服务同时在线。
- Native Loop 的模型调用与 Tool 执行可在 MLflow UI 中按 Run 定位。
- Agent 两个正常入口视觉一致，输入框不存在黑底黑字。
- 文档、进度、规格和实现一致，并创建中文详细 commit。
