# Sprint 192：Native Agent SiliconFlow Chat 有界适配（G2-B）

状态：Complete（2026-08-13；G2-B 离线验证通过，未执行真实模型或媒体调用）

## Goal

在已完成的 G2-A Run 四字段路由快照基础上，实现一个只供管理员显式选择、只服务 S03 单镜图片检查闭环的
`siliconflow_chat_v1` Native Agent 路由。该路由必须通过应用侧稳定模型调用身份、Chat 流事件适配、最终
Chat messages 计数、文本化图片 Tool Output 和能力 Profile 消除 SDK `__fake_id__` 与协议差异，同时保持
现有 `huomiao_responses` 路径行为不变。

本 Sprint 完成后只允许把 G2 记录为 `pass_offline`；真实 SiliconFlow 兼容性仍由独立 G3 零媒体 Gate
验证，S03 生图仍由 G4 单镜 Gate 单独授权。

## In scope

### 路由配置与创建

- 新增独立配置 `NATIVE_AGENT_SILICONFLOW_MODEL=deepseek-ai/DeepSeek-V3.2`；凭据和 Base URL 只读取既有
  `SILICONFLOW_API_KEY / SILICONFLOW_BASE_URL`。
- `NATIVE_AGENT_DEFAULT_ROUTE` 在本阶段继续只允许 `huomiao_responses`，不能把未做真实 Gate 的 Chat
  路由设成全局默认。
- `NativeAgentRunCreate` 增加可选 `model_route`；未传时走 G2-A 默认路线。只有 Admin 可以显式选择
  `siliconflow_chat_v1`，普通用户请求该路线返回 403。
- SiliconFlow Route 创建前校验：
  - 模型精确为本轮唯一候选 `deepseek-ai/DeepSeek-V3.2`；
  - API Key 非空，Base URL 是无 userinfo、query、fragment 的合法 HTTP(S) URL；
  - Skill Tool 集合恰好为 `generate_image + inspect_image`；
  - Run 有可用 Style，且不携带创作账号、YouTube 发布频道、审核视频或发布确认。
- 任一校验失败不创建 Run、Item、Workflow 或 enqueue，也不自动改用火苗。

### Provider、请求参数与消息边界

- Provider 固定为 `OpenAIProvider(use_responses=False, strict_feature_validation=True,
  buffer_streamed_tool_calls=False)`；client 与 Runner retry 均为 0。
- Chat `ModelSettings` 固定：`store=None`、`parallel_tool_calls=None`、`include_usage=None`、
  `extra_body={"enable_thinking": false}`；不主动发送未在当前官方 Chat 文档列出的可选开关。
- 新增薄 Chat Model wrapper，使用当前锁定 SDK 的同一个 `Converter.items_to_messages()` 并在插入 system
  message 后计数：最终消息 `<=10` 才允许请求，`>10` 抛出明确
  `NativeAgentChatMessageLimitError`。
- 消息超限不得截断、摘要、删除 system / tool call / tool output，也不得发起 Provider 请求；只记录数量，
  不记录消息正文。

### 模型调用身份与事件适配

- `native_agent_steps` 为未来模型 Step 增加可空观测字段：
  - `model_call_id`
  - `model_provider`
  - `model_api_shape`
  - `model_name`
  - `provider_response_id`
  - `execution_attempt`
  - `model_call_ordinal`
  - `converted_message_count`
  - `latency_ms`
- 每次实际模型调用使用应用身份：
  `native:{run_id}:attempt:{execution_attempt}:call:{ordinal}`。它作为模型 Step 幂等身份；SDK
  `__fake_id__` 永不进入 `model_call_id` 或 `provider_response_id`。
- 新增 route-independent `NativeModelEventAdapter`：
  - 以 `output_index` 建立 Function Call 映射，以真实 `call_id` 作为 Tool 身份；
  - 参数 delta 按 output index 隔离，多个相同 SDK Item ID 不得覆盖；
  - Responses 原生 arguments done 保持原语义；Chat 在 `response.output_item.done` 合成唯一内部 done；
  - 累计参数与 done Item 最终参数不一致时明确失败；
  - 从 Item / completed output 的 `provider_data.response_id` 补写 Chat Provider ID，同一调用出现多个不同
    ID 时明确失败；
  - Responses 继续使用真实 response ID，但模型 Step 同样改用应用 `model_call_id`。
- API Step 投影返回上述安全观测字段；Event 继续兼容现有前端的 `response_id` 字段，但其值改为稳定
  `model_call_id`，另行返回可空 `provider_response_id`。

