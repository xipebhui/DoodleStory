# SiliconFlow Native Agent 适配实施蓝图

日期：2026-08-12

状态：设计冻结候选；代码、迁移、真实模型调用和 S03 媒体调用均未执行

配套架构图：

- [SVG](diagrams/siliconflow-native-agent-adapter.svg)
- [PNG](diagrams/siliconflow-native-agent-adapter@2x.png)

## 1. 结论先行

SiliconFlow 不应被实现成“第二个 Base URL 开关”。首个安全版本需要一个**有明确能力边界的 Run 级
模型路由**，并同时修复当前 Native Agent 已存在的模型快照漂移问题。

建议的首版结构是：

```text
Run 创建时选择 route
  → 固化 provider / api_shape / model
  → 校验 Skill 是否属于该 route 已开放的能力 profile
  → Provider 工厂按 Run 快照取凭据
  → Chat 请求前按 SDK 的实际转换结果检查 messages
  → 事件适配器把 SDK 伪 ID 转为应用稳定身份
  → 现有 Session / Step / Event 继续作为事实来源
```

SiliconFlow Chat V1 不是“全 Native Agent 替代路线”。它首先只为 Paynes Creek S03 的
`generate_image → image_id → inspect_image → 文本 verdict` 验证链服务。公众号、多 Agent 文案、
YouTube 频道图片理解和发布等能力继续使用现有路线或保持禁止，直到各自通过独立 Gate。

## 2. 为什么只改 `use_responses=False` 一定不够

### 2.1 模型 Step 会在第二轮冲突

当前代码把 `response.created.response.id` 写成模型 Step 幂等键：

```text
native:{run_id}:model:{response_id}
```

当前安装的 Agents SDK 在 Chat Completions 路径创建的 Response ID 固定为 `__fake_id__`。工具调用通常
至少有两个模型回合：第一轮请求 Tool，第二轮读取 Tool Output 并回答。两轮都会得到同一个伪 ID，第二个
模型 Step 因此会撞上第一个 Step 的唯一约束或错误复用第一步。

Chat chunk 的真实响应 ID 并非完全丢失：SDK 会把 `chunk.id` 放入完成 Output Item 的
`provider_data.response_id`。但它在 `response.created` 时尚不可用，所以不能继续把 Provider ID 当作
应用模型调用主键。

### 2.2 多个 Function Call 会覆盖参数缓冲

当前代码按 `item.id` 保存：

- Function Call metadata；
- arguments delta buffer；
- 最近 flush 时间。

Chat 兼容层给所有 Function Call Item 和参数 delta 同一个 `__fake_id__`。同一响应如果出现两个工具
调用，第二个会覆盖第一个。流事件虽然保留 `output_index`，Function Item 也保留真实 `call_id`，当前
代码却没有把它们作为映射主键。

### 2.3 当前代码等待一个 Chat 路径不会产生的事件

Native Agent 只在 `response.function_call_arguments.done` 上调用
`complete_function_call_arguments()`。当前 Chat Stream Handler 只发：

```text
response.output_item.added
response.function_call_arguments.delta
response.output_item.done
response.completed
```

它不会发 `response.function_call_arguments.done`。因此即使只有一个 Tool，参数完成事件也不会进入当前
持久化投影。

### 2.4 图片 Tool Output 不会被文本 Chat 模型看见

`generate_image` 当前返回一段文本 JSON 和一个 `ToolOutputImage`。Chat Converter 默认只保留 Function
Tool Output 中的文本部分；`deepseek-ai/DeepSeek-V3.2` 本身也是文本模型。开启严格校验也不会在
“文本 + 图片”组合上报错，因为文本部分仍然存在，图片会被过滤。

所以不能在产品语义上继续声称“Agent 已看到生成图”。SiliconFlow Chat V1 必须显式把
`generate_image` 输出收敛为文本事实（`image_id`、宽、高），随后强制调用本地 `inspect_image`，由视觉
Provider 返回文本 verdict、score 和 issue。Responses 路线继续保留当前图片 Tool Output。

## 3. 当前还存在的路由快照缺口

### 3.1 `AGENT_MODEL` 被两条运行链共享

