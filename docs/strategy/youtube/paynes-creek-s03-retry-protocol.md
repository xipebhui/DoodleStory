# Paynes Creek S03 单镜重试与验收协议

更新时间：2026-08-12<br>
状态：`attempt_04_needs_revision / three_immutable_failed_attempts / stopped`<br>
适用 Gate：`G4 S03 single-image media gate`

配套空白记录：[S03 Gate 证据模板](paynes-creek-s03-gate-evidence-template.json)

## 这份协议解决什么

首条视频已经选定为 Paynes Creek 玛雅盐业，但第一次 S03 尝试停在 Agent 文本规划：模型返回 429，
图片调用、视觉检查和资产数全部为 0。下一次不能只写“再试一次”，而要把一次真实媒体授权的边界、
观测字段和通过条件提前锁定。

Attempt 02、03 与 04 均已按协议各执行一次并停止。当前真实状态：

```text
G2 离线适配      PASS_OFFLINE
G3 零媒体 Gate   PASS / ATTEMPT 2 / 5 REQUESTS / ZERO MEDIA
G4 S03 单镜       NEEDS_REVISION / ATTEMPT 04 STOPPED
累计图片、VL、视频 3 / 3 / 0
```

## 1. 不可变输入

| 字段 | 锁定值 |
| --- | --- |
| 用途 | `local_production_validation`，不代表市场实验 |
| Topic | `paynes-creek-salt-production-transport` |
| Scene | `S03` |
| 目标时长 | 11 秒 |
| 旁白 | 下面这一步，是依据遗迹和类比做的重建：盐工可能让盐水经过含盐土，提高浓度，再把更浓的卤水收进陶罐。 |
| 证据 | `F3`；来源 `S3 / S4`；权利 `R2 / R3`；`A_plus_B_reconstruction` |
| 运动 | `pan_right`；成片探针按 8% 放大、3% 右移复核 |
| Style | 本地记录 `4443d2412c994ec298b635e6c63806e7`；`active / prompt / 16:9 / Qwen/Qwen-Image`，Style Test 0、图片 0；仅作 [lineage](paynes-creek-style-state-audit.md) |
| 候选文件名 | `PC-S03-v01.png` |
| 通过后文件名 | `PC-S03-approved.png`；通过前不得使用 |
| 输入基线 | Git `ff3033cefd1bf3ea0128f8719694b683b9b2e73a` |
| Prompt 哈希 | SHA-256 `3cd1a0820096f3b3804aad06ced282265559adf40460401a6b0b47f980303729` |

Prompt 哈希的规范输入是
[中文旁白与 Prompt 包](paynes-creek-chinese-script-prompt-pack.md)中 S03 `text` 代码块的完整正文，使用
UTF-8 编码、换行统一为 LF、末尾不追加换行。执行前必须从将要提交的完整 Prompt 重新计算哈希；不一致
时停止并回到输入评审，不能在 G4 内顺手改 Prompt。

## 2. 开 Gate 前的硬前置条件

以下项目必须全部有真实证据，不能用“计划通过”或口头确认代替：

1. G2 留下 `pass_offline` 记录，覆盖路由隔离、Run 快照、事件身份、参数完成事件、能力 Profile、迁移和
   聚焦离线测试。
2. G3 留下独立的 `pass_for_s03_single_image_review` 记录，且其路由、Provider、API shape、模型和消息
   边界与本次 G4 一致；该记录必须依据
   [G3 零媒体 Gate 协议](../../testing/siliconflow-native-agent-zero-media-gate-protocol.md)和
   [机器可读模板](../../testing/siliconflow-native-agent-zero-media-gate-evidence-template.json)生成，协议准备状态
   不能代替真实通过状态。
3. 用户对 G4 做单独媒体授权，明确授权人、时间、一个图片 Tool Call、一个 `inspect_image` Tool Call
   和本 Gate 成本上限。
4. 指定一名事实审核人和一名视觉审核人；两种角色可以由同一人承担，但必须分别给出 verdict。
5. 从当前数据库重新解析 Style ID、状态、模型、比例、Prompt 哈希、参考图数量、Skill Version ID 和路由
   快照；本协议记录的旧本地 ID 只作 lineage，不能直接沿用。任一 Style 字段变化都停止并新建 attempt。
