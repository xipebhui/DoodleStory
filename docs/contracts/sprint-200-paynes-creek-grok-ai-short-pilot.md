# Sprint 200：Paynes Creek Grok AI 五镜短片样片

状态：In progress

## Goal

在 Sprint 199 已验证的 `grokcli` 图片 / 视频能力上，制作一条可本地完整播放的 Paynes Creek
中文横屏短片：五个选定镜头全部来自 Grok AI 图片与图生视频，配一条 SiliconFlow 中文旁白，最终由
Remotion 合成为 1920×1080、H.264 / AAC MP4。该样片用于验证新的 YouTube Agent 媒体方向，不自动发布。

## In scope

1. 固定五镜结构：海岸钩子、卤水浓缩、火上结晶、独木舟运输、证据边界。
2. 每镜保存 Grok 选中首帧、真实 MP4、Prompt、hash、ffprobe 和人工抽帧检查证据；内容失败可由人明确
   创建新 attempt，但同一次调用不自动重试、不切换 Provider。
3. 新增独立 Remotion `paynes-creek-grok-ai-short-v1` 模板，读取真实视频短镜头、整段中文旁白和逐镜字幕；
   根据真实 TTS 时长按旁白权重分配场景时长，并用有界 playback rate 适配镜头，不循环伪造新画面。
4. 新增一次性可审计 Runner：校验输入 hash，调用一次 SiliconFlow
   `FunAudioLLM/CosyVoice2-0.5B`，冻结 Render Manifest，渲染并规范化 MP4，输出接触表和运行报告。
5. 更新 Sprint 199 的真实媒体结论、项目规格与进度。

## Out of scope

- 自动选择 YouTube 赛道、批量生产、自动重试生成失败镜头或自动改用其他图片 / 视频 Provider。
- 自动上传 YouTube、创建发布任务、声明市场验证通过或复写此前 G4 随机图片 Gate 结论。
- 口型、人物主持、BGM、音色克隆、Grok TTS、4K 输出和完整两分钟长片。

## Done means

- 五个选中 Grok 镜头均有真实 H.264 MP4、稳定对象关系和人工接触表结论。
- 真实中文旁白只调用一次，最终时长由 ffprobe 记录；字幕逐镜显示且不依赖 AI 画内文字。
- 最终视频为 1920×1080、30fps、H.264 / AAC、yuv420p，可完整解码，音视频时长误差在一秒内。
- 输出报告记录所有选中 / 否决 attempt、Provider 调用数、hash、编码和 `publication_authorized=false`。
- Remotion typecheck / tests、Python 聚焦测试、`git diff --check` 通过。

## Verification

```powershell
$env:PYTHONPATH='backend;.'
& backend/.venv/Scripts/python.exe -m unittest backend.tests.test_paynes_creek_grok_ai_short
npm run typecheck --prefix remotion
npm test --prefix remotion
git diff --check
```

