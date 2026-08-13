# Sprint 176：SiliconFlow Native Agent 兼容性决策

状态：Complete（`adapter_required`；Sprint 177 已补充事件身份适配要求，真实兼容性 Gate 未执行）

## 背景

Sprint 175 的 Paynes Creek S03 单镜媒体 Gate 在第一轮 Native Agent 规划请求处停止：当前火苗
`gpt-5.5` Responses 路径返回 HTTP 429 `usage_limit_reached`，没有发生图片调用。用户已限定
SiliconFlow 只能使用一组具有账号免费额度的模型，其中当前 `SILICONFLOW_MODEL` 为
`deepseek-ai/DeepSeek-V3.2`。在重新制作 S03 前，需要先判断这个模型能否承担 Native Agent 的多轮
Tool Loop；不能只把 Base URL 和模型名替换后继续运行。

## Goal

只通过当前仓库代码、已安装 Agents SDK 源码和 SiliconFlow 官方公开文档，判断 SiliconFlow 与
DoodleStory Native Agent 属于“直接配置兼容”“需要显式适配器”还是“不支持”，并把下一次最小真实
兼容性 Gate 写成可执行边界。

## 决策

结论为 `adapter_required`：

- 当前 Native Agent 固定使用 `POST /responses`；SiliconFlow 官方公开入口为
  `POST /v1/chat/completions`，不能直接替换配置。
- SiliconFlow 官方模型中心将 `deepseek-ai/DeepSeek-V3.2` 标为支持工具调用；官方 Function Calling
  指南通过 Chat Completions 展示工具请求、工具结果回传和第二轮回答。
- 当前已安装的 OpenAI Agents SDK 可以用 `OpenAIProvider(use_responses=False)` 建立
  `OpenAIChatCompletionsModel`，并把 Chat Completion 流转换为一部分 `response.*` 事件；后续完整审计
  发现它复用固定 `__fake_id__` 且不发当前持久化代码等待的 arguments done，不能直接接入现有事件处理器。
- SiliconFlow Chat Completions 文档把 `messages` 数组记录为 1–10 条，而当前 Native Agent 数据库
  Session 会完整重放全部上下文，且最多运行 12 个模型回合。是否为真实硬限制、工具流分片是否完全兼容，
  都必须通过真实调用验证；静态审计不能将其升级为生产兼容。

完整证据和 Gate 设计见
`docs/integrations/siliconflow-native-agent-compatibility-decision.md`。

## In scope

- 审计 `config.py`、`native_agent_loop.py`、`native_agent_persistence.py`、旧 `AgentModelRouter` 和既有
  兼容性检查脚本，记录 Native Agent 当前实际地址、API 形状、模型和重放方式。
- 审计仓库实际安装的 `openai-agents==0.18.3` Chat Completions Provider、消息转换器与流事件转换器。
- 核对 SiliconFlow 官方 API 索引、Chat Completions、Function Calling、模型中心和价格页。
- 只把用户允许清单内、且当前已配置的 `deepseek-ai/DeepSeek-V3.2` 选为第一兼容性 Gate 候选；其他
  允许模型只保留为后续候选，不在本 Sprint 排名或调用。
- 输出直接配置、SDK 适配、多轮上下文、工具流、成本与当前制作 Gate 的决策矩阵。
- 定义下一次只使用一个模型、一个无副作用本地工具、零媒体调用、零自动切换的真实兼容性 Gate。

## Out of scope

- 不修改 `.env`、模型路由、Provider 选择、Native Agent 代码或 Agents SDK 版本。
- 不调用 SiliconFlow 的任何模型推理接口，不读取私有账单、余额或账号优惠，不消耗模型额度。
- 不重试 Sprint 175，不生成 S03、其他图片、语音、字幕或视频，不发布 YouTube 内容。
- 不新增 fallback、自动 Provider 切换、上下文截断、摘要压缩、静默忽略或兼容性降级。
- 不把用户允许清单描述成 SiliconFlow 对所有账号永久免费的公开价格承诺。
- 不改变 Sprint 105 已锁定的持久化、完整输入重放或错误分类契约。

## Done means

- 能从代码定位 Native Agent 的真实请求为火苗 `/v1/responses`，并证明 `SILICONFLOW_*` 当前没有参与
  该路径。
- 能从 SiliconFlow 官方公开目录证明 Chat Completions 与 Function Calling 是公开接入形状，且没有
  把未公开的 Responses 支持当成事实。
- 能从已安装 SDK 源码证明 Chat Completions 模式会产生
  `response.output_item.added`、`response.function_call_arguments.delta` 和 `response.completed`，并明确
  这些事件仍不足以满足当前模型 Step / Function 参数持久化契约。
- 明确记录官方 `messages` 1–10 条约束与当前完整 Session 重放 / 12 回合上限之间的风险。
- 输出唯一结论 `adapter_required`，同时把“静态可适配”与“真实生产兼容”分开。
- 下一 Gate 固定一个候选模型、一个本地确定性工具、明确通过 / 停止条件，不包含媒体 Tool 或 fallback。

## Verification

- 逐项核对官方链接与文档中的端点、工具调用、消息条数、模型 ID 和当前公开价格状态。
- 读取仓库当前安装版本的 `openai_provider.py`、`openai_chatcompletions.py`、
  `chatcmpl_converter.py` 和 `chatcmpl_stream_handler.py`，不依据另一版本 SDK 推断。
- 检查本轮新增链接、Markdown 格式、敏感信息新增、内容迭代控制器状态与 `git diff --check`。
- 本 Sprint 仅改文档，不运行模型兼容性脚本或媒体测试；真实 API 结果明确标记为未验证。

## Handoff

Sprint 177 已把实现范围细化为 Run 级 route 快照、应用侧模型调用 ID、按 output index / call ID 的
工具参数映射、Chat 工具输出 policy 和消息计数 wrapper，见
`docs/architecture/siliconflow-native-agent-adapter-blueprint.md`。用户批准后应先完成离线实现与聚焦测试，
再执行本文定义的真实兼容性 Gate。只有 Tool Loop、流事件、完整持久化重放以及 10 条消息边界全部得到
明确结果，才能决定是否允许 S03 继续使用该路由；不得自动截断、摘要或切换模型。