`Settings.agent_model` 当前同时被以下路径使用：

- 旧 `AgentModelRouter` / `agent_runner.py`：火苗 → LIO Responses 路由；
- `native_agent_loop.py`：单一火苗 Responses Provider。

如果为了 Native Agent 把 `AGENT_MODEL` 改成 `deepseek-ai/DeepSeek-V3.2`，旧 Router 也会把这个模型名
发给火苗 / LIO。新实现不能改变该字段的历史语义。

### 3.2 Run 的模型快照没有真正控制执行

Run 创建时保存 `model_snapshot=settings.agent_model`，但执行 Loop、Workflow Compiler、Writer、
Reviewer、Agent 和 Trace 都继续读取当前 `resolved_settings.agent_model`。环境变量在排队、重启或恢复
之前改变时，Run 可能用不同于快照的模型执行。

Run 也没有保存 Provider 和 API 形状，Follow-up 只继承模型名。因此加入可选路由之前，必须先把路由
身份变成完整快照，并让执行只读该快照。

## 4. 配置与选择契约

### 4.1 使用原子 route ID

不要让 Provider 与 API shape 成为两个可以任意组合的环境变量。固定支持的 route ID：

| Route ID | Provider | API shape | 模型配置 | 凭据 / Base URL |
| --- | --- | --- | --- | --- |
| `huomiao_responses` | `huomiao` | `responses` | `NATIVE_AGENT_HUOMIAO_MODEL` | `TEXT_FALLBACK_*` |
| `siliconflow_chat_v1` | `siliconflow` | `chat_completions` | `NATIVE_AGENT_SILICONFLOW_MODEL` | `SILICONFLOW_*` |

新增配置建议：

```text
NATIVE_AGENT_DEFAULT_ROUTE=huomiao_responses
NATIVE_AGENT_HUOMIAO_MODEL=gpt-5.5
NATIVE_AGENT_SILICONFLOW_MODEL=deepseek-ai/DeepSeek-V3.2
```

现有 `AGENT_MODEL` 保留给旧 Agent Router，不作为 Native Agent 新字段的隐式 fallback。未知 route、空
模型、缺 API Key 或非法 route / model 组合必须在 Run 创建前明确失败。

### 4.2 Run 级显式选择

Native Agent Run 创建请求增加可选 `model_route`。首版只允许 Admin 显式选择非默认 route；未传时使用
`NATIVE_AGENT_DEFAULT_ROUTE`。这避免一次部署级切换把所有 Skill 一起迁移到尚未验证的 Chat 路线。

路由选择先经过 capability profile 校验，再创建 Run。校验失败不创建排队记录，也不自动改用默认
route。

## 5. 持久化模型

### 5.1 Run 快照

`native_agent_runs` 增加：

| 字段 | 作用 |
| --- | --- |
| `model_route_snapshot` | 原子 route ID |
| `model_provider_snapshot` | `huomiao` / `siliconflow` |
| `model_api_shape_snapshot` | `responses` / `chat_completions` |
| `model_snapshot` | 保留，改为真正的执行模型来源 |

迁移必须把所有历史 Run 回填为：

```text
model_route_snapshot=huomiao_responses
model_provider_snapshot=huomiao
model_api_shape_snapshot=responses
```

这是历史代码路径的事实回填，不根据当前 `.env` 猜测。回填完成后字段设为非空；当前没有按 route 查询
Run 的业务路径，不新增推测性索引。

Follow-up 必须原样继承四个模型快照字段。恢复执行只根据 Run 快照选择 Provider 和模型；环境配置只提供
该 route 当前凭据和 Base URL，不得覆盖模型。

### 5.2 模型 Step 可观测字段

模型 Step 增加或在等价结构化字段中持久化：

- `model_call_id`：应用生成的稳定调用身份；
- `model_provider`、`model_api_shape`、`model_name`；
- `provider_response_id`：Chat chunk ID 或 Responses response ID，可在流后段补写；
- `latency_ms` 与 usage；
- `execution_attempt`、当前 attempt 内模型调用序号。

API 的 `NativeAgentRunRead` 至少返回 route、provider、api shape 和 model；Step 详情应能区分应用调用 ID
与 Provider 请求 ID。密钥、Authorization、完整 Prompt 和 Tool 图片 data URL 不进入这些字段。

