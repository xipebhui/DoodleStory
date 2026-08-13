# Sprint 202：Paynes Creek 英文留存优化剪辑

状态：In progress

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
- 最终时长位于 35–43 秒，五镜 playback rate 位于 0.65–1.35，完整音视频解码通过。
- 高密度接触表确认钩子、地图 / 步骤提示、短语字幕和切镜没有明显溢出或黑场。
- 记录未执行 BGM / ASR、零新增 Grok、零发布，并把用户完整观看保留为待确认。