### S03 Tool 与完成边界

- Chat 路由的 `generate_image` 成功和幂等重放只向模型返回文本 JSON：`status / image_id / width /
  height`，不得 materialize 或回传 `ToolOutputImage` / data URL。Responses 路径保持文本加图片输出。
- Chat 路由同一 Run 最多允许一次新的 `generate_image` Provider attempt；失败后不得在同一 Run 通过新
  Tool Call ID 或 retry-latest 再次请求图片。
- Route instructions 必须明确要求生成后按 `image_id` 调用 `inspect_image`；Run 只有在一张图片对应的
  `inspect_image` 已得到真实终态 verdict 后才能正常完成。`accept` 仍只是进入后续视频 Gate 的条件，
  不能在本 Sprint 自动解释为人工审核通过。
- Follow-up 继续继承四字段 Route 快照，但 `siliconflow_chat_v1` 的 S03 Run 不允许通过 Follow-up 绕过
  单镜预算；请求必须明确拒绝且不创建子 Run。

### 数据、文档与回归

- 新增一个 Alembic revision；历史模型 Step 的新观测字段保持 `NULL`，不根据旧 Event 或
  `output_ref_json` 伪造调用身份、attempt、消息数或延迟。
- 新字段无 server default；只为 `model_call_id` 建唯一约束保护应用调用身份，不增加推测性查询索引。
- 更新 `.env.example`、规格、出站端点文档、SiliconFlow 蓝图、Paynes Creek 控制室与项目进度。
- 使用合成 SDK 事件和 Fake Provider 完成全部测试；外部请求计数必须为 0。

## Out of scope

- 不调用 SiliconFlow、火苗、图片、VL、TTS、Whisper、Remotion、YouTube、发布或账单接口。
- 不创建或执行 G3 兼容性脚本，不填写真实证据报告，不读取账号余额或免费额度。
- 不生成或重试 S03，不创建 S01–S12 任何媒体，不修改 Style、Prompt、旁白或选题。
- 不把 `siliconflow_chat_v1` 设为默认 Route，不给普通用户或所有 Skill 开放，不新增前端模型选择器。
- 不开放公众号、多 Agent 文案、YouTube 频道研究、语音、字幕、视频或发布 Tool。
- 不升级 `openai-agents` / `openai`，不修改 vendor SDK 源码，不引入新的运行时依赖。
- 不增加 fallback、自动模型切换、Provider retry、stream buffer、上下文截断、摘要、占位结果或静默忽略。
- 不把 G2 离线通过写成真实 Provider 兼容、S03 可制作、市场验证或发布许可。

## Deliverables

- `backend/app/services/native_agent_model_routes.py`
- `backend/app/services/native_agent_chat.py`
- `backend/app/services/native_agent_model_events.py`
- `backend/app/services/native_agent_loop.py`
- `backend/app/services/native_agent_persistence.py`
- `backend/app/api/native_agent.py`
- `backend/app/schemas/native_agent.py`
- `backend/app/models/entities.py`
- 新 Alembic revision。
- `backend/tests/test_native_agent_chat_model.py`
- `backend/tests/test_native_agent_model_events.py`
- `backend/tests/test_native_agent_route_capabilities.py`
- 对现有 Native route / loop / follow-up / recovery 测试的最小必要更新。
- 项目规格、端点、控制室、研究日志与进度文档。

## Done means

### 创建与能力 Profile

- 未传 Route 的普通用户 Run 仍快照并执行 `huomiao_responses`。
- Admin 显式选择 SiliconFlow 时一次性写入
  `siliconflow_chat_v1 / siliconflow / chat_completions / deepseek-ai/DeepSeek-V3.2`。
- 普通用户、未知 Route、错误模型、缺凭据、非法 URL、Tool 集不精确、缺 Style 或携带发布上下文时，
  HTTP 403 / 409 / 503 明确返回，数据库与 enqueue 无新增。
- 旧 `AgentModelRouter` 继续只读 `AGENT_MODEL`；现有 SiliconFlow 文本、视觉和语音调用继续读各自旧字段。

### Chat 请求与事件

- Fake client 捕获到 `chat.completions` 路径、严格校验、非缓冲工具流、0 retry、关闭 thinking 和未发送
  `store / parallel_tool_calls / stream_options` 的有效语义。
- 最终 10 条消息通过 wrapper；11 条在 client 调用前失败，输入项逐项不变。
- 两个连续 `__fake_id__` response 产生两个不同模型 Step；Provider ID 从 `provider_data` 补写且伪 ID
  不入库。