6. 当前工作树、输入 Git commit、完整 Prompt 哈希和 Scene 字段已记录。

任一前置条件缺失时，把记录终态写为 `blocked_precondition`，不得创建 Run，也不得调用外部服务。

## 3. 单次授权边界

一次 G4 记录只覆盖：

```text
1 个新 Native Run
→ 最多 1 次 generate_image
→ 最多得到 1 张 S03 候选
→ 最多 1 次 inspect_image
→ 事实人工复核 1 次
→ 视觉人工复核 1 次
→ 写入一个 Gate 终态并停止
```

它不授权第二张候选、第二次 Run、自动重试、换 Agent 模型、换图片模型、换 Provider、Prompt 改写、
S01 / S04 生图、语音、字幕、视频或发布。候选不合格时可以保留资产用于审计，但不能命名为
`PC-S03-approved.png`。

## 4. 执行顺序

### A. 运行前冻结

- 复制空白 JSON 为新的不可覆盖记录；文件名应含日期与 attempt，例如
  `paynes-creek-s03-g4-2026-08-12-attempt-02.json`。
- 填写 G2 / G3 证据引用、G4 授权、成本上限、审核人、Git commit、Prompt 哈希和当前 Style / Skill ID。
- 只有 `preflight.all_passed=true` 后才可创建 Run。
- Run 建立后填写 Conversation、Run、execution attempt 与完整路由快照；这些字段必须来自持久化数据。

### B. 只生成一张 S03

- `generate_image` 使用锁定的完整 S03 Prompt 与当前 G4 已批准 Provider。
- 记录 Tool Call ID、Step ID、状态、Provider、模型、Provider request ID、`image_id`、asset ID 与错误。
- 从真实文件读取 MIME、字节数、SHA-256、宽度、高度和宽高比；请求尺寸与交付目标另列，不能覆盖真实值。
- 若模型在图片 Tool Call 前失败，终态写 `failed_before_image`；图片字段保持 `null`，调用计数写真实 0。
- 若图片请求失败或未形成可读资产，终态写 `failed_during_image`；不补第二次调用。

### C. 执行一次机器视觉检查

当前 Native Tool 的真实请求为：

```json
{
  "image_id": "<当前 Run 的 image_id>",
  "checks": [
    "historical_mechanism_alignment",
    "reconstruction_boundary",
    "modern_object_exclusion",
    "composition_and_subtitle_safety",
    "pan_right_crop_safety",
    "visual_artifacts_and_text_exclusion"
  ],
  "expected": {
    "story_beat": "<S03 机制与构图预期>",
    "characters": [],
    "required_text": []
  }
}
```

Native Runtime 要求 checks 为 1–10 个不重复字符串，`image_id` 必须属于当前 Run。成功返回字段包括：

```text
status = succeeded
image_id
verdict = accept | revise | ask_user | blocked
scores[每个请求 check] = 0..1
issues[] = code + message + optional suggested_change
provider + model + latency_ms
```

若工具失败，还要保存错误类型和安全化错误摘要。只有 `verdict=accept` 才能进入人工通过判断；
`revise / ask_user / blocked` 都结束本次媒体授权。机器检查不能证明来源真实性、考古解释强度或版权状态。

### D. 事实人工复核

事实审核人逐项写 `pass / fail` 与说明：

1. 画面只表达一个谨慎的卤水浓缩重建，不把整套装置冒充已完整出土事实。
2. 核心对象仅为高置简易木容器、低细节含盐土、漏斗状出口、青绿色液体路径和下方粗陶罐。
3. 琥珀色断线用于表达重建组件，不出现现代滤水器、金属管、阀门、精密机械或固定标准工位。
4. 不复制现代 Sacapulas 装置为古代现场，不复刻论文图版或文物陈列照片。
5. 不新增石砌工厂、宫殿、精确尺寸、确定人物身份或其他来源未支持的历史断言。

