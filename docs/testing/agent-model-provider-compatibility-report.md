# Agent 模型平台兼容性实测报告

## 结论

火苗主平台和 LIO 备用平台使用统一模型 `gpt-5.6-terra` 时，当前直接 HTTP 兼容性探测全部通过：

- Chat Completions 文本请求。
- JSON object 结构化输出。
- Chat Completions Function Calling 和 Tool Output 续写。
- 多模态 `image_url` 输入。
- 基础 Responses 文本请求。

这证明两个平台都具备进入 OpenAI Agents SDK 实测的基础能力，但还没有锁定正式 Runtime 的 API shape。当前脚本的 Function Calling/Tool Output 使用 Chat Completions，Responses 项只验证文本输出；Sprint 105 必须继续验证“Agents SDK + Responses Function Call + Tool Output + 应用侧完整输入重放”。只有两个平台的同一 SDK Tool Loop 都通过，才能正式选择 Responses 模型形态。

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

## Sprint 105 的输入

1. 锁定 OpenAI Agents SDK 与兼容 OpenAI client 版本。
2. 分别对火苗、LIO 运行相同的 Responses SDK Tool Loop，不在探测脚本中 fallback。
3. 验证 Function Call、Tool Output、final response 和应用侧完整历史重放，不只验证 Responses 文本。
4. 两个平台都通过后正式使用 Responses；任一失败时暂停并更新架构合同，不在一个 workflow 混用 API shape。
5. 正式 Runtime 底层关闭自动重试，由 Router 统一执行有界重试、错误语义分类和一次备用切换。