## 6. Provider 工厂与请求参数

### 6.1 Responses 路线

`huomiao_responses` 保持当前行为：

- `OpenAIProvider(use_responses=True)`；
- client 和 Runner retry 均为 0；
- `store=False`；
- 现有 Tool Output 形态不变。

### 6.2 SiliconFlow Chat V1

固定参数：

| 项目 | 值 | 原因 |
| --- | --- | --- |
| SDK Provider | `OpenAIProvider(use_responses=False)` | 使用官方公开 Chat API |
| strict feature validation | `true` | 不允许 SDK 静默忽略 Responses-only 能力 |
| streamed tool buffering | `false` | 首个 Gate 测真实流；失败即停，不自动换模式 |
| retry | client 0 / Runner 0 | 不重复消耗额度，不掩盖协议差异 |
| `store` | `None` | SDK 对非 OpenAI Base URL 会省略未设置字段；官方文档未列 `store` |
| `parallel_tool_calls` | `None` | 官方文档未列该字段；适配器仍需正确处理多个返回 Tool Call |
| `include_usage` | `None` | 不发送未公开的 `stream_options`；真实 Gate 必须观察 Provider 是否仍返回 usage |
| `enable_thinking` | `false`（`extra_body`） | 官方明确支持 V3.2；首 Gate 固定非思考模式，避免引入第二变量 |

SiliconFlow 官方 Chat API 文档列出了 `response_format` 与 `tools`，但没有在当前页面列出 `store`、
`parallel_tool_calls`、`stream_options` 或 `tool_choice`。V1 不主动发送未列出的可选参数；SDK 必需的
工具定义照常发送。

## 7. 内部事件适配器

新增一个 route-independent 的 `NativeModelEventAdapter`，把 SDK raw response events 转成应用内部事件。
持久化层不再直接依赖 SDK Response / Item ID 的唯一性。

### 7.1 模型调用身份

每次收到 `response.created` 时创建：

```text
model_call_id = native:{run_id}:attempt:{execution_attempt}:call:{ordinal}
```

它同时作为模型 Step 幂等身份。Provider response ID 是可空的外部关联字段：

- Responses：创建时即可记录真实 response ID；
- Chat：先为空，在 `output_item.done` 或 `response.completed.output[*].provider_data.response_id` 出现后补写；
- 永远不把 `__fake_id__` 存成 Provider response ID。

### 7.2 Function Call 身份

每个模型响应内部维护：

```text
output_index -> {tool_call_id, name, argument_buffer}
```

- `response.output_item.added`：读取真实 `call_id`，按 `output_index` 建立映射；
- `response.function_call_arguments.delta`：按事件 `output_index` 追加参数；
- 原生 `response.function_call_arguments.done`：按原语义完成；
- Chat `response.output_item.done`：读取 Item 中的最终 arguments，并合成内部
  `response.function_call.arguments.done`；
- 内部和 Tool Step 幂等继续使用 Provider `tool_call_id`，不使用 SDK Item ID。

完成时比较累计参数与 Item 最终参数；不一致直接失败并保留诊断事件，不选一个版本静默继续。

### 7.3 Provider request ID

Chat Stream Handler 会把真实 `chunk.id` 写进 Output Item 的 `provider_data.response_id`。适配器在
Item done 和 Response completed 时扫描并要求同一模型调用内所有非空值一致；不一致时失败。官方响应
头另提供 `x-siliconcloud-trace-id`，但当前 Agents SDK 流路径没有把该头暴露给应用，本版不伪造或要求
该字段。

## 8. Chat messages 边界

SiliconFlow 官方文档当前将 `messages` 数组写为 1–10 条。计数对象不是数据库 Item 数，而是 SDK
Converter 生成并插入 system message 后的最终 Chat messages：一次 Function Call 可能展开成 assistant
tool call 与 tool output 两条。

实现一个薄的 Chat Model wrapper，在每次实际请求前复用同一 Converter 计算最终数量：

