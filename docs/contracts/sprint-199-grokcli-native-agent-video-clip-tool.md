# Sprint 199：grokcli Native Agent AI 视频短镜头 Tool

状态：In progress

当前阻断：`xai_video_credits_or_subscription`。2026-08-13 本机 OAuth 登录成功；唯一一次 8 秒 I2V
提交由 xAI 返回 403 额度/订阅错误，未生成 MP4，且未自动重试或切换 Provider。代码与离线验证继续
完成，真实媒体验收需账号恢复视频额度后再执行一次显式 smoke。

## Goal

复用 DoodleStory 已有的 `ele-yufo/grokcli` OAuth 与子进程集成方式，把 Grok 文生视频 / 图生视频接入
Native Agent，产出可在当前会话播放、可审计、可复用的真实 MP4 短镜头；随后用 Paynes Creek 的已审核
图片和提示词执行一次 8 秒图生视频验证。

## Dependency decision

- 上游仓库：`https://github.com/ele-yufo/grokcli`，MIT License。
- DoodleStory 当前固定 `ba81473c44b209ad008c1304fa42979a525eb814`（`grokcli 0.1.0`），已有
  T2V / I2V / R2V，但 I2V 仍使用旧 `grok-imagine-video-1.5-preview` 约定。
- 本 Sprint 固定升级到已审计的 `2dcd4d4b2dc6c35f013a6b2a826721e4b98bfe13`（`grokcli 0.2.0`），
  使用统一 `grok-imagine-video-1.5`；不复制 OAuth token 或上游源码到仓库。

## In scope

1. 新增独立 `grokcli` 视频适配器：构造参数数组而非 shell 字符串；支持 T2V 和单张当前会话图片 I2V；
   模型、分辨率和超时由服务端配置，比例与 1–15 秒时长执行严格白名单校验。
2. 每次 Tool Call 只启动一个 `grokcli video` 子进程；不自动重试、不切换模型 / Provider，避免超时或网络
   结果不明时重复计费。认证、额度、内容策略、超时、网络和输出错误分别产生明确错误。
3. 输出限制在独立临时目录；只接受该目录内唯一 MP4，读取后删除临时文件。使用 ffprobe 校验 H.264 / MP4、
   正尺寸、正时长、帧率与帧数，不信任文件扩展名或 CLI stdout 路径。
4. Native Agent 新增 `generate_video_clip(prompt, image_id?, duration_seconds, aspect_ratio)` Function Tool；
   `image_id` 只能引用当前 Conversation 中的图片，先本地化再传给 grokcli。
5. 复用 `NativeAgentVideo` 与 `generated_video` FileAsset 保存短镜头，快照记录 `grok-video-clip-v1`、
   Provider、模型、模式、Prompt、源图片、尺寸、时长、fps 和 CLI 版本；同一 `tool_call_id` 成功重放只复用
   原资产，未确认执行拒绝重复。
6. 同步 Tool Catalog、能力 API、前端 Tool 名称、Docker / `.env.example`、端点清单、项目规格与进度。
7. 离线验证完成并提交后，使用本机持久化 `GROKCLI_HOME` 做一次登录状态检查；若已登录，则只执行一次
   Paynes Creek 8 秒 16:9 / 720p I2V。若未登录，启动一次浏览器 OAuth 并等待用户完成；未完成时保留
   `blocked_by=xai_oauth_login`，不改走其他 Provider。

## Out of scope

- `video-extend`、`video-edit`、多参考图 R2V、参考音频、声音克隆和 Grok TTS。
- 把 AI 短镜头自动拼成完整 Paynes Creek 视频；现有 `render_story_video` 仍只合成图片、音频与字幕。
- 自动发布 YouTube、创建 PublishableVideo、标题 / 封面 / SEO 或把 8 秒镜头称为完整成片。
- 直接请求或重新实现 xAI OAuth / `/videos/*`；DoodleStory 只调用固定版本 grokcli。
- 认证失败时自动改用 SiliconFlow Wan、ListenHub 或其他视频 Provider。

## Done means

- 上游依赖固定到精确 commit，许可证、能力和本机版本有记录。
- T2V / I2V 命令、参数边界、输出目录逃逸、非 MP4、ffprobe 失败和所有退出码均有聚焦测试。
- Agent Tool 只读当前会话图片，成功保存可播放视频资产并在 API / 事件中返回 Provider、模型和媒体参数；
  同一 Tool Call 重放不再调用 grokcli。
- `grokcli` 生成失败不会执行 Provider fallback 或自动重试。
- 后端聚焦测试、完整后端测试、前端测试 / build、Remotion typecheck / tests、空库迁移、控制器校验和
  `git diff --check` 通过。
- 真实 smoke 若有可用 OAuth，生成唯一 8 秒 Paynes Creek I2V 并记录 hash / ffprobe / 调用数；若 OAuth
  未完成，代码交付可完成，但合同保持 In progress 并明确只剩登录阻断。

## Verification

```powershell
$env:PYTHONPATH='backend;.'
& backend/.venv/Scripts/python.exe -m unittest backend.tests.test_grokcli_video_generation
& backend/.venv/Scripts/python.exe -m unittest backend.tests.test_native_agent_loop
& backend/.venv/Scripts/python.exe -m unittest discover -s backend/tests
npm test --prefix frontend
npm run build --prefix frontend
npm run typecheck --prefix remotion
npm test --prefix remotion
& backend/.venv/Scripts/python.exe -m alembic -c alembic.ini upgrade head
py -3.11 .agents/skills/content-iteration-controller/scripts/validate_controller_state.py
git diff --check
```

## Handoff

- 通过且已登录：交付可在 Agent Skill 中选择的 `generate_video_clip`，并给出真实 Paynes Creek AI 镜头。
- 代码通过但未登录：停止在 OAuth，不生成伪视频、不绕到其他 Provider；用户登录后只需执行真实 smoke。
- 真实镜头通过后，下一 Sprint 才评估 Remotion 混合“AI 视频镜头 + 受控图形 + 旁白字幕”的多镜成片。
