# Paynes Creek G7 中文语音与字幕协议

更新时间：2026-08-12

状态：Design ready / blocked by G7-0 runtime lineage / not authorized / not run

G7-0 的可审核实现边界见
[同会话跨 Run 媒体 Lineage 蓝图](../../architecture/native-agent-cross-run-media-lineage-blueprint.md)与
[Sprint 187 合同](../../contracts/sprint-187-native-agent-cross-run-media-lineage.md)；两者均未授权或实施。

## 1. 先决结论：当前不能直接执行 G7

纸面上可以把 12 镜语音逐镜验收，但当前 Native Runtime 有一个硬阻断：

```text
每镜独立 G7 Run
  ├─ generate_speech → NativeAgentAudio(run_id = 当前 Run)
  └─ generate_subtitles → 只接受当前 Run 的 audio_id

新的 G8 Run
  └─ render_story_video → 只查询 G8 Run 自己的 audio_id / subtitle_id
                         → 无法读取 12 个 G7 来源 Run 的音频与字幕
```

Follow-up 也会创建新的 `NativeAgentRun`，只继承上下文和 Artifact 摘要，不会把父 Run 的
`NativeAgentAudio` / `NativeAgentSubtitle` 改挂到新 Run。当前通用等待输入只覆盖文章审批和图片质量，
没有“生成一镜语音后暂停人工试听，再在同一 Run 继续十二镜”的语音 Gate。

因此以下两种做法都禁止：

- 把 12 镜塞进一个 Run 并在没有逐镜人工试听时直接渲染；这会绕过 G7 Gate。
- 每镜独立 Run 后声称 G8 可以直接消费；当前查询明确不支持。

## 2. G7-0：必须先补齐的最小运行时能力

G7-0 不是媒体调用，而是未来需单独批准的离线开发 Gate。最小方向是只扩展 G8 的输入解析：

1. `render_story_video` 可读取**同一 Native Conversation**中成功来源 Run 的 `NativeAgentAudio` 与
   `NativeAgentSubtitle`，不能放宽为同一用户任意 Conversation。
2. 来源 Run 必须成功；Audio / Subtitle / FileAsset 均存在，Subtitle 的 `audio_id` 必须等于 Scene 的
   Audio ID，两个来源 Run ID 必须被保存到视频 Scene 快照。
3. 继续校验 Conversation owner；Admin 可读规则不能转化为跨用户渲染授权。
4. 不复制、不移动、不重新登记媒体资产；G8 只保存引用与不可变 lineage。
5. 当前 `generate_subtitles` 仍只接受本 Run 音频，因为每镜 Speech + Subtitle 本来就应在同一个 G7 Run。
6. G8 使用只暴露 `render_story_video` 的专用 Skill Version，不暴露 `inspect_image`。图片的机器与人工通过
   已由 G4–G6 来源 Run 留证；若 G8 再暴露 `inspect_image`，当前代码只会承认 G8 Run 内的检查结果。
7. 测试至少覆盖：同 Conversation 跨 Run 成功、跨 Conversation 拒绝、跨用户拒绝、字幕 / 音频不匹配
   拒绝、来源 Run 未成功拒绝、当前 Run 行为保持、Scene 快照保存图片 / 音频 / 字幕三个来源 Run ID；
   Generation Task 图片或内联字幕没有 Native 来源 Run 时对应字段为 `null`。

只有离线实现与测试写入 `pass_for_g7_scene_runs`，才允许评审 G7-01 的真实语音授权。本文不批准或实现
G7-0。

## 3. 已核实的语音与字幕事实

### 火山语音

| 字段 | 当前固定值 / 行为 |
| --- | --- |
| Provider | `volcengine`，V3 单向流式 TTS |
| Resource | `seed-tts-2.0` |
| Model | `seed-tts-2.0-standard` |
| Speaker | `zh_female_xinlingjitang_uranus_bigtts` |
| 格式 | MP3 / 24 kHz |
| 本片速度 | `speed=1.0` → `speech_rate=0` |
| 音量 | `loudness_rate=0` |
| 时长 | Provider frame；缺失时由显式 `ffprobe` 实测 |

模型只能提交旁白文本和六档速度之一。当前没有 SSML、拼音、停顿标记、逐词发音覆盖、情绪参数或备用音色。
若“佩恩斯克里克”“伯利兹”“一米四三”等读音失败，当前 attempt 必须停止；不能在同一授权内改写文本、
换音色或切 Provider。

### 本地字幕

- `generate_subtitles(audio_id)` 只接受当前 Run 中有真实 `duration_ms` 的音频。
- 本地 faster-whisper 固定 `language="zh"`、`vad_filter=True`、`word_timestamps=True`。
- Whisper 只提供时间锚点；最终全文和 cue 文字使用保存的 `NativeAgentAudio.text`，不是未经校准的 ASR 文本。
- 规范化字符序列匹配低于 50% 时明确失败；成功结果不返回具体匹配率，不能在证据中猜一个数。
- cue 按句号 / 问号 / 分号等强边界、逗号等软边界和最多 18 个对齐字符切分；时间必须单调且不超音频。
- 当前默认模型快照为 `tiny:source-aligned-v1`；实际 attempt 仍需记录当时的 model / device / compute 配置。
- 持久化全文必须逐字等于 TTS 原文，字幕时长必须等于音频真实时长。

