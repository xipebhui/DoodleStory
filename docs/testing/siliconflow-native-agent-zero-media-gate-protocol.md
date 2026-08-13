# SiliconFlow Native Agent G3 零媒体真实兼容性 Gate 协议

更新时间：2026-08-12<br>
状态：`protocol_ready / g2_not_implemented / not_authorized / not_run`<br>
适用范围：`siliconflow_chat_v1` 首次真实 Provider 兼容性验证

配套空白记录：[G3 证据模板](siliconflow-native-agent-zero-media-gate-evidence-template.json)

## 一句话边界

G3 只回答一个问题：完成 G2 后，`deepseek-ai/DeepSeek-V3.2` 能否在 DoodleStory 的有界 Chat 路由中
稳定完成文本流、一个确定性 Tool、持久化恢复和 10 条消息请求。

它不生成图片，不调用 S03，不开放生产默认路由，也不证明文章、多 Agent、YouTube 看图、发布或长对话
兼容。当前代码仍固定走火苗 Responses，G2 尚未实施，所以这份文件是未来执行协议，不是测试报告。

## 1. 当前与目标状态

```text
当前仓库
  Native Provider                 huomiao / responses
  model_route snapshot            不存在
  Chat event adapter              不存在
  converted message wrapper       不存在
  G3 compatibility script         不存在
  G3 Provider calls               0

G3 执行前目标
  G2 offline result               pass_offline
  route                           siliconflow_chat_v1
  provider / API shape            siliconflow / chat_completions
  model                           deepseek-ai/DeepSeek-V3.2
  registered tool                 echo_probe only
  media / publish tools           0
```

## 2. 开 Gate 前的硬前置条件

以下条件必须全部有当前 commit 可追溯证据：

1. G2 离线实现已经提交，结论为 `pass_offline`，迁移处于 head，聚焦测试全部通过。
2. Run 已能快照并返回 `model_route / provider / api_shape / model`，执行与 Follow-up 只读快照。
3. Chat Event Adapter 已用应用侧 `model_call_id` 取代 SDK 伪 Response ID，并能按
   `output_index → tool_call_id` 完成参数投影。
4. Chat `output_item.done` 已能合成唯一 arguments done；累计参数与最终参数不一致会明确失败。
5. 生产 wrapper 按 SDK Converter 最终结果计算消息数，`<=10` 放行、`>10` 明确失败，不截断或摘要。
6. `siliconflow_chat_v1` capability profile 仍只开放 S03 图片生成 + 检查；G3 脚本使用测试专用
   `echo_probe`，不把该 Tool 注册到生产能力表。
7. 用户单独批准 G3 外部调用，确认最多 5 次 Chat 请求、成本上限和当前账号 V3.2 可用额度。
8. 执行环境、脚本 SHA-256、G2 commit、Python / SDK 版本、临时数据库位置指纹和报告路径已冻结。

缺少任一项时把记录写为 `blocked_precondition`，不得创建临时 Run 或发外部请求。

## 3. 固定 Provider Profile

| 项目 | G3 固定值 |
| --- | --- |
| Route | `siliconflow_chat_v1` |
| Provider | `siliconflow` |
| API shape | `chat_completions` |
| Model | `deepseek-ai/DeepSeek-V3.2` |
| Agents SDK | `openai-agents==0.18.3` |
| OpenAI client | `openai==2.45.0` |
| Thinking | `false` |
| Streaming | `true` |
| Strict feature validation | `true` |
| Streamed tool buffering | `false` |
| Client / Runner retry | `0 / 0` |
| Fallback | 无 |
| `store` / `parallel_tool_calls` / `include_usage` | 不主动发送 |
| Database | 每次 Gate 新建临时本地 SQLite；不得使用生产库 |
| Tool | 仅测试进程内 `echo_probe` |
| 图片 / VL / TTS / 字幕 / 视频 / 发布 | 全部不注册、调用数必须为 0 |

任一固定值变化都算新变量，必须停止并另建 Gate，不能在同一次脚本里自动尝试第二种配置。

## 4. 请求预算

G3 将恢复重放合并进单 Tool 两回合，外部请求上限固定为 5：

