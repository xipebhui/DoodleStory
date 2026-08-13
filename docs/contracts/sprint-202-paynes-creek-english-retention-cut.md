# Sprint 202：Paynes Creek 英文留存优化剪辑

状态：Complete（`pass_local_retention_candidate`）

## Goal

在不重新生成 Grok 图片 / 视频、不覆盖 Sprint 201 成片的前提下，把英文五镜样片优化为一条更适合
正式发布评审的 38–42 秒留存剪辑：前三秒给出清晰冲突，字幕按短语切换，视觉信息按“问题—过程—证据—
未知边界”推进，并继续保持考古事实与解释边界。

## In scope

1. 把英文旁白压缩到约 106 词，首句改为“盐已抵达内陆、航运记录却没有留下”的信息缺口。
2. 新增显式 `retention` edit mode；经典中 / 英文计划保持 `classic`，既有成片和复跑语义不变。
3. Retention 模式支持前三秒钩子、逐镜视觉处理、轻微推镜、无中间黑场硬切和按真实场景时长分配的
   1–4 条短语字幕。
4. 复用 Sprint 200 已验收的五个 Grok 视频和 hash；Attempt 3 只允许一次 SiliconFlow 英文 TTS、一次
   Remotion 和一次 FFmpeg 规范化，不自动重试、不切换 Provider。
5. 输出独立 1920×1080、30fps、H.264/AAC、yuv420p MP4、接触表和审计摘要；保持禁止发布。

## Explicit constraints

- `music` Skill 引用的共享配置 / 认证说明在当前本机安装中缺失，不能完整执行 Mureka 流程；本 Sprint
  明确保持 `bgm=false`，不静默改用其他音乐 Provider，也不生成占位配乐或音效。
- 不新增 Grok 调用，不新增随机图片，不改变五个已验收镜头的媒体内容。
- 不把技术通过或接触表通过表述为已经达到最终发布标准；用户完整观看仍是正式发布前门禁。

## Done means

- v3 计划的文案、短语字幕、timing weight、钩子和视觉处理字段通过严格校验。
- 中文 classic、英文 classic 与英文 retention Manifest 测试通过，Python 聚焦测试与 TypeScript typecheck
  通过。
- 最终时长位于 35–43 秒；weighted timing 的 playback rate 位于 0.65–1.35，冻结真实语音边界的
  source-aligned timing 可显式放宽到 0.65–1.45；完整音视频解码通过。
- 高密度接触表确认钩子、地图 / 步骤提示、短语字幕和切镜没有明显溢出或黑场。
- 记录未执行 BGM、零新增 Grok、零发布；如执行项目本地 Whisper，只保存模型、匹配率与时间偏差，
  并把用户完整观看保留为待确认。

## Attempt records

- Attempt 3（`paynes-creek-grok-ai-short-en-v3`）恰好执行一次 TTS、Remotion 与 FFmpeg，完整解码通过，
  高密度接触表确认 retention 视觉方向成立；但真实成片为 44.096 秒，超过 43 秒合同上限，且前三秒钩子
  遮罩使首条字幕对比度偏低，因此明确 rejected，不覆盖、不发布。
- Attempt 4（`paynes-creek-grok-ai-short-en-v4`）保持相同脚本、五个 Grok 媒体 hash、Provider 和视觉处理，
  只把同一 CosyVoice2 声音速度从 1.00 调整到 1.08，并提高字幕层级；允许各执行一次 TTS、Remotion 与
  FFmpeg。新增 Grok、音乐和发布调用仍为 0，这不是 Attempt 3 内自动重试。
- Attempt 4 实际输出 39.061 秒，完整解码、长静音、视觉与字幕对比度检查通过；但项目本地
  `faster-whisper tiny/cpu/int8` 对 TTS 原文的匹配率为 98.6%，并测得 weighted timing 在中段最大偏差
  1.624 秒，声音与字幕 / 切镜不同步，因此明确 rejected，不发布。
- Attempt 5（`paynes-creek-grok-ai-short-en-v5`）复用 Attempt 4 音频 hash，不再调用 TTS；把 Whisper
  校准出的场景和短语边界冻结为帧数。为贴合两个较短的过程旁白，source-aligned 模式显式允许最高 1.45
  playback rate，计划实值最高约 1.44；只允许一次 Remotion 和一次 FFmpeg，其他 Provider 调用仍为 0。

## Result

- Attempt 5 使用 source commit `e4bc14b7213a314bae5609c85da31b13dbb7021b` 通过干净 preflight；五个
  Grok 媒体与复用旁白的路径、hash、ffprobe 时长均一致。真实执行 TTS=0、Remotion=1、FFmpeg=1，
  Grok / 音乐 / 发布调用均为 0。
- 最终 MP4 为 39.061 秒、1920×1080、30fps、H.264/AAC、yuv420p/tv range、1170 帧、34,866,506
  bytes，SHA-256 `dce4db625939372bd49d1d9031b8bc28af41ec7d75b6a34127e8ab34e8c60c56`。
- 五镜 playback rate 为 0.94–1.44；完整解码、长静音、中点与 20 帧高密度接触表通过。钩子、证据图层、
  短语字幕、轻微推镜和无黑场切镜未见明显溢出或技术故障。
- 17 条短语的内部边界相对 Whisper 锚点最大误差为 17ms，最后一条字幕在语音结束后保留 140ms。两种
  本地英文 Whisper 对原文匹配率分别为 98.6% 与 96.6%，但对 `Maya / Paynes Creek / canoes / route`
  仍有近音误识别；正式发布前必须由用户完整听看确认发音。
- 审计摘要保存于 `docs/testing/paynes-creek-grok-ai-short-en-retention-2026-08-13.json`；终态只表示本地
  留存优化候选通过，不代表上传授权或市场验证。
