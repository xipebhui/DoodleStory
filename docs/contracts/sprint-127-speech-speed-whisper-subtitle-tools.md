# Sprint 127：语音倍速、Whisper 字幕与 Remotion 时间轴

## Status

Active。用户于 2026-07-28 要求确认火山引擎语速和字幕能力，并把可控语速、字幕文件生成、
字幕时长及视频字幕消费集成到 Native Agent；这些方法必须可在 Skill 设置中选择。

## Goal

把现有多媒体链路拆成三个可组合 Function Tool：

1. `generate_speech(text, speed)`：用固定 Seed-TTS 2.0 模型和音色生成指定枚举倍速的语音。
2. `generate_subtitles(audio_id)`：使用本地 OpenAI Whisper 对真实音频生成带时间轴的 WebVTT。
3. `render_story_video(...)`：消费图片、音频及可选字幕资产，以准确时间轴显示字幕。

## In scope

- `generate_speech` 开放 `0.5/0.75/1.0/1.25/1.5/2.0` 六档倍速，Runtime 映射到火山
  `speech_rate=-50/-25/0/25/50/100`；模型不能传任意数值。
- 音频记录保存请求倍速与实际 `speech_rate` 快照；相同 Tool Call 重放保持幂等。
- 保持当前 Seed-TTS 2.0 V3 HTTP Chunked 接口，不切换到异步长文本或 Realtime 协议。
- 新增 `generate_subtitles(audio_id)`，仅接受同一 Conversation 内可访问的 Native Audio。
- 使用仓库现有 `faster-whisper`（OpenAI Whisper 模型实现）对真实音频转写，保存 segment
  起止毫秒、全文、语言、模型和 WebVTT `generated_subtitle` 资产。
- 新增 Native Subtitle 数据、迁移、Tool Step/Result/Event、调用计数、API/SSE 投影和
  owner 资产权限。
- `render_story_video` 的 Scene 可显式使用 `subtitle_id`；字幕时间相对当前 Scene 音频，
  Remotion 按时间轴只显示当前 cue。保留显式整段 `subtitle` 输入模式，二者必须且只能选一个。
- Skill Tool catalog 新增“生成字幕”，发布版本勾选后 Native Runner 才暴露。
- Skill 页面继续复用现有 Tool catalog UI，不增加专用 Workflow 编辑器。

## Out of scope

- 自动切换到火山异步长文本、Realtime 或其他字幕接口。
- 火山字幕失败后静默切 Whisper；当前 HTTP 接口直接以 Whisper 为唯一字幕实现。
- 任意语速浮点数、音色、音调、情绪或音量开放。
- 逐字卡拉 OK 样式、字幕人工编辑器、多语言翻译、说话人分离或字幕烧录开关 UI。
- 为旧音频自动批量补字幕或修改历史视频。

## Done means

- 六档 speed 均通过 schema 校验并正确映射到火山请求；不支持的倍速明确失败。
- Provider 不返回时长时继续以 `ffprobe` 读取真实音频时长，不估算。
- Whisper 对 Native Audio 生成非空、时间单调且不越过音频总时长的 cue 和有效 WebVTT。
- Subtitle 资产、模型、全文、语言、cue JSON、音频关联和 owner 权限可审计。
- Remotion 使用 subtitle ID 时按 cue 时间显示文字，不再把整段字幕铺满整个 Scene。
- `generate_speech`、`generate_subtitles`、`render_story_video` 都能在 Skill 设置中独立勾选。

## Verification

1. 火山请求测试覆盖六档映射、非法倍速和真实时长。
2. Whisper 单元测试覆盖 cue 校验与 WebVTT 生成；真实音频完成一次字幕 smoke。
3. Native Tool 测试覆盖字幕持久化、幂等、跨 owner 拒绝和资产权限。
4. Remotion TypeScript 测试覆盖 timed captions manifest；真实视频用 VTT cue 渲染。
5. 前端构建、空库 Alembic、`./scripts/check.sh` 与 `git diff --check` 通过。

## Handoff

字幕属于音频派生资产，因为时间轴由实际音频和倍速决定；视频模板只消费字幕，不负责识别。
后续若要利用火山原生字幕，需要先对当前 Seed-TTS 2.0 HTTP 接口完成独立协议验证，再作为新的
字幕 Provider 显式加入，不能静默替换 Whisper。