| Case | 用途 | Provider 请求上限 |
| --- | --- | ---: |
| Z1 | 普通流式文本 | 1 |
| Z2 | 第一次模型调用 Tool；持久化后跨进程恢复；第二次模型调用最终回答 | 2 |
| Z3 | 生产 wrapper 下转换后恰好 10 条消息 | 1 |
| Z4 | 测试脚本专用的 11 条 Provider 边界探针 | 1 |
| **总计** |  | **5** |

脚本启动前必须显示预算并要求显式外部调用确认。达到 5 次后无论状态如何都停止；连接超时、429、5xx、
空流、解析错误和 Provider 拒绝均不重试。

## 5. 唯一测试 Tool

`echo_probe` 不读文件、不访问网络、不写生产数据，也不使用时间、随机数或环境变量参与输出。

输入：

```json
{
  "probe_id": "g3-echo-01",
  "value": "PAYNES-CREEK-G3"
}
```

确定性输出：

```json
{
  "probe_id": "g3-echo-01",
  "echo": "PAYNES-CREEK-G3"
}
```

Schema 必须 `extra=forbid`；两个字段都是非空字符串。Tool Step 的输入、输出和执行次数写入临时数据库。
整个 Z2 中执行次数必须恰好为 1。

## 6. 四个执行用例

### Z1：普通流式文本

发送一个短、确定性的文本请求，要求最终回答包含固定 marker `G3-TEXT-OK`。通过必须同时证明：

- 至少一个非空文本 delta；
- 唯一 terminal completed event；
- 非 `__fake_id__` 的 Provider response ID；
- 应用侧 `model_call_id`、成功模型 Step 和一次请求 usage；
- Run 终态成功，转换后消息数已记录；
- 没有 Tool、媒体、fallback 或 retry 事件。

空文本、缺 terminal、缺 usage、缺 Provider ID 或出现第二次请求都立即 `stop_before_media`。

### Z2：单 Tool 两回合 + 进程级恢复

这个用例使用同一临时数据库，由父脚本启动两个独立 Python 子进程：

1. 子进程 A 创建临时 Run，发第一次模型请求；模型必须只调用一次 `echo_probe`。
2. 适配器保存唯一 Tool call ID、完整合法 JSON arguments 和唯一 arguments done。
3. 应用执行 `echo_probe` 一次并持久化 Tool Output；子进程 A 在第二次模型请求前正常退出，阶段状态写为
   `paused_after_tool_commit`。
4. 子进程 B 只从临时数据库恢复同一 Run / Session，不继承子进程 A 的内存对象。
5. 恢复逻辑确认已完成 Tool 不再执行，向模型发第二次请求；最终文本必须同时包含
   `G3-TOOL-OK` 和 `PAYNES-CREEK-G3`。

通过还必须满足：

- 两个应用 `model_call_id` 不同，两个 Provider response ID 不同且都不是 `__fake_id__`；
- Tool call ID 在 Function Call、arguments、Tool Output 和 Session 重放中一致；
- arguments delta 合并值与 `output_item.done` 最终 arguments 完全一致；
- 模型 Step 2 个、Tool Step 1 个、Tool 实际执行 1 次；
- 两次成功请求各有 terminal event 和 usage；
- 恢复后的 Session 没有丢失、复制或重排 user / assistant tool call / tool output；
- 没有第三次请求，没有媒体或发布 Tool。

进程 B 启动失败、Tool 被重复执行、任何 ID 冲突、参数不一致或恢复后模型看不到 Tool Output 都立即停止。

### Z3：转换后 10 条消息

使用与生产 route 完全相同的 Converter 和消息计数 wrapper 构造最终恰好 10 条 Chat messages。请求不含
Tool 或媒体，要求固定 marker `G3-MSG10-OK`。通过条件：

- wrapper 记录 `converted_message_count=10` 并允许请求；
- Provider 返回非空文本、唯一 terminal、非伪 response ID 和 usage；
- 请求数为 1，无重试、fallback、截断、摘要或消息删除。

10 条被本地预检拒绝或被 Provider 拒绝，G3 直接 `stop_before_media`。

### Z4：11 条 Provider 边界

生产 wrapper 必须继续对 11 条 fail-closed。为了区分“本地限制”与“Provider 真正行为”，G3 测试脚本
可在这个唯一 case 中，复用同一 Converter 生成恰好 11 条消息后，显式走一个 **test-only boundary
client** 绕过生产 wrapper 发一次请求。该入口不能被应用 API 或生产 route 调用。

