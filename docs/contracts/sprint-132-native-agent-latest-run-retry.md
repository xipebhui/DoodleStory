# Sprint 132：Native Agent 最近 Run 原地重试

## Status

Complete。用户确认在同一个 Session 中输入精确的“重试”时，系统应自动继续最近一次 Run，
不要求用户理解或选择 Run ID、Step，也不创建新的 Run。

## Goal

让 Native Agent 在末端 Tool 异常后能够复用同一 Run 已保存的上下文和成功资产，从最近失败点
继续执行，避免重新生图、重新生成语音等重复付费。

## In scope

- Native Agent 输入去除首尾空白后精确等于“重试”时，调用专用的最近 Run 重试接口。
- 后端按 Conversation 内 `created_at`、`id` 倒序选择最近 Run，并继续同一个 Run ID。
- 重试忽略提交区当前选中的 Skill 和 Style，继续使用目标 Run 固定的 Skill Version、Style
  快照、模型快照和已有资产。
- 同时检查 Run 状态和 Tool Step 状态；支持 Tool 失败但 Run 已被模型收尾为 `succeeded`
  的情况。
- 已知失败的 Tool 使用原 Tool 名和原参数重新执行；重试前不允许模型改写失败 Tool 参数。
- 成功 Tool 和资产不重新执行；取消、执行中或结果未知的 Run 不自动重试。
- 重试命令写入 Run 的展示 Item、SDK Context 和 Event，服务重启后仍可恢复排队。
- Tool 重试成功时清除旧错误字段，Run 可生成新的 final Step 和最终输出。

## Out of scope

- 在界面中展示或要求用户选择历史 Run ID、Step ID。
- 选择更早的非最近 Run。
- 识别“再试一下”等非精确重试表达。
- 自动恢复用户已取消的 Run。
- 自动重试 Provider 结果为 `unknown` 的 Tool。
- 用重试时新选的 Skill 或 Style 覆盖历史 Run 快照。

## Done means

- 同一 Conversation 有多个 Run 时，“重试”只继续最近 Run，返回的 Run ID 不变。
- 当前 Skill/Style 为空或与目标 Run 不同，都不影响重试，后台仍使用目标 Run 快照。
- 失败 Tool 被重置为可执行状态并保留 attempt 计数；只有原参数可以认领该重试 Step。
- Tool 失败但 Run 为 `succeeded` 时仍可重试；真正完成、取消、活动中或 unknown 状态返回明确
  冲突，不产生新 Run 或付费调用。
- 前端在“重试”模式下不再强制选择 Skill，并明确提示本次将复用最近 Run 的配置。
- 后端测试、前端构建、`./scripts/check.sh` 和 `git diff --check` 通过。

## Verification

- 后端集中测试覆盖 succeeded Run 中失败 Tool 的同 Run 重试、原参数认领、参数不匹配拒绝、
  failed Tool 禁止把 Run 收尾为成功，以及 `retrying` Run 重启重新入队。
- 前端生产构建验证精确“重试”无需 Skill 即可提交，专用请求不携带 Skill/Style。
- `./scripts/check.sh` 通过：292 项后端测试、空库 Alembic 升级、前端生产构建、Remotion
  TypeScript 检查和 5 项 Remotion 测试。
- `git diff --check` 通过。

## Handoff

- 当前只提供自然语言最近 Run 重试；若后续需要重试更早 Run，应另行设计历史任务入口。
- Provider 返回结果无法确认的 `unknown` Step 继续保持人工确认边界，避免重复计费。