- `<= 10`：允许继续；
- `> 10`：抛出明确 `NativeAgentChatMessageLimitError`；
- 不截断、不摘要、不删除 system、tool call 或 tool output；
- 记录 `converted_message_count`，不记录正文。

独立真实 Gate 可以故意发送 10 / 11 条无副作用请求以确认 Provider 行为；生产 route 在文档边界被解除
前仍以 10 条作为 fail-closed 上限。这个限制意味着 V1 是有界 S03 route，不是通用长对话兼容证明。

## 9. 工具能力 Profile

### 9.1 首个开放 Profile

`siliconflow_chat_v1` 首次只开放：

```text
profile: s03_image_inspection
tools: generate_image + inspect_image
article_workflow: false
```

约束：

1. Skill 含 `generate_image` 时必须同时含 `inspect_image`；
2. `generate_image` 对 Chat 路线只返回文本 JSON，不返回 `ToolOutputImage`；
3. instructions 明确要求每张生成图必须按 `image_id` 调 `inspect_image`；
4. `inspect_image` 返回 `accept` 前不得把图标记为可进入视频；
5. 当前 S03 Gate 仍限制最多一次生图调用，失败即停。

### 9.2 明确禁止

| 能力 | V1 决策 | 原因 |
| --- | --- | --- |
| `inspect_youtube_channel` | 禁止 | 当前契约承诺把头像和封面交给模型，Chat 文本模型看不到 Tool 图片 |
| 多 Agent 文章工作流 | 禁止 | Compiler / Director / Writer / Reviewer 的结构化输出、子 Agent 和消息量未 Gate |
| 仅 `generate_image`、不检查 | 禁止 | 主模型不能直接看图，不能自己判断质量 |
| 发布 YouTube | 禁止 | 路由兼容测试不能携带外部发布副作用 |
| 其他现有 Skill | 默认禁止 | 不从一个 S03 Gate 外推全平台兼容性 |

后续每开放一个 Profile，都要有独立协议 / 恢复 / 副作用 Gate，不能因为都是文本 Tool 就自动加入。

## 10. 测试矩阵

### Phase A：离线实现与聚焦测试

| 测试 | 必须证明 |
| --- | --- |
| route 解析 | 两个合法 route 可解析；未知组合、缺密钥、空模型明确失败；无 fallback |
| 旧 Router 隔离 | 修改 Native route / model 不改变 `AgentModelRouter` 的 `AGENT_MODEL` |
| Run 快照 | 创建后环境变化不改变执行 Provider、shape、model；Follow-up 完整继承 |
| 历史迁移 | 旧 Run 全部回填为 `huomiao_responses`；空库 upgrade 到 head |
| 两轮伪 ID | 两次 `__fake_id__` 产生两个不同模型 Step，均可完成 |
| 多 Tool 参数 | 相同 Item 伪 ID、不同 output index / call ID 不覆盖 |
| 参数完成 | Chat `output_item.done` 能合成唯一 arguments done；不一致明确失败 |
| Provider ID | 从 `provider_data.response_id` 补写真实 ID；`__fake_id__` 不入库 |
| Tool Output | Chat 的 `generate_image` 只返文本；Responses 保持文本 + 图片 |
| capability | 非 S03 Profile、缺 inspect、文章或 YouTube 看图在 Run 创建前失败 |
| message count | 转换后 10 条通过预检，11 条在生产 wrapper 明确失败；没有截断 |
| recovery | 已完成 Tool 不重复执行，新的 execution attempt / model call identity 不冲突 |
| API / trace | Run / Step 可读 route、provider、shape、model、request ID、usage、latency；无秘密 |

建议新增独立测试模块，而不是把 Chat 语义塞进历史 Responses 报告：

```text
backend/tests/test_native_agent_model_routes.py
backend/tests/test_native_agent_chat_event_adapter.py
backend/tests/test_native_agent_route_capabilities.py
```

### Phase B：真实零媒体 Gate

前提是用户明确批准一次小额 SiliconFlow 调用，并确认账号有 V3.2 可用额度。固定：

- `deepseek-ai/DeepSeek-V3.2`；
- 非思考模式；
- 一个确定性 `echo_probe` 本地 Tool；
- 临时数据库；
- 重试 0、fallback 0、媒体 Tool 0。

