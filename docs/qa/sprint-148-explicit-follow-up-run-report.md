# Sprint 148 显式 Follow-up Run QA 报告

## 结论

PASS。Sprint 148 合同范围已实现并通过自动化与无费用浏览器验收；没有阻塞问题。Probe、Probe
Artifact 与主线采纳仍按合同留给 Sprint 149。

## 合同核对

| 合同项 | 结果 | 证据 |
| --- | --- | --- |
| 父 Run / Checkpoint 关系与字段形状 | 通过 | Alembic migration、ORM CheckConstraint、空库全量迁移 |
| 成功终态、owner、同会话和 active Run 限制 | 通过 | Follow-up service/API 专项回归及真实 409 浏览器路径 |
| 完整只读 snapshot | 通过 | 64KB/50 产物硬上限；仅纳入 Durable committed 与 Native completed/approved，拒绝内容不注入 |
| 幂等创建 | 通过 | 同键同载荷返回原子 Run；同键异载荷 409；真实 FastAPI 重放返回同一子 Run ID |
| 资源固定与发布安全 | 通过 | 继承 Skill/Style/账号、频道和视频引用；发布确认与确认时间清空 |
| Runtime 注入 | 通过 | 普通 Loop 和文案角色均注入 `<follow_up_context>`，父事实只读且本轮输入为新目标 |
| 父子隔离 | 通过 | 子 Run 建立独立 Workflow/Task/Checkpoint；父 Run 状态和产物保持不变 |
| 文案与非文案 Workflow | 通过 | 文案建立 6 个 ARTICLE_TASKS；非文案建立空 Workflow 并可继续进入 Native Loop |
| Projection / SSE | 通过 | `parent_run_id` 与 `continued_from_checkpoint_id` 进入统一 Run projection，刷新仍存在 |
| 页面交互 | 通过 | 成功 Run 入口、失败 Run 无入口、固定提示、取消、父子定位、失败后保留输入均通过真实页面验证 |

## 自动验证

- `./scripts/check.sh`：通过。
- 后端：367 项测试通过。
- Alembic：空 SQLite 从初始 revision 升级至 `t1u2v3w4x5y6` 通过。
- 前端：14 项测试与生产构建通过。
- Remotion：TypeScript 检查与 5 项测试通过。
- Follow-up 专项：6 项通过，覆盖 snapshot 过滤/上限、父子隔离、幂等、越权、非成功父 Run、
  active Run 和非文案 Worker 调度。
- `git diff --check`：通过。

## 浏览器验收

使用隔离 SQLite、真实 FastAPI/Vite、真实登录与持久化 fixture；未 Mock API，未调用模型、图片、
语音、字幕或视频 Provider。

- 成功父 Run 显示“基于此结果继续”；失败 Run 不显示。
- 续接模式显示固定 Skill v1 与 Style，资源按钮禁用，并明确不继承发布确认。
- 取消续接后输入文本保留。
- 临时把已选择的父 Run 改为失败态，真实 API 返回 409；页面保留父 Run 选择、输入文本并展示明确
  错误。随后恢复 fixture 状态。
- 已存在幂等键通过真实 API 重放，返回同一子 Run `525302fe99f44b1295dd8933d1d8456c`，未再次
  入队。
- 刷新后子 Run 显示“续接自上一结果”；登录态刷新后 Console 为 0 error / 0 warning。
- 截图：`output/playwright/sprint-148-follow-up-refresh.png`（本地 QA 产物，不纳入源码）。

浏览器首次提交还发现：非文案 Follow-up 的空 Durable Workflow 会被 Worker 误判为“没有 ready
Attempt”并永久停在 queued。该隔离 Run 在 Provider 调用前被跳过并随即取消，没有产生费用。代码
已改为仅在 Workflow 实际含 Durable Task 时执行该阻断，并新增 Worker 级专项回归；修复后再次运行
完整检查通过。

## 未执行

- 未再次运行真实收费文本或媒体 Provider。Sprint 148 改动的是续接控制面与上下文边界；真实全媒体
  Provider 链已在前序 Sprint 测试，本 Sprint 使用 instructions、Worker 调度和持久化边界回归验证。
- 未实现或验证 Probe，符合 Out of Scope。

## 下一步

Sprint 149 实现受控 Probe：固定 Checkpoint、只读有限预算、无副作用 Tool、Probe Artifact 和显式
采纳命令。
