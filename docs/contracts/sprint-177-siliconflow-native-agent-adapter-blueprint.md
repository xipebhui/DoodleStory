# Sprint 177：SiliconFlow Native Agent 适配实施蓝图

状态：Complete（设计完成；运行时代码与真实兼容性 Gate 未授权、未执行）

## 背景

Sprint 176 将 SiliconFlow Native Agent 判定为 `adapter_required`，但当时只确认了 Chat
Completions Provider 可以生成类似 Responses 的流事件。继续审计当前安装的
`openai-agents==0.18.3` 后发现，SDK 的 Chat 兼容层会为每次模型响应和每个输出 Item 复用固定
`__fake_id__`，且不会发出当前持久化代码等待的
`response.function_call_arguments.done`。如果只切换 `use_responses=False`，第二次模型调用会与第一步
幂等键冲突，多工具参数流也会因为同一个 Item ID 相互覆盖。

与此同时，当前 `AGENT_MODEL` 同时供旧 `AgentModelRouter` 和 Native Agent 使用；Run 只保存模型名，
执行时却使用当前环境模型而不是 Run 快照。直接把全局模型改成 DeepSeek 会同时改变旧 Router，并让排队
或恢复中的 Run 发生路由漂移。

## Goal

只通过当前仓库代码、数据库模型、已安装 SDK 源码与 SiliconFlow 官方文档，形成一份可直接进入实现
评审的适配蓝图：明确配置隔离、Run 快照、事件身份、工具输出、消息边界、能力 Gate、数据迁移、测试矩阵
与 S03 单镜恢复顺序。

## In scope

- 逐项审计 Native Agent 的 Provider 构造、Run 创建、Follow-up、模型 Step 幂等键、Function Call 参数
  流、工具输出和 API 投影。
- 逐项审计当前安装的 Chat Completions 模型、Converter 和 Stream Handler，而不是依据其他 SDK 版本。
- 设计独立 Native Agent 路由配置，不复用或改写旧 Router 的 `AGENT_MODEL` 语义。
- 设计 Run 级 Provider / API 形状 / 模型快照，以及历史行回填与 Follow-up 继承规则。
- 设计不依赖 SDK 伪 ID 的内部事件身份与参数完成语义。
- 设计 SiliconFlow Chat V1 的工具能力边界：首个生产候选只允许 S03 的
  `generate_image + inspect_image` 闭环。
- 设计无媒体真实兼容性 Gate 和通过后的 S03 单镜 Gate；两者不能合并。
- 输出 Markdown 架构蓝图和独立 SVG / PNG 架构图。

## Out of scope

- 不修改 `.env`、Settings、数据库、API、Provider、Native Agent 或 Agents SDK 代码。
- 不调用 SiliconFlow、火苗、图片、视觉、TTS、字幕、视频或发布接口，不读取账号余额。
- 不重试 S03，不生成图片、音频、字幕或视频，不创建或发布 YouTube 内容。
- 不增加 fallback、自动模型切换、重试、上下文截断、摘要、占位工具结果或静默丢弃。
- 不把 Chat 路由开放给公众号文章、多 Agent 文案、YouTube 频道看图或所有现有 Skill。
- 不修改 Sprint 105 已锁定的旧 Router 错误分类与应用数据库完整重放契约。

## Done means

- 明确记录 Chat 兼容层固定 `__fake_id__`、真实 Provider response ID 所在位置，以及缺少参数 done 事件
  对当前代码造成的具体失败方式。
- 明确记录 `AGENT_MODEL` 共享、Run 路由快照缺失、执行时模型漂移和 Follow-up 继承不完整问题。
- 定义原子 route ID、分路由模型配置、Run 快照、迁移回填和 API 可见字段，且没有隐式 fallback。
- 定义应用侧 `model_call_id`、`output_index → tool_call_id` 映射和
  `output_item.done → arguments.done` 合成规则。
- 明确 Chat 路由不能让文本模型直接看 Function Tool 返回的图片；S03 必须通过 `image_id` 再调用
  `inspect_image` 获取文本检查结果。
- 明确官方 1–10 条消息边界必须按 SDK 转换后的最终 Chat messages 计算；超限明确失败，不截断。
- 输出分阶段实施顺序、聚焦测试矩阵、真实 Gate 通过 / 停止结论和 S03 恢复条件。

## Verification

- 对照 `native_agent_loop.py`、`native_agent_persistence.py`、`native_agent.py`、
  `native_agent_follow_up.py`、SQLAlchemy 实体和 Pydantic Schema。
- 对照安装目录中的 `openai_provider.py`、`openai_chatcompletions.py`、
  `chatcmpl_converter.py`、`chatcmpl_stream_handler.py` 和 `chatcmpl_helpers.py`。
- 对照 SiliconFlow 官方 Chat Completions、Function Calling 与公开 API 索引。
- 检查 SVG 结构、PNG 转换结果、Markdown 链接、敏感信息新增、`git diff --check` 和内容控制器状态。
- 本 Sprint 只验证设计证据，不把文档检查冒充代码、迁移或真实 Provider 验收。

## Handoff

用户明确批准实现后，下一 Sprint 只做蓝图 Phase A：配置隔离、Run 快照、事件适配、能力校验、迁移与
离线聚焦测试；不调用真实模型。Phase A 通过后，再由用户批准一次小额 SiliconFlow 调用，执行独立
零媒体 Gate。只有该 Gate 结论为 `pass_for_s03_single_image_review`，才创建一轮只允许生成一张 S03
候选的媒体 Gate。