执行协议已进一步压缩为最多 5 次 Provider 请求：普通流式文本 1 次；单 Tool 两回合与跨 Python
子进程恢复合并为 2 次；转换后 10 条消息 1 次；测试专用 11 条 Provider 边界探针 1 次。随后核对
事件 / Step / Session、Tool 只执行一次和报告脱敏。Tool call ID、arguments、Provider response ID、
terminal event 和 usage 任一缺失，结论均为 `stop_before_media`。

完整固定输入、请求预算、进程恢复边界、11 条 test-only wrapper 绕过规则和机器可读空白记录见
[G3 零媒体 Gate 协议](../testing/siliconflow-native-agent-zero-media-gate-protocol.md)与
[G3 证据模板](../testing/siliconflow-native-agent-zero-media-gate-evidence-template.json)。协议准备完成不代表
G2 已实现或 G3 已获外部调用授权。

真实脚本应独立新增：

```text
scripts/check_siliconflow_native_agent_compatibility.py
docs/testing/siliconflow-native-agent-compatibility-report.json
```

不覆盖已有 Huomiao / LIO Responses 报告。

### Phase C：S03 单镜 Gate

只有 Phase B 得到 `pass_for_s03_single_image_review`，才能：

1. 使用既有 S03 Skill、Style 与 Prompt，新建显式 `siliconflow_chat_v1` Run；
2. 只允许一次 `generate_image(provider=qy)`；
3. 必须随后调用 `inspect_image`；
4. 记录图片真实宽高、对象、重建表达和字幕安全区；
5. `inspect_image=accept` 后仍需人工审核；
6. 任一失败停止，不重试、不换 Agent 模型、不生成 S01 或其余镜头。

## 11. 实施顺序与文件影响

### 实施 Sprint A：代码但无外部调用

为避免一次改动同时触及持久化事实、Responses 回归、Chat 事件和能力开放，Sprint A 拆成两个都通过后
才算完成的子 Gate：

#### G2-A：Run 路由快照基础

- Settings / `.env.example`：分离 Native 默认 route 与当前火苗模型，不从 `AGENT_MODEL` 回退；
- SQLAlchemy / Alembic：Run 增加 route / provider / API shape 非空快照，历史固定回填当前 Responses
  路径并保留原 `model_snapshot`；
- 新 Run、Follow-up、重试、恢复、文章角色、API 和 trace 统一只读四字段快照；
- Provider factory 在本切片只接受 `huomiao_responses`，不产生 Chat 路径；
- 完整范围和验收见 [Sprint 181 待批准合同](../contracts/sprint-181-native-agent-run-route-snapshot-foundation.md)。

#### G2-B：SiliconFlow Chat 有界适配

- 增加 Admin 显式 `siliconflow_chat_v1` 选择和独立模型配置；
- 模型 Step 观测字段、应用侧调用身份、Provider response ID 补写；
- Model wrapper / Event Adapter、Tool 参数完成合成；
- Chat Tool Output policy、S03 capability validator 与 10 条消息 wrapper；
- 独立合同只在 G2-A 完成后冻结和批准。

G2-A 通过不等于 G2 通过，也不能进入 G3。只有 G2-A 与 G2-B 的离线迁移、测试和文档全部通过，G2 才能
留下 `pass_offline` 证据。

### 实施 Sprint B：真实兼容性 Gate

- 新增独立脚本与脱敏报告；
- 只调用一个文本模型与本地 Tool；
- Gate 结论不自动修改默认 route。

### 实施 Sprint C：S03

- 只重做一张 S03；
- 不批量制作；
- 结果写回 S03 Gate 记录和 YouTube 研究日志。

## 12. 最终决策

```text
当前：g2a_contract_ready_for_user_approval
允许：先实施 Sprint 181 / G2-A（需用户明确批准）
禁止：真实模型调用、S03 生图、批量媒体、发布
```

这份蓝图修正了 Sprint 176 对 SDK 事件兼容面的低估，但不改变 `adapter_required` 总结论。它把下一步
从“试着换地址”变成了可以逐项验证的工程工作，同时把首条 YouTube 样片继续锁在一张 S03 的成本边界内。