字幕原文对齐能防止 ASR 把“可能”“不等于”“未知”改掉，但它无法证明声音确实读对，所以机器成功后仍需
人工试听。

## 4. G7 生产顺序

G7 按语言风险排序，不按成片时间线：

| Gate | Scene | 语言风险 | 必听锚点 | 排位理由 |
| --- | --- | --- | --- | --- |
| G7-01 | S01 | 专名 + 问句节奏 | 佩恩斯克里克；不完整、却能追踪 | 先决定固定音色能否承载全片入口和核心专名 |
| G7-02 | S02 | 地名 + 年代 | 伯利兹南部；大约；公元六百到九百年 | 第二个高频读法族，验证地点和年代不粘连 |
| G7-03 | S08 | 度量读法 | 全尺寸木桨；约一米四三 | 唯一小数口语化读法，尽早失败 |
| G7-04 | S03 | 重建限定词 | 依据遗迹和类比做的重建；可能 | 固定 A+B 重建的语气与字幕保真 |
| G7-05 | S07 | 可能 + 否定 | 可能；但这不等于；通用货币 | 避免重音只落在“通用货币”造成反向理解 |
| G7-06 | S09 | 解释 + 无记录 | 合理解释；但；没有货单；不知道 | 验证转折后的未知项完整可懂 |
| G7-07 | S10 | 支持 + 未知列表 | 共同支持；具体路线、城市和买家仍然未知 | 列表不能被吞词或读成确定路线 |
| G7-08 | S11 | 反误读 + 时间顺序 | 不代表；废弃后；反而保存 | 先否定水下煮盐，再说后来淹没 |
| G7-09 | S12 | 综合收束 | 能拼出机制；不能复原；知道与不知道 | 检查长句对照和结尾停顿 |
| G7-10 | S04 | 器物列举 | 陶碗、陶罐或陶盆；黏土支座；逐渐结晶 | 低风险机制句，复用已确定节奏 |
| G7-11 | S05 | 社会解释边界 | 支持；但我们不知道；家谱和分工 | 保留有限解释与未知边界 |
| G7-12 | S06 | 规模与不可量化 | 共同支持；超过日常自用；确切年产量仍不知道 | 最后补齐并计算 12 镜真实总时长 |

成片仍按 S01–S12 播放。G7 顺序只控制真实语音调用、人工试听与失败成本。

## 5. 每镜原子 attempt

一次明确授权只覆盖选中一个 Scene 的一对 Tool：

```text
前置 Gate / 文本哈希 / Provider 快照 / 审核人 / 成本通过
  → 一个新 Run
  → generate_speech(text=锁定旁白, speed=1.0)
  → 成功后 generate_subtitles(audio_id=本 Run 新音频)
  → Run 完成
  → 文件探针 + 人工试听 + VTT 校对
  → 写终态并停止
```

| 项目 | 上限 |
| --- | ---: |
| 新 Run | 1 |
| 火山 TTS Provider 请求 | 1 |
| `generate_speech` Tool Call | 1 |
| 新音频 | 1 |
| `generate_subtitles` Tool Call | 1 |
| 新 VTT | 1 |
| 人工语言复核 | 1 |
| 自动重试 / 新音色 / 新速度 / 文本变化 / 自动下一镜 | 0 |

Speech 与 Subtitle 是一个 Scene attempt 内的授权对：字幕是本地派生层，不在两者之间设置人工暂停。若 Speech
失败，不调用 Subtitle；若 Subtitle 失败，保留音频与错误，当前 attempt 停止。代码允许同一音频最多两次字幕
失败，但本协议更严格：一次失败后不在当前授权内调用第二次。

## 6. 每镜机器检查

### Speech

- 提交文本 SHA-256、字符数和 UTF-8 字节数与选中 Profile 一致，`speed=1.0`。
- Provider / Resource / Model / Speaker / Format / Sample Rate / speech rate 与 Profile 一致。
- 成功终态、`audio_id`、`asset_id`、Provider request ID、非空文件、SHA-256、字节数和真实 `duration_ms`
  均可回查。
- 音频文件可由 `ffprobe` 读取，文件时长与持久化 `duration_ms` 在后续实现约定的容差内；当前不预填容差。
- `speech_call_count=1`，没有第二次 Provider 请求、备用音色、速度变化或文本变化。

### Subtitle

- `audio_id` 等于本 attempt 新音频且属于同一 Run。
- Provider 为 `faster-whisper`，语言为 `zh`，模型后缀为 `source-aligned-v1`。
- Subtitle `text` 与音频保存原文逐字相等；按 cue 顺序拼接文本也逐字相等。
- cue 非空、时间单调、`end_ms > start_ms`，最后一条不超音频 `duration_ms`。
- Subtitle `duration_ms` 等于 Audio `duration_ms`；VTT 以 `WEBVTT` 开始，文件哈希与资产记录一致。
- 每个 cue 最多 18 个规范化对齐字符；标点可附着，不能把这个内部规则误写成 18 个 Unicode code point。
- `subtitle_call_count=1`；成功只证明对齐门槛已执行，不记录虚构的具体匹配率。

