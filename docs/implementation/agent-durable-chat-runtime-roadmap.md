# 聊天优先的 Agent Durable Runtime 路线

## Product Boundary

`/agent` 是用户与创作 Agent 协作的聊天空间，不是工作流编辑器或任务后台。后端以
Workflow Run、动态 Task、Attempt、Artifact、Gate、Checkpoint 和 Tool Effect 保存执行事实；
前端只将这些事实投影成聊天里的计划摘要、阶段状态、产物和当前可处理决定。

```text
用户目标
  → 初始计划
  → 当前可执行 Task
  → Artifact / Gate / Checkpoint
  → 计划修订或下游 Task
  → 用户可见聊天摘要
```

## Sprint Sequence

| Sprint | Outcome | User-visible result |
| --- | --- | --- |
| 144 | Durable Runtime 基础、文章选题/正文/Review Gate | 选题确认后在同一对话继续正文和审稿，不再断上下文 |
| 145 | 受控动态计划修订与聊天式计划投影 | 用户看到“本次计划”随研究、反馈和 Review 自然演进 |
| 146 | 图片方案、并行图片 Task、质量 Gate、局部重跑 | 用户在聊天中确认图片方案和质量，只重做不合格 Panel |
| 147 | 统一控制命令、恢复、Probe、故障验收 | 刷新、SSE 重连、重启、取消和局部诊断均保持正确状态 |
| Deferred Evaluation | 回归数据集、真实 Provider baseline 与发布结论 | 给出内部使用 `GO_INTERNAL` 或 `NO_GO` |

## Stable Semantics

- Run 是一次完整用户目标；只有 required Task 全部完成且 Gate 全部解决后才可成功。
- Task 是最小可调度、等待、重试、取消和验证的业务单元。
- Attempt 记录 Task 的一次真实执行，绝不覆盖历史执行。
- Gate 是人工介入点；批准推进后续 Task，修改只失效目标及下游。
- Checkpoint 是不可变恢复锚点；SDK Session 仅作为单个 Attempt 的模型上下文。
- Tool Effect 是外部副作用账本；结果 unknown 时不自动重放。
- 模型可提议计划，但 Runtime 校验 Task 类型、依赖、预算、权限与完成契约。

## Non-goals

- 用户编辑 DAG 或查看内部 Task ID/Attempt/lease。
- 在没有证据时引入 Temporal、Redis、Celery 或独立 Worker 服务。
- 用模型摘要替代 Artifact、Gate 或 Checkpoint 事实。
- 用新的自然语言“继续”猜测恢复哪一个已结束 Run。
