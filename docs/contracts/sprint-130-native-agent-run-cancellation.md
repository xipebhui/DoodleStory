# Sprint 130：Native Agent Run 可终止执行

## Status

Complete。用户于 2026-07-28 要求在同一对话执行长故事时，可以从消息提交区终止当前 Run；
终止必须覆盖队列等待、模型等待以及图片、语音、字幕和视频 Tool，终止完成前禁止再次提交。

## Goal

为 Native Agent 增加数据库持久化的 `cancel_requested → cancelled` 状态机、进程内当前执行句柄
取消和提交区终止交互，确保取消后不再启动新的付费 Provider 调用。

## In scope

- 新增 owner 隔离、幂等的 Native Run cancel API。
- `queued` Run 未开始时直接完成取消；当前执行 Run 取消其 asyncio Agent Task。
- prepared/running Native Tool Step 统一标记 `cancelled`，保存事件和完成时间。
- Tool 完成、Run 成功或失败持久化不得覆盖 `cancel_requested/cancelled`。
- Run 创建冲突检查包含 `cancel_requested`，取消完成前同一 Conversation 不能创建下一轮。
- 服务启动恢复时把遗留 `cancel_requested` 收敛为 `cancelled`，不得恢复执行。
- 前端提交区在 active Run 时显示“终止任务”；点击后显示“正在终止…”并禁用文本、选择器和按钮，
  直到 SSE 返回最终 `cancelled`。

## Explicit boundary

- 点击取消后不再发起新的图片、语音、字幕或视频 Provider 请求。
- 已经被第三方 Provider 接收的 HTTP 请求没有撤销/退款 API，本系统只能取消本地等待并丢弃其
  未确认结果，不能承诺第三方不计费。

## Out of scope

- Provider 退款、第三方任务撤销协议或跨进程/多实例取消。
- 恢复被取消 Run、保留部分视频或自动重试已取消 Tool。
- 外部队列、独立 Worker 或分布式取消。

## Done means

- queued 和 running Run 都能从 API 进入 cancelled。
- 取消后不执行后续 Tool，迟到完成不能覆盖取消状态。
- 同一 Conversation 在 cancel_requested 阶段创建 Run 返回冲突，cancelled 后可重新提交。
- 前端终止中不能重复点击或提交。
- 后端测试、前端构建、`./scripts/check.sh` 和 `git diff --check` 通过。

## Verification

- Native Agent 集中测试 20 项通过，其中新增覆盖持久化取消、迟到写入拒绝、API 幂等取消和
  运行中 asyncio Task 取消。
- `./scripts/check.sh` 通过：286 项后端测试、空库 Alembic 升级、前端生产构建、
  Remotion TypeScript 检查和 5 项 Remotion 测试。
- `git diff --check` 通过。
