# Sprint 124：Native Agent 火山引擎固定语音 Tool

## Status

Complete（Closed）。用户已于 2026-07-28 提供并真实验证 `seed-tts-2.0`、
`seed-tts-2.0-standard` 和固定音色
`zh_female_xinlingjitang_uranus_bigtts`，并要求将文本转语音注册为可由 Skill 使用的
Native Agent Tool。

## Goal

新增真实 `generate_speech(text)` Function Tool。Skill 发布版本选择该 Tool 后，Native Agent
本轮实际获得该函数；函数使用固定火山引擎模型和音色生成 MP3，保存为当前 Run 所有者可读取的
音频资产，并在 Agent 对话中展示可播放结果。

## In scope

- 新增火山引擎 V3 HTTP Chunked TTS Client，读取现有 `DOUBAO_VOICE_GEN_*` 环境变量。
- 固定 Resource、Model、Speaker、MP3、24kHz、正常语速和正常音量，不把 Provider 配置暴露给
  模型参数。
- Native Function Tool 只接受非空 `text`，使用 SDK `tool_call_id` 派生幂等键。
- 新增 Native Agent Audio 持久化模型、迁移、API 投影、owner 资产访问校验和 SSE 快照展示。
- Skill Tool catalog 增加“生成语音”，Skill 草稿和不可变发布版本可保存该 Tool。
- Native Run 按固定 Skill Version 的 Tool 列表实际构建 Tools；未选择的 Tool 不传给模型。
- Native 对话前端展示音频播放器；纯语音 Skill 不强制选择 Style。
- 增加 Provider 解析、Tool 执行、幂等、权限、API 和前端类型相关测试。
- 更新规格、进度和环境变量示例。

## Out of scope

- 声音复刻、音色上传、动态音色选择、多音色混合或用户自定义 Provider 参数。
- 修改现有 SiliconFlow 视频任务 TTS 链路。
- 长文本自动切段、长文本异步 TTS、字幕时间戳和音频内容模型 Review。
- 音频积分计费、Native Run 多 Worker、全局 Provider 并发池、暂停或取消。
- Provider fallback、兼容旧 V1 TTS 或失败时静默改用其它语音服务。

## Done means

- 发布版 Skill 勾选 `generate_speech` 后，Native Runner 收到真实 Function Tool；未勾选时不
  暴露该函数。
- 模型调用 `generate_speech` 后只产生一次真实火山请求，音频资产、Tool Step、Result 和 Event
  可恢复、可审计。
- 当前会话 owner 能播放音频，其他用户不能读取。
- 纯语音 Skill 可在不选择 Style 的情况下运行。
- Provider 或解析失败时 Run 明确失败，不生成空资产或伪成功结果。

## Verification

1. Provider 单元测试覆盖 V3 请求头、固定参数、多 JSON frame 拼接、终态和错误响应。
2. Native Agent 定向测试覆盖动态 Tool 列表、语音成功、幂等复用和持久化事件。
3. API/权限测试覆盖 Audio 投影和 owner 资产访问。
4. Skill 管理测试覆盖 Tool catalog、草稿、发布版本和未知 Tool 拒绝。
5. 前端 TypeScript/Vite 生产构建通过。
6. `./scripts/check.sh` 和 `git diff --check` 通过。

完成证据（2026-07-28）：

- 使用开发 `.env` 完成一次真实 Provider smoke：HTTP 200、成功终态 `20000000`、17 个音频
  chunk、56,493 bytes，生成 24kHz mono MP3；密钥值未写入代码、日志或文档。
- Provider、Skill catalog、Function Tool、动态白名单、持久化、幂等与 owner 权限定向测试
  通过。
- `./scripts/check.sh` 通过 272 项后端测试、Python compileall、空 SQLite Alembic migration
  和前端 TypeScript/Vite 生产构建。
- `git diff --check` 通过。未调用图片 Provider，未实施 Deferred Evaluation。

## Handoff

本 Sprint 完成后，新的 Skill 只需在编辑页勾选“生成语音”，并在正文中规定何时把哪段文本交给
`generate_speech`。后续视频 Skill 可以组合 `generate_image` 与 `generate_speech`，但视频封装
Tool、长任务拆分和父子 Agent 必须另开合同。