## 7. 人工语言复核

每镜必须由指定语言审核人试听完整音频并逐 cue 阅读 VTT：

1. Profile 的 `must_hear_segments` 全部可懂，没有吞音、错重音、数字误读或歧义停顿。
2. `must_preserve_subtitle_segments` 在字幕中逐字存在，且出现顺序与旁白一致。
3. 声音无截断、重复、异常静音、突发噪声、明显拼接或结尾被吃掉。
4. 句内停顿没有改变证据强度，特别是“支持 / 可能 / 不等于 / 没有 / 未知 / 后来”。
5. 字幕 cue 在听感上跟随语音，没有明显提前、滞后或一闪而过；精确画面遮挡留到 G8 实际渲染检查。
6. 音色、语速、响度与所有已通过前序镜一致；不加入 BGM、环境音或未授权声音。

人工 `pass` 之前，文件只能按资产 ID 和逻辑候选名引用，不能标记为 `PC-Sxx-zh-approved.mp3/.vtt`。

## 8. 总时长与后继 Gate

- 每镜记录真实 `duration_ms`，不把计划秒数写成实测值。
- 每次通过后更新累计时长；G7-12 只有在 12 段全部通过且总时长为 120000–150000 ms 时，才可写
  `pass_for_g8_render_plan_review`。
- 单镜不设置凭估算发明的硬秒数区间。明显不自然的快慢由人工语言复核失败；总时长在最后统一判定。
- 若总时长不合格，写 `needs_script_or_speed_revision` 并停止。修改文本或速度会改变锁定输入，必须新建
  生产包版本和 attempt；不静默拉伸、截断或删除限定词。

| Gate | 完整通过状态 | 只允许评审的下一 Gate |
| --- | --- | --- |
| G7-01 / S01 | `pass_for_g7_02_s02` | G7-02 |
| G7-02 / S02 | `pass_for_g7_03_s08` | G7-03 |
| G7-03 / S08 | `pass_for_g7_04_s03` | G7-04 |
| G7-04 / S03 | `pass_for_g7_05_s07` | G7-05 |
| G7-05 / S07 | `pass_for_g7_06_s09` | G7-06 |
| G7-06 / S09 | `pass_for_g7_07_s10` | G7-07 |
| G7-07 / S10 | `pass_for_g7_08_s11` | G7-08 |
| G7-08 / S11 | `pass_for_g7_09_s12` | G7-09 |
| G7-09 / S12 | `pass_for_g7_10_s04` | G7-10 |
| G7-10 / S04 | `pass_for_g7_11_s05` | G7-11 |
| G7-11 / S05 | `pass_for_g7_12_s06` | G7-12 |
| G7-12 / S06 | `pass_for_g8_render_plan_review` | G8 计划与授权评审 |

共用失败终态：`blocked_precondition`、`failed_during_speech`、`failed_during_subtitles`、
`needs_pronunciation_revision`、`needs_subtitle_revision`、`needs_script_or_speed_revision`。任何失败都阻断后继
Scene，且不自动修改输入或重试。

## 9. 证据记录

执行时复制[空白 attempt 模板](paynes-creek-g7-scene-attempt-template.json)，例如
`paynes-creek-g7-03-s08-2026-08-12-attempt-01.json`。12 镜使用 12 个独立文件，不覆盖旧记录。

存储资产实际文件名由 Run / Step 生成；`PC-Sxx-zh.mp3` 与 `PC-Sxx-zh.vtt` 只是本地导出 / manifest 的
逻辑名。不得把逻辑名伪装成真实 `FileAsset.original_filename`。

未运行写 `not_run`，未审核写 `not_reviewed`，未知写 `null`。不得记录 API Key、Authorization、签名 URL、
账号密码、完整 Provider 响应或本地绝对数据库路径。

## 控制器决策

- `input_used`：锁定旁白、生产草案、Native Speech / Subtitle / Render / Follow-up 实现与本地样片章程。
- `artifact`：本协议、12 镜 Profile、空白 attempt 模板、G7-0 架构蓝图与 Sprint 187 合同。
- `decision`：先设 G7-0 跨 Run lineage 前置；之后按语言风险逐镜生成 Speech + Subtitle 对并人工验收。
- `next_step`：维持 G7 关闭；G2 已离线完成，当前先评审 G3；Sprint 187 / G7-0 仍需独立批准。

本轮完成：发现并固定 G7 / G8 的真实 Run 边界，避免生成 12 段最终无法进入独立 G8 Run 的音频。

下一步建议：G3 已通过，先按顺序完成 G4–G6 视觉 Gate；Sprint 187 / G7-0 实施前不调用火山语音或
Whisper，避免生成无法被独立 G8 Run 消费的音频。
