# Sprint 125：Native Agent 固定 Remotion 视频 Tool

## Status

Complete（Closed）。用户于 2026-07-28 确认个人产品的第一版采用“固定模板、逐步开放枚举参数”：
每个画面使用已有图片、旁白音频和整段字幕，可选择一种图片 Motion Preset，并可选添加 BGM，
最终由 Native Agent 生成可播放视频。

## Goal

新增真实 `render_story_video(scenes, bgm_asset_id?)` Function Tool。发布版 Skill 选择该 Tool
后，Native Agent 可把当前 Run 已生成的图片和语音按给定顺序送入固定
`narrated-panel-v1` Remotion 模板，使用受控图片动态效果、整段字幕和可选 BGM 渲染一个
1080×1920 MP4，并保存为当前会话 owner 可读取的视频资产。

## In scope

- 新增独立 Remotion 4 项目和 `narrated-panel-v1` 模板，固定 1080×1920、30fps、H.264/AAC。
- 每个 Scene 接受当前 Run 的 `image_id`、`audio_id`、非空 `subtitle` 和一个 Motion Preset：
  `static`、`zoom_in`、`zoom_out`、`pan_left`、`pan_right`、`pan_up`、`pan_down`。
- Scene 时长严格来自对应 Native Audio 的 `duration_ms`；字幕在整个 Scene 显示。
- BGM 可选；提供时必须是当前会话 owner 有权读取的音频资产，固定低音量、循环并随视频裁切，
  开头淡入、结尾淡出。
- Tool 只接受业务语义参数；分辨率、fps、codec、缩放幅度、平移幅度、字体、字幕布局、
  BGM 音量、输出路径和渲染并发均由 Runtime 固定。
- Python 渲染桥接负责资产本地化、严格输入校验、调用 Node/Remotion、读取 MP4 和明确错误。
- 新增 Native Video 持久化、迁移、Tool Step/Result/Event、幂等复用、MLflow Span、API/SSE
  投影、owner 资产访问和 Agent 对话视频播放器。
- Skill Tool catalog 增加“渲染故事视频”，Native Runtime 按固定 Skill Version 动态暴露。
- Docker 构建包含固定 Remotion 依赖和渲染所需 Node 运行环境。
- 增加模板输入、渲染桥接、Tool、持久化、权限、API 和前端类型测试。

## Out of scope

- 让模型生成或修改 React、CSS、Remotion Composition 或任意动画表达式。
- 已有视频素材混剪、视频裁剪、原声混音、画中画、多轨时间线或视频特效编辑器。
- 逐字字幕、句级时间戳推断、自动转写、强制对齐或按字数猜测字幕时间。
- 用户上传 BGM 的新管理页面、内置默认 BGM、音乐推荐、自动卡点或多条 BGM。
- 横屏/方形模板、动态分辨率、动态 fps、任意 codec、任意动画数值或效果叠加。
- Remotion Lambda、Cloud Run、Redis、外部队列、分布式渲染、取消正在执行的 Chromium 编码。
- 重写现有 Admin `VideoTask` / `comic-video-studio` 链路。

## Done means

- Skill 发布版本勾选 `render_story_video` 后，Native Runner 获得真实 Function Tool；未勾选时
  不暴露。
- Tool 对每个 Scene 校验图片和语音属于当前 Run、音频有正数时长、字幕非空、Motion 在枚举内；
  任何错误都明确失败，不使用其他资产或默认时长。
- 至少两张测试图片、两段测试音频和两种 Motion 能真实渲染可播放 MP4；有/无 BGM 输入均能
  生成确定性 Composition。
- 同一 SDK `tool_call_id` 成功重放时复用已有视频，不重复执行 Remotion。
- 视频、模板版本、Scene 快照、BGM 快照、时长、分辨率、fps 和渲染器版本可审计；owner 可播放，
  其他用户不能读取。
- Remotion 或 Chromium 缺失、渲染超时、非零退出、空文件或持久化失败时 Run 明确失败，不产生
  伪成功视频。

## Verification

1. Remotion 项目 TypeScript 检查和固定输入单元测试通过。
2. Python 渲染桥接测试覆盖 manifest、成功输出、超时、非零退出和空文件。
3. Native Agent 定向测试覆盖 Function schema、动态 Tool 白名单、持久化、幂等与权限。
4. 使用本地测试图片和音频完成一次真实 Remotion MP4 smoke，并用 `ffprobe` 核对
   1080×1920、30fps、H.264 和音频流。
5. 前端 TypeScript/Vite 生产构建通过。
6. 空 SQLite Alembic migration、`./scripts/check.sh` 与 `git diff --check` 通过。

## Handoff

第一版完成后，Skill 正文只需规定如何为每个画面选择 Motion Preset、何时添加 BGM，并把已有
图片/语音 ID 交给 `render_story_video`。后续根据真实样片再新增版本化模板、字幕 Preset、
转场 Preset 或 BGM 音量枚举；已有视频素材混剪与逐字字幕必须另开合同。
