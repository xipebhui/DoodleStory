# Sprint 193：SiliconFlow Native Agent G3 真实零媒体 Gate

状态：Complete（Attempt 2 `pass_for_s03_single_image_review`）

## Goal

在不生成图片、语音、字幕或视频的前提下，用最多 5 次真实 SiliconFlow Chat Completions 请求验证
`siliconflow_chat_v1 / deepseek-ai/DeepSeek-V3.2` 的文本流、单 Tool、跨进程恢复和 10 / 11 条消息边界，
并形成可审计、无凭据的 G3 报告。通过后只开放 G4 的一张 S03 图片。

## Authorization and cost boundary

- 用户在当前任务明确授权完成本地视频所需的真实 Provider 调用与媒体制作。
- G3 最多 5 次 Provider 请求；client、Runner 均不重试，不回退、不切换模型或 thinking / buffering 设置。
- 仅使用 SiliconFlow 账号现有额度；不充值、不购买套餐。若额度不足或 Provider 拒绝，记录
  `stop_before_media` 并停止。
- 本 Sprint 不调用图片、VL、TTS、Whisper、Remotion、YouTube 或发布平台。

## In scope

1. 新增测试专用 `scripts/check_siliconflow_native_agent_compatibility.py`：
   - 固定 Z1 文本流、Z2 单 `echo_probe` 两回合跨进程恢复、Z3 10 条消息、Z4 11 条 Provider 边界；
   - 复用生产 `SiliconFlowBoundedChatProvider`、`NativeModelEventAdapter` 和数据库 Session；
   - 使用新建临时 SQLite，记录 Run、Model Step、Tool Step、Event、Session 和请求计数；
   - 报告只保留 allowlist 字段，不保存 API Key、Authorization、完整 URL、原始 Provider body 或绝对数据库路径。
2. 新增离线测试，验证请求预算、报告判定、脱敏和 11 条生产 wrapper 仍 fail-closed。
3. 在脚本和离线验证先提交后，执行一次真实 G3，并写入
   `docs/testing/siliconflow-native-agent-compatibility-report.json`。
4. 同步协议、生产控制室、规格和进度中的真实状态。

## Out of scope

- 不生成 S03 或任何其他图片。
- 不改 Native Agent 默认路由；默认仍为 `huomiao_responses`。
- 不把 `echo_probe` 注册到生产 Skill、API 或能力 Profile。
- 不实施 G4–G8，不创建本地视频，不上传 YouTube。
- 不因失败自动修改模型、Prompt、消息策略、Provider 或请求参数。

## Done means

- 脚本来源 commit、脚本 SHA-256、模板 SHA-256、SDK / OpenAI 版本和临时数据库指纹已记录。
- Z1、Z2、Z3 均通过；Z4 为 `accepted` 或带请求标识的 `rejected_documented`。
- 总 Provider 请求不超过 5，`echo_probe` 实际执行恰好 1 次，两个进程和两个模型调用身份可区分。
- 所有成功调用都有非伪 Provider ID、terminal、usage；持久化 Step / Event / Session 可交叉复核。
- media / publish 注册和调用均为 0，默认路由和生产数据库未改变。
- 报告 JSON 可解析并通过敏感信息扫描。
- 若任一硬条件失败，报告终态只能为 `stop_before_media`，不执行 G4。

## Verification

```powershell
& backend/.venv/Scripts/python.exe -m unittest backend.tests.test_siliconflow_g3_gate
& backend/.venv/Scripts/python.exe -m unittest discover -s backend/tests
& backend/.venv/Scripts/python.exe -m compileall backend/app scripts/check_siliconflow_native_agent_compatibility.py
py -3.11 .agents/skills/content-iteration-controller/scripts/validate_controller_state.py
git diff --check
```

真实执行前：

```powershell
& backend/.venv/Scripts/python.exe scripts/check_siliconflow_native_agent_compatibility.py --preflight
```

真实执行只允许一次：

```powershell
& backend/.venv/Scripts/python.exe scripts/check_siliconflow_native_agent_compatibility.py `
  --execute `
  --authorization-ref "user-current-task-full-local-video-authorization" `
  --attempt-label "g3-2026-08-13-02" `
  --previous-attempt-ref "docs/testing/siliconflow-native-agent-compatibility-report-attempt-01-local-db-preflight-failure.json" `
  --source-git-commit "<implementation-commit>"
```

## Handoff

- `pass_for_s03_single_image_review`：在新的 G4 attempt 中只生成一张 S03，并执行 VL 与人工审核。
- `stop_before_media`：保留报告，停止媒体；修复必须另建 Sprint 和新 attempt，不覆盖失败证据。
- G3 通过不等于图片、整片或发布授权已经执行，也不证明 SiliconFlow 长对话或其他模型兼容。

## Verification record before real execution

- G3 聚焦测试：13 项通过，包含真实 Agents SDK 流式文本、流式 Tool Call、Tool Output 持久化和恢复 Mock。
- 完整后端：406 项通过。
- Python compileall：通过。
- `git diff --check`：通过。
- SiliconFlow Provider 请求：0；图片、VL、TTS、字幕、视频和发布调用：0。

## Attempt 1 record

- 来源 commit：`d774ed9`；脚本 hash 与 commit 一致。
- 终态：`stop_before_media`；停止点为临时 SQLite 创建测试 Run 之前。
- 根因：Windows 绝对 SQLite 路径被百分号编码成工作区字面文件名，Alembic 没有升级目标临时文件。
- Provider 请求：0；Tool 执行：0；媒体与发布调用：0。
- 不可变报告：
  `docs/testing/siliconflow-native-agent-compatibility-report-attempt-01-local-db-preflight-failure.json`。
- Sprint 194 已修复并验证路径解析；Attempt 2 必须使用包含修复的新来源 commit 与新脚本 hash。

## Attempt 2 record

- 来源 commit：`b701126`；脚本 SHA-256 为
  `c1a1b3200e667067e2ed6bfe99edb52517dbe0e7b97a4752aebf3e351abed492`，与 commit 完全一致。
- Z1 文本流、Z2 单 Tool 跨进程恢复、Z3 转换后 10 条消息、Z4 11 条 Provider 边界全部通过；Z4 实际被
  Provider 接受，但生产 wrapper 仍在 HTTP 前拒绝 11 条。
- Provider 请求恰好 5 次且全部成功，自动重试 / fallback / 模型切换均为 0；`echo_probe` 执行恰好一次。
- 所有成功请求均有非伪 Provider response ID、terminal 与 usage；持久化 Model Step / Tool Step / Event /
  Session 身份交叉复核通过。
- 图片、VL、语音、字幕、视频和发布调用均为 0；报告敏感信息扫描通过，默认路由仍为
  `huomiao_responses`。
- 真实报告：`docs/testing/siliconflow-native-agent-compatibility-report.json`。
- Gate 终态：`pass_for_s03_single_image_review`；只开放 G4 的唯一一张 S03，不开放批量媒体。
