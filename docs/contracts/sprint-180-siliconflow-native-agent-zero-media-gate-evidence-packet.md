# Sprint 180：SiliconFlow Native Agent 零媒体 Gate 证据包

状态：Complete（文档与空白证据模板；G2 未实施，G3 未授权、未运行）

## Goal

把 SiliconFlow Native Agent 的 G3 真实兼容性验证收敛成一轮小额、零媒体、可审计的未来执行合同：
固定前置 G2 证据、唯一模型、请求上限、确定性本地 Tool、进程级恢复、10 / 11 条消息边界、通过条件和
脱敏记录，使后续真实调用既能证明 S03 所需的 Chat Tool Loop，又不会扩张为媒体或通用 Agent 兼容声明。

## In scope

- 对照 Sprint 176 / 177 决策、当前 Native 持久化模型和已安装 Agents SDK，固定 G3 的可观测字段。
- 将普通流式文本、单 Tool 两回合、进程级恢复、事件投影和 10 / 11 条消息边界压缩为最多 5 次
  SiliconFlow Chat Completions 请求。
- 定义测试专用 `echo_probe` 的确定性输入、输出和执行次数，不注册任何媒体或发布 Tool。
- 定义成功请求必须记录的应用模型调用 ID、Provider response ID、Tool call ID、arguments、terminal
  event、usage、Step / Event / Session 对应关系和转换后消息数。
- 输出 Markdown 执行协议与所有观测值为空的 JSON 证据模板。
- 同步架构蓝图、兼容性决策、首片生产控制室、S03 重试协议、索引、研究日志、根 README 与进度。

## Out of scope

- 不批准、实现或验收 G2，不修改 Settings、API、Schema、模型、迁移、Provider、Event Adapter 或测试代码。
- 不创建 `check_siliconflow_native_agent_compatibility.py`，不建立临时 Run 或真实兼容性报告。
- 不读取 SiliconFlow 私有账单，不调用 SiliconFlow、火苗、图片、VL、TTS、字幕、视频或发布接口。
- 不把 `echo_probe` 注册为生产 Tool，不打开 S03、文章、YouTube 看图或发布能力。
- 不修改默认 Native route，不切换模型，不启用 thinking、重试、fallback、stream buffer、截断或摘要。
- 不把协议准备度写成 G3 通过、S03 可生图、全 Agent 兼容或市场验证结论。
- 不更新 `strategy_memory.md` 或内容 Skill。

## Deliverables

- `docs/testing/siliconflow-native-agent-zero-media-gate-protocol.md`
- `docs/testing/siliconflow-native-agent-zero-media-gate-evidence-template.json`
- Sprint 177 蓝图、Sprint 176 决策、Paynes Creek 控制文档和项目索引 / 进度更新。

## Done means

- 操作者能准确判断何时允许 G3，单次最多产生多少外部请求，以及任一失败后为何必须停止。
- 普通流、Tool + 恢复、10 条和 11 条边界四个用例的输入、调用数、观测字段和 verdict 均明确。
- Tool + 恢复用例在两个 Python 子进程间完成，`echo_probe` 只执行一次，两个模型调用身份和 Provider
  response ID 均不同，且 `__fake_id__` 不进入持久化事实。
- 10 条消息必须通过生产 wrapper；11 条只允许在测试脚本中绕过生产上限探测 Provider，接受或拒绝都
  必须形成完整证据，生产 route 仍保持 10 条 fail-closed 上限。
- JSON 未运行字段全部为 `null` 或 `not_run`，不含伪造 ID、usage、成本、余额、错误或通过结论。
- Gate 只能得到 `pass_for_s03_single_image_review` 或 `stop_before_media`；通过也只开放 G4 单图授权评审。

## Verification

```powershell
Get-Content docs/testing/siliconflow-native-agent-zero-media-gate-evidence-template.json -Raw |
  ConvertFrom-Json | Out-Null
rg -n "siliconflow_chat_v1|echo_probe|provider_request_budget|messages_10|messages_11" `
  docs/testing/siliconflow-native-agent-zero-media-gate-*
git diff --check
```

Manual or QA checks:

- 对照适配蓝图 Phase B 与兼容性决策第 8 节，确认没有降低既有通过门槛。
- 对照当前 Native Run / Step / Event / Session 字段和 Agents SDK `0.18.3` Chat 事件，确认模板字段可追溯。
- 检查 5 次请求上限、重试 / fallback / thinking / stream buffer 为固定关闭，不存在隐含外部调用。
- 检查本地链接、敏感信息、JSON 空白状态和内容控制器状态。
- 确认工作树没有运行时代码、配置、数据库、策略记忆或 Skill 改动。

## Risks / notes

- G3 依赖 G2 新增的 route 快照、事件适配、消息 wrapper 和兼容性脚本；当前仓库没有这些实现。
- 11 条边界探针必须由测试脚本显式绕过生产 wrapper，否则只能证明本地预检，不是 Provider 行为。
- 11 条被 Provider 拒绝仍可满足“行为已记录”，但必须有 HTTP 状态、错误码和 request / trace 标识；
  证据不足时仍是 `stop_before_media`。
- Provider 接受 11 条也不会自动提高生产上限；需等官方文档或独立评审改变当前 10 条边界。
- 公开价格不等于账号实际可用额度，执行前仍需人工确认本次最多 5 个请求的成本上限。

## Handoff

- 下一步先由用户明确批准 [Sprint 181 / G2-A 路由快照基础](sprint-181-native-agent-run-route-snapshot-foundation.md)。
  G2-A 只冻结当前 Responses 路由，完成后仍需另行批准 G2-B；两者都通过后，才填写本模板的授权和成本
  字段并请求 G3 外部调用批准。本 Sprint 不自动进入任何实施或真实调用。