任一项 `fail`，事实 verdict 为 `fail`，Gate 终态为 `needs_revision`；本次不生成 v02。

### E. 视觉人工复核

视觉审核人必须查看原始文件，并在应用 `pan_right` 的 8% 放大、3% 右移探针后逐项写 verdict：

1. 实际画面为横向 16:9 或已记录的真实近似比例，未把请求目标冒充真实尺寸。
2. 核心机制位于中央 84% 和上方 70%，底部 30% 保持低信息、低对比字幕区。
3. 平移探针后，容器、液体路径、漏斗出口和陶罐仍完整可辨，不被裁切。
4. 单一青绿液体路径清楚，重建组件使用琥珀断线，画面不制造多条冲突流向。
5. 平面编辑插画与锁定色板一致，不漂移为写实文物照片、电影海报或现代工业示意图。
6. 无文字、字母、数字、带字箭头、Logo、水印、乱码或明显生成伪影。
7. 主焦点明确，缩小到视频观看尺寸后仍能读懂“过滤 / 浓缩 → 收集”的方向。

任一项 `fail`，视觉 verdict 为 `fail`，Gate 终态为 `needs_revision`；本次不生成 v02。

## 5. 终态决策表

| 条件 | 本次终态 | 允许的下一动作 |
| --- | --- | --- |
| G2 / G3 / 授权 / 审核人 / 成本任一缺失 | `blocked_precondition` | 补齐缺失项；不创建 Run |
| Run 在图片 Tool 前失败 | `failed_before_image` | 保留 Run 证据；新尝试需另行授权 |
| 图片调用或资产落盘失败 | `failed_during_image` | 保留调用证据；新尝试需另行授权 |
| `inspect_image` 技术失败 | `failed_during_inspection` | 保留候选和错误；不得跳过机器检查 |
| 机器 verdict 非 `accept` | `needs_revision` | 记录 issues；新 Prompt / 新图另开评审与授权 |
| 任一人工审核非 `pass` | `needs_revision` | 记录具体失败项；本次停止 |
| 机器 `accept` + 事实 `pass` + 视觉 `pass` | `pass_for_s01_anchor` | 才可写批准文件名，并单独评审 G5 的 S01 |

`ask_user` 不等于通过；等待补充判断期间仍保持本次停止。`pass_for_s01_anchor` 只开放下一张 S01
锚点的评审，不自动授权 S04、余图、语音或视频。

## 6. 记录规则

- 未观测值使用 `null`，未运行 / 未审核使用 `not_run / not_reviewed`；不要填 `0`、`false` 或空字符串
  来假装已经检查。
- 调用计数在 Run 结束后从数据库读取；没有建立 Run 时保持 `null`。
- 只记录安全化 Provider request ID 和错误摘要；不得记录 API Key、Authorization header、邮箱密码、
  签名 URL、本地绝对 Storage 路径或完整环境变量。
- 真实文件哈希、宽高和字节数来自候选文件；Provider 元数据与本地文件不一致时，两者分别记录并停止核对。
- 记录不原地覆盖。每个 attempt 使用新文件，并通过 `previous_attempt` 形成链路。
- 任何批准都必须写审核人、时间和可追溯证据；“看起来可以”不算 verdict。

## 7. 完成边界

Attempt 02、03 与 04 的权威结果分别见
[Attempt 02](../../testing/paynes-creek-s03-g4-2026-08-13-attempt-02.json)和
[Attempt 03](../../testing/paynes-creek-s03-g4-2026-08-13-attempt-03.json)、
[Attempt 04](../../testing/paynes-creek-s03-g4-2026-08-13-attempt-04.json)。Attempt 03 的正向白名单消除了
现代器件，但仍产生底部乱码、未获准木块、延伸虚线和字幕区占用；机器 `revise`、委托事实 `fail`、委托
视觉 `fail`。Attempt 04 消除了文字和多余对象，机器误给 `accept`，但陶罐 / 木槽关系倒置且液流向画外
扩张，委托事实 / 视觉仍 `fail`。三轮均无批准文件；当前不开放 G5、语音、视频或发布。