- 同一模型回合两个 Function Call 即使 Item ID 相同，也按 output index / call ID 保存各自完整参数和唯一
  done 事件。
- Chat `output_item.done` 能合成 arguments done；累计与最终参数不同、缺 call ID、重复 output index、
  Provider ID 冲突或 completed 前未完成 Function Call 都让 Run 明确失败。
- Responses 现有文本流、Tool 参数、usage、Session 重放与完成状态回归通过。

### S03 安全边界与恢复

- Chat 图片成功 / 重放只产生文本 Tool Output；测试断言 `_completed_image_url` 未调用。Responses 仍含图片。
- 第二个新图片 Tool Call 和失败后的同 Run retry 在图片 Provider 前失败；已有成功 Tool 的同一
  idempotency replay 仍只复用数据库资产。
- 缺少 `inspect_image` 终态时 Run 不能成功；存在 verdict 时可以按真实结果结束，但不会写人工审核通过。
- retry / startup recovery 保持原 Route、模型、execution attempt 与新 model call identity 不冲突；已成功
  Tool 不重复执行。
- SiliconFlow S03 Run 的 Follow-up 被拒绝且无子 Run；Responses Follow-up 行为不变。

### 数据、API 与安全

- 空库升级到新 head；从 `v3w4x5y6z7a8` 升级时历史模型 Step 新字段全为 NULL，旧 Run / Step / Event /
  Session 内容逐字不变；downgrade 可恢复。
- 新模型 Step 持久化 route、provider、shape、model、应用调用 ID、Provider ID、attempt、ordinal、消息数、
  latency 与 usage；API 能读取，默认 trace / Event 不含密钥、Authorization、Base URL、完整 Prompt、消息
  正文或图片 data URL。
- `git diff --check`、内容控制器状态、聚焦测试与完整仓库检查全部通过。

## Verification

```powershell
$env:PYTHONPATH='backend'
& backend/.venv/Scripts/python.exe -m unittest `
  backend.tests.test_native_agent_chat_model `
  backend.tests.test_native_agent_model_events `
  backend.tests.test_native_agent_route_capabilities `
  backend.tests.test_native_agent_model_routes `
  backend.tests.test_native_agent_follow_up `
  backend.tests.test_native_agent_loop

& backend/.venv/Scripts/python.exe -m unittest discover -s backend/tests
& backend/.venv/Scripts/python.exe -m compileall backend/app backend/alembic/versions
npm test --prefix frontend
npm run build --prefix frontend
npm run typecheck --prefix remotion
npm test --prefix remotion
& backend/.venv/Scripts/python.exe `
  .agents/skills/content-iteration-controller/scripts/validate_controller_state.py
git diff --check
```

Migration verification:

1. 空临时 SQLite 执行 `upgrade head`，核对新 head、字段、NULL/default、唯一约束与无额外索引。
2. 第二个临时库先停在 `v3w4x5y6z7a8`，插入 Responses 历史模型 Step 与 Event / Session，再升级；核对
   新字段全 NULL 且旧内容不变。
3. 对第二个临时库 downgrade 到 `v3w4x5y6z7a8`，确认只移除 G2-B 字段与约束。

## Handoff

- G2-B 离线实现与全部验证通过后，把 G2 记录为 `pass_offline`，但 Route 默认值仍保持火苗。
- 下一步不是生图，而是按 Sprint 180 协议创建测试专用兼容性脚本和脱敏报告；真实执行必须再次获得
  明确的小额外部调用授权。
- 只有 G3 得到 `pass_for_s03_single_image_review`，才允许 G4 新建一轮只生成一张 S03 候选的 Run；
  任一失败保持 `stop_before_media`。

## Verification record（2026-08-13）

- 聚焦 Chat / Event / capability 测试 11 项通过；受影响 Native route / follow-up / loop 共 59 项通过。
- 完整后端 398 项通过；Python `compileall` 通过。
- 空 SQLite 升级到 `w4x5y6z7a8b9`；从 `v3w4x5y6z7a8` 插入历史模型 Step / Event / Session 后升级，
  9 个新观测字段全为 `NULL` 且旧内容逐字不变；降级后仅移除新字段与约束。
- 当前本地开发库已升级到 `w4x5y6z7a8b9 (head)`。
- frontend 14 项与 production build、Remotion 5 项与 typecheck、内容控制器状态和 `git diff --check` 通过。
- 全过程使用合成 SDK 事件、MockTransport 与 Fake Provider；火苗、SiliconFlow、图片、VL、TTS、Whisper、
  Remotion、YouTube、发布与账单外部请求均为 0。
