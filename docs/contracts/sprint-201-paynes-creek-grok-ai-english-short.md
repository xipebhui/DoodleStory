# Sprint 201：Paynes Creek Grok AI 英文五镜短片

状态：In progress

## Goal

复用 Sprint 200 已通过人工与技术验收的五个 Grok AI 视频镜头，制作一条面向英语 YouTube 受众的
独立英文短片。英文版必须使用自然英语叙事、英文标题 / 证据标签 / 字幕和一次英文 TTS，不覆盖中文版，
不重新调用 Grok 图片或视频，也不自动发布。

## In scope

1. 冻结一套约 45–52 秒的英语 Story-style explainer 文案：问题钩子 → 浓缩 → 加热结晶 → 独木舟运输 →
   已知机制与未知路线的边界。
2. 扩展现有 `paynes-creek-grok-ai-short-v1` 模板和 Manifest，使其显式支持 `zh-CN` / `en-US`；根据
   locale 选择字体、标题尺寸、证据标签与页脚，现有中文版保持兼容。
3. 参数化现有 Runner 的生产计划路径，使英文计划可复用相同 hash / ffprobe / playback-rate / Remotion / 
   FFmpeg 验证，不复制第二套渲染逻辑。
4. 每个不可变英文 attempt 只调用一次 SiliconFlow `FunAudioLLM/CosyVoice2-0.5B:alex` TTS；如果真实音频
   导致任一镜头 playback rate 超出 0.65–1.35，明确停止，不循环镜头、不改用其他 TTS。
5. 输出独立 1920×1080、30fps、H.264/AAC、yuv420p MP4、接触表和审计报告。

## Out of scope

- 重新生成 Grok 图片 / 视频、换视觉风格、增加镜头、人物主持、口型、BGM、音色克隆或背景音乐。
- 自动上传 YouTube、生成缩略图 / SEO 包、声明英语市场验证通过。
- 用机器翻译逐句替换中文；英文脚本按英语观看节奏单独撰写。

## Done means

- 英文生产计划固定五镜、英文标题、英文证据标签、英文旁白和复用媒体 hash。
- 中文 Manifest 与英文 Manifest 的离线测试、Remotion typecheck / tests、Python 聚焦测试通过。
- 每个英文 attempt 只执行一次 TTS、一次 Remotion、一次 FFmpeg 规范化；最终被接受 attempt 的所有
  playback rate 在安全范围内。
- 最终视频可完整解码，字幕与标题在高密度接触表中可读，没有超过 1.5 秒的长静音。
- 结果保存 `publication_authorized=false`，没有发布调用。

## Attempt records

- Attempt 1（`paynes-creek-grok-ai-short-en-v1`）已完成一次 TTS、Remotion 和 FFmpeg，但最终英文校对发现
  首句 `How did salt made ...` 语法错误，因此明确标记为 rejected，不覆盖、不发布、不作为最终成片。
- Attempt 2（`paynes-creek-grok-ai-short-en-v2`）只修正 S01 / S03 语法和 S09 英语自然度，复用相同五图、
  五视频与媒体 hash；允许重新执行一次 TTS、Remotion 和 FFmpeg。新增 Grok 图片 / 视频调用仍为 0，
  这不是自动重试，也不改变 Provider。