允许记录两种 Provider 结果：

- `accepted`：保存非空文本、terminal、usage 和非伪 Provider response ID；
- `rejected_documented`：保存 HTTP 状态、Provider 错误码、安全化错误摘要，以及 request ID 或 trace ID。

两种结果都不改变生产 10 条上限。网络不确定、没有结构化终态、拒绝但缺少请求标识或发生重试时，行为
没有被充分观测，G3 仍为 `stop_before_media`。

## 7. 证据来源与对应关系

真实报告必须能从以下来源交叉复核：

| 证据 | 权威来源 |
| --- | --- |
| route / provider / shape / model | Run 快照与 API 读取结果 |
| 应用模型调用 ID、attempt、ordinal | 模型 Step |
| Provider response ID、usage、latency | 模型 Step与完成事件 |
| Tool call ID、arguments、Tool Output | Function Item、Tool Step、Session Item |
| Tool 实际执行次数 | 临时数据库 Tool Step / probe execution record |
| 进程边界 | 子进程 PID 指纹、阶段记录和恢复 attempt；不保存绝对路径 |
| 转换后消息数 | Chat wrapper / boundary probe 结构化计数 |
| 媒体调用 0 | 注册工具集合、Run counters、Step 和 Event 扫描 |
| 无 retry / fallback | 请求计数、事件、错误和配置快照 |
| 无秘密 | 报告字段 allowlist + 敏感模式扫描 |

原始 Prompt、API Key、Authorization、完整 Base URL query、本地绝对数据库路径和用户凭据不进入报告。
测试 marker 和 `echo_probe` 参数可以记录，因为它们是固定公开值。

## 8. Gate 决策

G3 只有两个运行后结论：

### `pass_for_s03_single_image_review`

必须全部成立：

- Z1、Z2、Z3 通过；
- Z4 为 `accepted` 或 `rejected_documented`，且证据完整；
- 实际 Provider 请求数 `<=5`，Tool 执行数为 1；
- 所有成功请求都有唯一非伪 Provider ID、terminal 和 usage；
- 应用模型调用身份、Tool 参数、Step / Event / Session 与恢复证据一致；
- media / publish 工具注册与调用均为 0；
- 报告脱敏扫描通过，默认 route 和生产数据库未改变。

该结论只允许用户评审是否授权 G4 的一张 S03；不自动创建 Run 或调用 Qwen-Image。

### `stop_before_media`

任一硬前置失败、核心 case 失败、请求超限、证据缺失、Tool 重复、ID / 参数冲突、10 条失败、11 条行为
不明确、秘密泄漏或出现媒体调用，都必须使用该结论。停止后不得在同一次授权内切换模型、buffer、
thinking、Provider、上下文策略或重试；后续修复和再次验证必须另建 Sprint 与授权。

## 9. 记录与提交规则

- [空白模板](siliconflow-native-agent-zero-media-gate-evidence-template.json)本身不填写假值；执行时复制为
  `docs/testing/siliconflow-native-agent-compatibility-report.json`。
- 未观测字段使用 `null`，未运行使用 `not_run`，不要用 0 或 `false` 伪装观测。
- 报告先落盘、验证 JSON 和脱敏，再由人工核对数据库；Gate verdict 不能由脚本在证据不完整时强行通过。
- 同一授权不覆盖失败报告。若未来批准第二次尝试，先把旧报告改为带 attempt 的不可变文件，再更新引用。
- 真实报告提交不得包含临时数据库、日志原文、环境文件或凭据。

## 10. 当前控制器决策

- `input_used`：Sprint 176 兼容性决策、Sprint 177 实施蓝图、当前 Native Run / Step / Event / Session
  代码、Agents SDK `0.18.3` 与 OpenAI client `2.45.0` 源码。
- `artifact`：本协议与空白 JSON 模板。
- `decision`：允许冻结未来 G3 的证据和成本边界；禁止把模板当成 G2 / G3 通过或发起外部调用。
- `next_step`：仍等待用户批准 G2 离线适配；G2 通过后再单独请求 G3 最多 5 次调用授权。

本轮完成：把 S03 前的零媒体兼容性验证压缩为 5 次请求、四个用例和两个终态。<br>
下一步建议：批准或拒绝 G2 离线适配，不跳过到 G3 或媒体制作。
