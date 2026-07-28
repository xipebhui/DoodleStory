# Sprint 133：Native 语音字幕原文二次校准

## Status

Complete。用户确认系统生成的语音应使用提交给 `generate_speech` 的准确原文二次校准字幕，
避免本地 Whisper 中文误识别直接进入成片。

## Goal

对 Native Agent 自生成语音采用“原文决定字幕文字、Whisper 决定时间轴”的受约束对齐，
让 WebVTT 与持久化字幕全文保持 TTS 原文，同时保留真实音频时间。

## In scope

- `generate_subtitles(audio_id)` 从对应 `NativeAgentAudio.text` 读取 TTS 原文。
- faster-whisper 开启词级时间戳，识别结果只作为时间锚点，不再直接作为最终字幕文字。
- 将 Whisper 识别字符与原文规范化字符做单调序列对齐；同音字、人名和标点以原文为准。
- 根据原文标点和单条字幕字数生成可读 cue，并从对齐时间轴取得每条 cue 的起止时间。
- 保存的字幕全文和 WebVTT 文本来自原文；模型快照明确记录原文对齐版本。
- 对齐覆盖率不足、原文为空、Whisper 无有效时间锚点时明确失败，不静默回退到未经校准的
  Whisper 文本或在线服务。

## Out of scope

- 接入在线 ASR、自动 Provider 切换或失败降级。
- 为没有可信原稿的外部上传音频提供原文校准。
- 逐字卡拉 OK、说话人分离、字幕人工编辑器或历史字幕批量重建。
- 改写 TTS 原文、自动修正文案或在字幕中隐藏音频实际漏读。

## Done means

- Whisper 出现少量中文错字时，最终字幕仍与 `NativeAgentAudio.text` 一致。
- cue 时间单调、不越过真实音频时长，WebVTT 合法。
- 原文标点被保留，较长原文可拆成多条可读字幕。
- 识别结果与原文明显不匹配时 Tool 明确失败且不保存错误字幕资产。
- 现有字幕持久化、幂等、owner 权限和 Remotion 消费合同保持不变。

## Verification

- 单元测试覆盖错字校准、标点保留、长句切分、覆盖率不足拒绝和时间轴合法性。
- Native Tool 测试确认将音频记录保存的原文传给字幕生成器。
- 运行相关后端测试、Python compileall、`git diff --check` 和 `./scripts/check.sh`。

## Handoff

- 当前能力只适用于系统已经保存可信 TTS 原文的 Native Audio。
- 后续若支持任意外部音频，应显式设计“纯转写”和“有稿对齐”两种模式，不能复用本路径
  假定原稿可信。

## Verification result

- 8 项聚焦测试通过，覆盖中文错字校准、标点保留、长句切分、低匹配率拒绝、缺少词级
  时间戳拒绝及 Native Tool 原文传递。
- 两条真实火山 TTS smoke 通过：15 字、3432ms 音频的字幕全文与原文一致；54 字、
  15480ms 音频拆为 6 条单调 cue，字幕全文与原文一致。
- `./scripts/check.sh` 通过：298 项后端测试、Python compileall、空 SQLite 全量 Alembic、
  前端生产构建、Remotion TypeScript 与 5 项 manifest 测试。
- `git diff --check` 通过。
