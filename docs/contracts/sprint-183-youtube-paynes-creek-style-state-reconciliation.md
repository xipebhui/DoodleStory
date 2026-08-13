# Sprint 183：YouTube Paynes Creek Style 状态对账

状态：Complete（只读审计与文档同步；未创建 Style，未调用模型或媒体）

## Goal

消除 Paynes Creek 生产资料中“Style 待建立”“本地记录已存在”和“Style 已可用于真实制作”之间的歧义，
把仓库本地验证库中的 Style 配置事实、测试事实、媒体事实和频道绑定事实分别记录，并为未来 G4 固定
重新解析与停止条件，避免重复创建 Style 或把旧 Run 快照误当成视觉验收。

## In scope

- 只读核对当前 Style、Style Test、生成任务、Native Agent Run / 图片和 YouTube 频道绑定计数。
- 记录 Style 名称、本地 ID、状态、模型、画幅、参考模式、提示词哈希与测试状态。
- 解释当前代码中 `active` 的语义，以及它不能证明的视觉质量、真实尺寸和 Provider 可用性。
- 将机器可读生产草案从“Style 草案”升级为“本地 Style 状态快照”。
- 同步 Prompt 包、生产控制室、S03 重试协议、样片输入哈希、YouTube 索引、研究日志与项目进度。

## Out of scope

- 不创建、编辑、激活、删除或测试 Style，不写数据库，不绑定 YouTube 频道。
- 不创建 Skill、Conversation、Run、Task 或 Asset，不调用 Agent、图片、VL、TTS、字幕、视频或发布接口。
- 不批准或实施 Sprint 181 / G2-A，不设计或实施 G2-B，不开放 G3 或 G4。
- 不把 Style `active`、历史 Run 快照或提示词一致性写成图片质量、尺寸、成本或生产链路已通过。
- 不修改题目、旁白、逐镜 Prompt、模型、Provider、画风规则、来源或发布策略。

## Deliverables

- `docs/strategy/youtube/paynes-creek-style-state-audit.md`
- `docs/strategy/youtube/paynes-creek-production-draft.json` schema v2
- Prompt 包、生产控制室、S03 重试协议与样片验收模板同步。
- YouTube 索引、研究日志、根 README 与 `docs/progress.md` 更新。

## Done means

- 文档明确区分 `style_record_created`、`config_active`、`media_output_verified` 和频道绑定数量。
- 现有本地 Style 不再被描述为“待建立”，也不被描述为视觉已验证。
- 生产草案不再使用含义不清的 `binding_created`，并保存可复核的提示词 SHA-256。
- 未来 G4 必须重新读取当前 Style ID、状态、模型、比例、提示词哈希和参考图数量；任一变化都停止并新建
  attempt，不直接沿用本次审计值。
- S03 空白 Gate 模板的 `observed_style_id` 继续保持 `null`，直到获得真实 G4 授权并运行 preflight。
- JSON 可解析、锁定输入哈希一致、本地链接有效，且新增文档不含密钥、账号密码或绝对数据库路径。

## Verification

```powershell
Get-Content docs/strategy/youtube/paynes-creek-production-draft.json -Raw |
  ConvertFrom-Json | Out-Null

Get-Content docs/strategy/youtube/paynes-creek-local-pilot-acceptance-template.json -Raw |
  ConvertFrom-Json | Out-Null

& backend/.venv/Scripts/python.exe `
  .agents/skills/content-iteration-controller/scripts/validate_controller_state.py

git diff --check
```

Manual checks:

- 以只读 SQLite 连接复核 Style、测试、生成任务、Run、图片与频道绑定计数，不执行任何写操作。
- 对照 Style schema、API 激活逻辑与图片 Gateway，复核 `active`、Prompt 模式、16:9 和模型字段的含义。
- 逐项重算样片验收模板中的锁定文件 SHA-256。
- 检查新增内容不含凭据、Authorization、签名 URL、绝对数据库路径或虚构媒体结果。

## Risks / notes

- 本次只读事实来自仓库 `.env` 所配置的本地验证库；其他电脑、部署环境或未来数据库不保证存在同一
  Style ID，执行时必须重新解析。
- `last_tested_at=null`、Style Test 0 和图片 0 表示当前没有视觉证据；不能从提示词文本推导模型输出质量。
- 目标 YouTube 频道仍未指定，因此频道绑定数量为 0 是预期事实，不应在本 Sprint 内补建绑定。

## Handoff

- Sprint 183 只关闭文档歧义，不改变 G0–G9 的任何运行状态。
- 当前唯一可授权的下一步仍是 Sprint 181 / G2-A；G2-A、G2-B、G3 与 G4 必须串行完成并分别验收。
- 未来 G4 preflight 重新解析 Style 后，才把当次真实 ID 写入新的 Gate 证据记录。
