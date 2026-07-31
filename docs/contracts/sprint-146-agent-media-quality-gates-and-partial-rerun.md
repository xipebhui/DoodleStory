# Sprint 146：Agent 媒体 Task、图片质量 Gate 与局部重跑

## Status

Draft。依赖 Sprint 144 的 Durable Runtime 和 Sprint 145 的受控计划修订与聊天式 Projection。

## Goal

把“图片方案 → 多张图片生成 → 图像检查 → 用户质量确认/局部修订”接入同一聊天优先的
Task Runtime。用户仍在会话中确认方案和质量，系统在后台按依赖并行执行安全的图片 Task，并只
重跑不合格的局部节点。

## In Scope

### 1. 图片计划与方案 Gate

- Skill 可以声明图片生产的阶段意图：视觉方案、Panel / 场景列表、生成约束、质量标准和
  `visual_plan_review` Gate。
- Runtime 将已确认文本/Review Artifact 转为版本化视觉方案 Artifact；创建 Gate 前冻结其 hash、
  关联输入文本版本与 Style/Character/账号快照。
- 用户批准视觉方案后，Runtime 在同一 Run 发布计划修订，创建每个 Panel 的图片生成 Task；
  用户要求修改时，只重做视觉方案及下游图片 Task。
- 不让模型在未获视觉方案批准时直接提交真实图片副作用。

### 2. 并行图片 Task 与 Tool Effect

- 每个 Panel 图片生成是独立 Task，依赖同一视觉方案 Artifact，可由 Worker 在明确并发上限内
  并行领取。
- 图片 Task 通过新 Runtime 的明确 adapter 调用既有图片生成领域能力，复用既有积分、Style、
  Character、FileAsset、GenerationTask、Panel 和 GeneratedImage 事实；不复制传统产品域数据。
- 每次外部图片调用必须创建 Tool Effect，保存稳定幂等键、Task/Attempt、Provider request ID、
  prepared/submitted/succeeded/failed/unknown 状态和生成资产/图片版本引用。
- Provider 结果未知时，Task 进入 `unknown` 并阻止自动重跑；明确失败可按 Task 契约创建 retry
  Attempt；已成功图片不得因重试重复扣费或重新调用 Provider。

### 3. 图像检查与质量 Gate

- 每张成功图片触发独立 `inspect_image` / 质量检查 Task，保存结构化视觉结论、问题类别、建议和
  对应图片版本引用。
- Run 汇总各图检查结果后创建 `image_quality_review` Gate；聊天中展示紧凑的质量摘要和图片预览，
  不展示原始视觉模型 Prompt 或 Response。
- 用户可：
  - 接受全部合格图片；
  - 对指定 Panel 要求重做并填写意见；
  - 退回视觉方案；
  - 对不确定/unknown 副作用进行明确人工处理。
- 指定 Panel 重做只能失效其图片 Task、该图片检查 Task 和下游汇总，不重跑正文、Review、其它
  图片或已接受图片。

### 4. 聊天式媒体呈现

- 聊天展示“图片方案等待确认”“正在生成 2/6 张图片”“第 3 张需要处理”“图片质量等待确认”等
  阶段摘要和可点击图片预览。
- 图片质量 Gate 在聊天中提供针对 Panel 的操作，不以任务表格、进度 dashboard 或工作流画布替代
  对话。
- “查看本次计划”可以显示图片并行组、已完成数和待处理数，但不暴露 Worker、lease、Tool 参数或
  原始质量推理。

## Out of Scope

- 音频、字幕、视频渲染及其质量检查。
- 任意自动无限重绘、自动接受图片或由模型绕过用户质量 Gate。
- 跨 Run 的批量图片复用、全局素材库推荐、用户编辑 DAG。
- 通用 Probe Branch；该能力在 Sprint 147 只作为受控恢复/诊断分支讨论，不在本 Sprint 落地。

## Deliverables

- 视觉方案、图片生成、图像检查、质量汇总和 Panel 级修订的 Task 类型与 Artifact/Gate 契约。
- 新 Runtime 到现有图片领域服务的 adapter 与 Tool Effect 幂等链路。
- 图片并行领取、质量 Gate、Panel 级局部重跑和聊天 Projection。
- 积分、幂等、unknown 结果、局部失效、SSE 和浏览器测试。

## Done Means

- 用户确认视觉方案后，同一 Run 创建多个可并行图片 Task；聊天准确展示完成进度与待处理质量项。
- 每张图片都绑定其 Task、Attempt、Tool Effect、视觉方案版本、图片版本和检查结论。
- 指定 Panel 的质量退回只重跑该 Panel 及其检查/汇总；其它 Panel、正文、Review 和已接受图片
  保持不变。
- 服务重启、SSE 重连或页面刷新后，图片进度、质量 Gate、已接受状态和局部重跑目标准确恢复。
- Provider 结果未知时不会自动二次调用或扣费；用户在聊天中能看到明确、可处理的状态。

## Verification

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest \
  backend.tests.test_agent_runtime \
  backend.tests.test_agent_media_tasks \
  backend.tests.test_agent_image_quality \
  backend.tests.test_image_generation
npm --prefix frontend test
npm --prefix frontend run build
./scripts/check.sh
git diff --check
```

Browser QA:

- 从已批准正文启动视觉方案，确认方案后观察多张图片并行执行。
- 对一张图片退回并提供意见，验证只创建目标 Panel 的新 Attempt/图片版本。
- 接受其余图片，刷新并 SSE 重连；在一张图片运行中重启后端，验证 Tool Effect 和积分不重复。
- 保存 Conversation、Run、Task、Attempt、Tool Effect、图片版本、质量 Gate ID 与必要截图。

## Handoff

Sprint 147 统一所有控制命令、恢复/取消/重试、受控诊断分支和全流程故障验收，使聊天式 Runtime
达到内部使用前的稳定性门槛。
