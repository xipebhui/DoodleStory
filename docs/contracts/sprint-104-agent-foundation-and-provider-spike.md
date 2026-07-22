# Sprint 104：Agent 开发前置契约与模型平台兼容性验证

## Goal

在编写正式 Agent Runner、数据库迁移和生产 API 之前，建立一套可评审、可验证的 Agent V1 产品与技术契约，并用真实火苗与 LIO 配置确认两套 OpenAI 兼容平台能否承载 Agent 所需的文本、结构化输出、工具调用、多轮工具结果和视觉理解能力。

## In scope

- 编写 Agent V1 精简 PRD，明确会话、Agent Run、漫画任务、Panel 修改和资源引用的关系。
- 编写单 Agent Runtime 与持久化边界设计，明确数据库是会话和运行状态的事实来源。
- 编写最小 Tool 契约，区分 Agent 模型、模型可调用工具和 Runtime 内部状态操作。
- 编写火苗主平台、LIO 备用平台的模型路由与错误分类契约，但不接入正式业务链路。
- 新增只读兼容性检测脚本，分别验证两个平台，不在检测脚本中自动执行 Provider fallback。
- 增加兼容性脚本的无网络单元测试。
- 使用当前本地已配置的火苗与 LIO 密钥执行真实兼容性检测，并保存不含密钥和原始敏感响应的结论。
- 建立 Agent V1 Evaluation 用例集和首版评分规则。

## Out of scope

- 不安装或接入 OpenAI Agents SDK。
- 不实现正式 `AgentModelRouter`、Agent Loop 或 Tool 执行器。
- 不新增会话、Run、Step、Tool Call 数据表或 Alembic migration。
- 不修改现有任务创建、内容提取、LLM、生图或积分链路。
- 不实现正式前端 API、SSE、WebSocket 或流式 Token 输出。
- 不引入 LangChain、LangGraph、Redis、Celery、Temporal 或其它工作流基础设施。
- 不伪造平台兼容结果；未通过的能力必须在报告中明确标记。

## Done means

1. PRD 明确新建/继续对话、后台任务、Panel 重试和 `@资源` 的验收行为。
2. Runtime 设计明确单 Agent、应用侧上下文、step checkpoint、恢复边界和拟议状态表。
3. Tool 契约明确图片生成、图片检查和资源注入边界，并说明文本模型为什么不是同层 Tool。
4. 兼容性脚本可以只读取环境配置，分别运行火苗和 LIO 测试，输出脱敏 JSON 结果。
5. 两个平台的真实测试报告至少覆盖 Chat Completions、JSON 输出、Function Calling、多轮 Tool Output、多模态输入和 Responses API 探测。
6. Evaluation 数据集至少包含 15 个代表性用例，并区分确定性断言与人工/模型评分项。
7. 文档明确下一 Sprint 采用哪个 API 形态，以及哪些能力仍是 blocker。

## Verification

- `PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_agent_model_compatibility`
- `backend/.venv/bin/python scripts/check_agent_model_compatibility.py --provider all --output /tmp/doodlestory-agent-provider-report.json`
- `backend/.venv/bin/python -m compileall scripts/check_agent_model_compatibility.py backend/tests/test_agent_model_compatibility.py`
- `git diff --check`
- `./scripts/check.sh`

真实 Provider 检测允许以非零退出码结束，但报告文件必须成功生成，并逐项记录失败原因；兼容能力失败不是测试脚本失败，而是本 Sprint 必须保留的决策证据。

## Handoff

下一 Sprint 只能基于真实兼容性报告选择：

- 两个平台都完整支持 Responses 时，评估 `OpenAIResponsesModel`。
- 任一平台只可靠支持 Chat Completions 时，Agent V1 统一使用 `OpenAIChatCompletionsModel`，避免同一 workflow 混用两种模型形态。
- LIO 工具调用或多轮 Tool Output 不通过时，LIO 不能作为完整 Agent Turn 的透明备用平台；必须先解决模型/线路能力或缩小备用范围。
- 只有工具调用兼容性、应用侧上下文重放和失败分类契约通过后，才实现正式 Provider Router。

## Assumptions to review

- 本文档将用户所说的“引领你平台”映射为仓库现有 `LIO_*` 配置。
- 当前部署的 `TEXT_FALLBACK_*` 指向火苗，作为 Agent 主平台；`LIO_*` 作为备用平台。
- 第一版保持单 Agent，不通过多 Agent 或工作流图解决漫画创作问题。

## Completion record

- 真实测试时间：2026-07-22。
- 火苗 `gpt-5.4` 的 Chat Completions、JSON、Function Calling、Tool Output、多模态和 Responses 全部通过。
- LIO `gemini-3.1-flash-lite-preview-thinking-minimal` 除 Responses 外全部通过；`/v1/responses` 返回永久路径不兼容。
- Agent V1 因此统一选择 Chat Completions，完整结论见 `docs/testing/agent-model-provider-compatibility-report.md`。
- Evaluation 数据集包含 20 个场景，见 `evals/agent_v1/cases.jsonl`。
- 本 Sprint 未安装 SDK、未创建 Agent 表、未实现 Router 或修改现有生产链路，符合 Out of scope。
