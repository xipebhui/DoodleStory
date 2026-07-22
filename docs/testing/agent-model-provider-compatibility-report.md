# Agent 模型平台兼容性实测报告

## 结论

Agent V1 的火苗主平台与 LIO 备用平台统一采用 OpenAI Chat Completions 形态。

- 火苗 `gpt-5.4`：Chat Completions、JSON 输出、Function Calling、Tool Output 续写、多模态输入和 Responses API 全部通过。
- LIO `gemini-3.1-flash-lite-preview-thinking-minimal`：Chat Completions、JSON 输出、Function Calling、Tool Output 续写和多模态输入通过；`/v1/responses` 明确不支持。
- 不在同一个 Agent workflow 中混用 Responses 与 Chat Completions。即使火苗支持 Responses，只要透明备用线路 LIO 不支持，V1 就统一使用 Chat Completions，并由 DoodleStory 保存可重放的完整消息与工具历史。
- LIO 对“不支持 `/v1/responses`”返回 HTTP 503，但错误体是 `invalid_request` 和永久能力错误。正式 Router 必须联合判断 HTTP 状态码、Provider 错误码和错误语义，不能把所有 503 都重试或切换。

本次实测确认的是接口兼容性，不等于长期稳定性结论。持续可用率、延迟分位数和故障切换仍需要在 Agent Runtime 落地后通过结构化 trace 和故障注入验证。

## 测试环境

测试时间：2026-07-22（Asia/Shanghai）。

| 角色 | Host | 模型 | 配置来源 |
| --- | --- | --- | --- |
| 主平台 | `api.huomiao.art` | `gpt-5.4` | `TEXT_FALLBACK_*` |
| 备用平台 | `api.apilio.ai` | `gemini-3.1-flash-lite-preview-thinking-minimal` | `LIO_*` |

脚本直接调用 OpenAI 兼容 HTTP 接口；每项请求零自动重试、零跨平台 fallback。报告不保存 API key，不保存成功响应原文，只保存通过证据、延迟和脱敏错误摘要。

## 最终实测矩阵

| 能力 | 火苗 | LIO | Agent V1 决策 |
| --- | --- | --- | --- |
| Chat Completions | 通过，1698 ms | 通过，1544 ms | 使用 |
| JSON object | 通过，5030 ms | 通过，721 ms | 使用，但仍做应用层 schema 校验 |
| Function Calling + Tool Output | 通过，3871 ms | 通过，2363 ms | 使用 |
| 多模态 `image_url` | 通过，1795 ms | 通过，1534 ms | 可作为 VL 模型调用形态 |
| Responses API | 通过，2215 ms | 失败，327 ms | V1 不使用 |

延迟为一次兼容性请求的观测值，不作为性能基准或 SLA。

## JSON 输出校准发现

LIO 首次 JSON 探测使用了“返回这段 JSON 的含义”这一有歧义的指令。平台返回了合法 JSON，但把要求的字段改写成一个 `meaning` 字段。将测试改成明确约束“键名、类型、值均不得重命名、翻译、包装或省略”后通过。

这说明 Evaluation 不能只判断“能否解析 JSON”，还必须验证字段、类型和业务不变量。正式 Runtime 对所有模型结构化结果都要执行应用层 schema 校验；校验失败属于模型输出不合格，不应当被当作网络错误无限重试。

## Responses 失败性质

LIO `/v1/responses` 返回 HTTP 503，但脱敏后的核心语义是：当前模型所有分组均不支持该 API 路径，错误码为 `invalid_request`。这是永久能力不匹配，而不是临时服务不可用：

- 不应在同一平台重复请求同一路径。
- 不应依靠 HTTP 503 单独判断为可重试。
- 不应在一次 workflow 中让火苗使用 Responses、切到 LIO 时再临时转换为 Chat Completions。

## 验证命令

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest \
  backend.tests.test_agent_model_compatibility

backend/.venv/bin/python scripts/check_agent_model_compatibility.py \
  --provider all \
  --output /tmp/doodlestory-agent-provider-report.json
```

全平台命令按设计返回非零退出码，因为 LIO Responses 能力失败；JSON 报告仍完整生成。单测覆盖敏感信息脱敏、Chat/Responses 内容提取、能力参数解析和暂时/永久错误分类。

## 下一 Sprint 的输入

1. 用 Chat Completions 模型形态实现一个 `AgentModelRouter`，火苗主用、LIO 备用。
2. 底层 Client 关闭自动重试；Router 统一负责有界重试和跨平台切换。
3. Router 解析 Provider 错误体，识别“503 + invalid_request/unsupported”为永久错误。
4. 每次模型请求从应用数据库重放规范化消息、Tool Call 与 Tool Output，不依赖 Provider response ID。
5. 用故障注入分别验收“主平台临时失败后切 LIO”和“请求/权限/能力错误不切换”。
