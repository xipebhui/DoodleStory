# Agent 模型平台兼容性实测报告

## Sprint 105 最终结论

2026-07-22 的 OpenAI Agents SDK 决策门已经通过。正式 Runtime 锁定：

- `openai-agents==0.18.3`。
- `openai==2.45.0`。
- 火苗和 LIO 均使用 `gpt-5.6-terra` 与 Responses API。
- 两个平台分别在零 SDK retry、零 client retry、零跨 Provider fallback 下完成 Responses Function Call → Tool Output → final response，并通过应用侧完整输入重放的第二轮请求。
- 正式 Runtime 不使用 `previous_response_id` 或 Provider remote conversation 作为上下文事实来源。

脱敏机器可读证据保存于 `docs/testing/agent-sdk-provider-compatibility-report.json`。最终实测中，火苗完整探测耗时 17496 ms；LIO 完整探测耗时 11806 ms，并返回 3 个可追踪 Provider request ID。成功响应正文与 API key 均未写入报告。

## Sprint 104 基础 HTTP 结论

火苗主平台和 LIO 备用平台使用统一模型 `gpt-5.6-terra` 时，当前直接 HTTP 兼容性探测全部通过：

- Chat Completions 文本请求。
- JSON object 结构化输出。
- Chat Completions Function Calling 和 Tool Output 续写。
- 多模态 `image_url` 输入。
- 基础 Responses 文本请求。

这些直接 HTTP 结果是进入 SDK 决策门的基础证据；正式 API shape 已由上面的 Sprint 105 SDK 探测锁定为 Responses。

本次结果是接口能力证据，不是长期可用率或 SLA。延迟分位数、真实 fallback 和运行稳定性需要在 Agent Runtime 落地后通过 trace、故障注入和重复 Eval 建立基线。

## 测试环境

最终测试时间：2026-07-22（Asia/Shanghai）。

| 角色 | Host | 模型 | 密钥配置来源 |
| --- | --- | --- | --- |
| 主平台 | `api.huomiao.art` | `gpt-5.6-terra` | `TEXT_FALLBACK_*` |
| 备用平台 | `api.apilio.ai` | `gpt-5.6-terra` | `LIO_*` |

脚本直接调用 OpenAI 兼容 HTTP 接口；每项请求零自动重试、零跨平台 fallback。报告不保存 API key，不保存成功响应原文，只保存通过证据、延迟和脱敏错误摘要。

## 最终实测矩阵

| 能力 | 火苗 | LIO | 当前结论 |
| --- | --- | --- | --- |
| Chat Completions | 通过，4127 ms | 通过，2469 ms | 两个平台可用 |
| JSON object | 通过，4301 ms | 通过，2739 ms | 两个平台可用，仍需应用 schema 校验 |
| Chat Function Calling + Tool Output | 通过，3567 ms | 通过，6072 ms | 两个平台可用 |
| 多模态 `image_url` | 通过，3049 ms | 通过，8792 ms | 两个平台可用 |
| 基础 Responses 文本 | 通过，1680 ms | 通过，8159 ms | 进入 SDK Tool Loop 决策门 |

延迟是单次兼容性请求的观测值，不作为性能门槛。

## LIO API key 更新过程

第一次把 LIO 模型临时覆盖为 `gpt-5.6-terra` 时，`/v1/models` 可以看到该模型，但实际请求返回 HTTP 503、错误码 `model_not_found`，语义是当前 API key 所属 `[origin]` 分组没有可用渠道。用户更新 LIO API key 后，五组探测全部通过。

这个过程产生两个 Router 约束：

- `/v1/models` 可见不等于当前 key/group 实际可调用，必须用真实请求验收。
- Provider 可能用 HTTP 503 包装永久配置错误；Router 必须联合判断错误码和错误语义。`model_not_found`、无可用渠道、`invalid_request` 和 API/模型不支持不得按临时 503 自动重试或切换。

## JSON 输出校准发现

早期 LIO JSON 探测使用了“返回这段 JSON 的含义”这一有歧义的指令。平台返回合法 JSON，但把要求字段改写成 `meaning`。将测试明确为“键名、类型、值均不得重命名、翻译、包装或省略”后通过。

因此 Evaluation 不能只判断能否解析 JSON；正式 Runtime 对模型结构化结果必须继续执行应用层 schema 和业务不变量校验。

## 验证命令

Sprint 105 最终 SDK 决策门：

```bash
PYTHONPATH=backend backend/.venv/bin/python scripts/check_agent_sdk_compatibility.py \
  --provider all \
  --model gpt-5.6-terra \
  --output /tmp/doodlestory-agent-sdk-provider-report-final.json
```

正式 Runtime 两轮真实对话：

```bash
PYTHONPATH=backend backend/.venv/bin/python scripts/check_agent_runtime_smoke.py \
  --output /tmp/doodlestory-agent-runtime-smoke-report.json
```

该 smoke 的脱敏证据保存于 `docs/testing/agent-runtime-two-turn-smoke-report.json`；Conversation ID 为 `7980d1bac60b476f834e8d191fa6a832`，两个 Run ID 为 `7fdd4824f69243ae94c450198628e00f`、`0e744b264dc54b1180b475210351d52d`。第二轮从应用数据库重放 4 条规范化消息，并验证了第一轮上下文标记。

Sprint 104 直接 HTTP 能力探测：

最终模型通过进程环境临时覆盖，未修改仓库 `.env`：

```bash
TEXT_FALLBACK_MODEL=gpt-5.6-terra \
LIO_MODEL=gpt-5.6-terra \
backend/.venv/bin/python scripts/check_agent_model_compatibility.py \
  --provider all \
  --output /tmp/doodlestory-agent-gpt-5.6-terra-report.json
```

LIO 更新 key 后的独立复测也保留为诊断证据：

```bash
LIO_MODEL=gpt-5.6-terra \
backend/.venv/bin/python scripts/check_agent_model_compatibility.py \
  --provider lio \
  --output /tmp/doodlestory-agent-gpt-5.6-terra-lio-updated-key-report.json
```

离线脚本测试：

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest \
  backend.tests.test_agent_model_compatibility
```

## Sprint 105 的落地结果

1. 已锁定 OpenAI Agents SDK 与兼容 OpenAI client 版本。
2. 火苗、LIO 的 Responses SDK Tool Loop 均在独立、零 fallback 条件下通过。
3. Function Call、Tool Output、final response 和应用侧完整历史重放均已验证。
4. 正式 Runtime 只使用 Responses，不在同一 workflow 混用 API shape。
5. 正式 Runtime 底层自动重试关闭，由 Router 统一执行有界重试、错误语义分类和一次备用切换。
