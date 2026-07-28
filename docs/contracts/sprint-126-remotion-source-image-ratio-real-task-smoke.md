# Sprint 126：Remotion 跟随源图比例与指定会话真实验收

## Status

Complete（Closed）。用户于 2026-07-28 指定已有 Native Agent 会话的成品图，要求真实识别
图片内文字、把文字转成语音，再调用视频 Function 生成视频；视频比例应跟随图片，而不是由
Tool 固定为 9:16。

## Goal

让 `render_story_video` 可使用同一会话历史 Native Run 图片或当前用户已有 Generation Task
的成功当前图片，并由首张图片的真实宽高决定 Composition 比例；使用用户指定会话完成一次真实
“图片文字识别 → `generate_speech` → `render_story_video`”验收。

## In scope

- `image_id` 明确支持两类 ID：当前会话任一 Native Run 的 `NativeAgentImage.id`，或当前
  会话 owner 所拥有任务中的成功且 current 的 `GeneratedImage.id`。
- 输出宽高取首张源图真实尺寸；H.264 需要偶数尺寸时，只把奇数边向上补 1 像素。
- 多个 Scene 的图片比例必须一致；比例不一致时明确失败，不自动裁成其他比例。
- Remotion `calculateMetadata` 根据受校验的输入宽高设置 Composition；fps、codec、动画参数、
  字幕样式与 BGM 参数仍固定。
- 使用用户指定会话 `8e6670870201470280fa27f2f07fc8c4` 已保存的四张 Native 图片，通过
  现有真实 VL 能力逐图识别可见文字。
- 为每张图识别出的非空文字分别调用真实 `generate_speech`，再调用真实
  `render_story_video`，保存 Agent Audio、Video、Step、Event 与资产。
- 用 `ffprobe` 核对最终 MP4 的宽高比例、30fps、H.264 和 AAC 音频。

## Out of scope

- 自动选择任意历史版本、失败图片、其他用户图片或未授权资产。
- OCR Tool 产品化、文字识别结果数据库新表、人工校对 UI 或 OCR 置信度。
- 任意输出分辨率参数、任意裁剪方式、横竖屏模板枚举、逐字字幕或自动字幕对齐。
- 通过完整 Agent 模型 Loop 自主规划这次测试；验收直接调用已注册 Function，保证输入可审计。
- 修改最新 Generation Task、覆盖其图片，或把测试视频写入旧 Admin VideoTask 链路。

## Done means

- 指定会话及其四张图片由数据库查询得到，没有用 Prompt 文本冒充图片识别结果。
- VL 确实读取图片并返回逐图可见文字；没有文字的图片明确失败，不使用任务原文代替。
- 四次真实语音 Tool 调用产生可播放的 Native Audio，视频 Tool 使用返回的 audio ID。
- 视频 Tool 直接接受同一会话历史 Native 图片；其他用户会话图片被拒绝。
- 最终视频比例跟随首张图片；本次 1086×1448 图片输出保持 1086×1448 的 3:4，而不是
  固定 1080×1920。
- 最终视频可播放，并保存为当前测试会话 owner 可读取的 Native Video。

## Verification

1. Remotion TypeScript 与 manifest 测试覆盖动态宽高和非法尺寸。
2. Python bridge 测试覆盖源图宽高、偶数化输出和不同比例拒绝。
3. Native Agent 真实调用覆盖同一会话历史 Native 图片授权，owner 可读视频且其他用户不可读。
4. 真实 VL、真实火山语音与真实 Remotion Function 均成功。
5. `ffprobe` 核对视频流、音频流、宽高、fps 和总时长。
6. `./scripts/check.sh` 与 `git diff --check` 通过。

## Handoff

本 Sprint 只验证“同一会话历史 Native 图片也能进入受控视频 Tool”和“输出比例跟随图片”。
后续如需把 OCR 正式开放成 Agent Tool、支持混合比例图片、添加裁剪枚举或让用户在 UI 选择
历史任务，应另开合同。
