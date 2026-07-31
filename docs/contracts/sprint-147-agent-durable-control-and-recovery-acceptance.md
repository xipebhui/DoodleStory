# Sprint 147：Agent 控制命令、恢复语义与端到端验收

## Status

Draft。依赖 Sprint 144–146 的 Durable Runtime、动态计划、文章 Gate、媒体 Task 和图片质量
Gate。

## Goal

完成聊天优先 Runtime 的控制与恢复闭环：用户对当前 Gate 的批准/修改、Task retry、取消、后端
重启恢复、SSE 重连和受控诊断分支都由明确命令与不可变 Checkpoint 驱动，并通过完整文章到图片
质量链路的故障演练验收。

## In Scope

### 1. 明确控制命令

- 定义并实现统一命令：`approve_gate`、`request_changes`、`retry_task`、`cancel_run`、
  `resume_run`、`resolve_unknown_effect` 和受控 `create_probe`。
- 每个命令必须校验 Conversation owner、Run/Task/Gate 当前状态、allowed actions、Checkpoint
  revision 与 Tool Effect 状态；重复提交必须幂等返回或明确冲突，不能静默忽略。
- 聊天界面只展示当前状态允许的用户语言操作；按钮文案必须表达真实后果，例如“批准图片方案并开始
  生成 6 张图片”“重做第 3 张并重新检查”。
- 完成 Run 后，新的相关目标创建显式 Follow-up Run，并通过 `parent_run_id` /
  `continued_from_checkpoint_id` 引用经选择的事实；不能把终态 Run 改回运行态，也不能复制完整
  SDK Session。

### 2. 受控 Probe 与局部诊断

- `create_probe` 只能从不可变 Checkpoint 创建只读或明确隔离的分支 Attempt，固定
  `base_checkpoint_id`、目标 Task、允许 Tool 和预算。
- Probe 默认不写主 Run Artifact、不调用不可逆或付费副作用；若需要将结果采用为主线，用户必须
  在聊天中明确批准，Runtime 以新的计划修订合并可验证 Artifact。
- 主 Run、Probe Attempt、Tool Effect 和聊天 Projection 必须清楚区分；用户看到的是“尝试一个
  替代方案”及可采用结果，不需要接触内部 branch ID。

### 3. 恢复、取消和状态收敛

- Worker 以 Attempt lease、heartbeat 和 Checkpoint 恢复；优雅关闭把可安全恢复的执行写为
  interrupted/retryable，启动后只重新入队安全 Attempt。
- `waiting_for_input`、已终态 Task、有效 lease、unknown Tool Effect、取消中的副作用均不得
  被启动恢复错误执行。
- 取消必须阻止未开始的下游 Task 和新的外部副作用；迟到 Provider 结果不得覆盖取消或终态事实。
- SSE 使用 sequence/state version；前端在刷新、断线、重连、收到终态或 sequence 缺口时，拉取
  有界 Conversation Projection 并删除任何本地猜测的“等待执行”状态。

### 4. 端到端验收与操作文档

- 建立覆盖文章与图片链路的故障矩阵、恢复 fixture 和浏览器 QA 报告。
- 更新运行时操作文档：数据库备份/迁移、Attempt 恢复、unknown Effect 人工处理、Run/Task/
  Checkpoint/Tool Effect 定位方法、回滚边界与日志字段。
- 记录真实会话验收结果和截图/ID；不以单元测试或代码审查代替浏览器验收。

## Out of Scope

- 跨项目/跨用户共享 Memory、团队协作审批、审批 SLA、通知中心。
- 自动化生产发布、任意外部工作流引擎、生产多实例调度。
- 新的媒体类型、自动化质量 Judge 排行或最终 Evaluation 数据集建设。

## Deliverables

- 统一控制命令 API、命令权限/幂等/并发控制与聊天操作组件。
- Checkpoint 分叉的受控 Probe、Follow-up Run 语义、恢复/取消/SSE 收敛实现。
- 故障矩阵、操作手册、浏览器验收记录和 Sprint QA 报告。

## Done Means

- 用户可以在聊天中完成完整流程：选题确认 → 正文确认 → Review 修订/确认 → 图片方案确认 →
  图片质量确认 → 终态，不会因刷新、SSE 断开或后端重启失去当前上下文或错误新建 Run。
- 所有批准、修改、取消、重试和恢复由后端 allowed actions 与 Checkpoint revision 决定；重复请求、
  过期请求、越权请求和 unknown Effect 都有明确结果。
- Probe 不污染主线、不会默认执行付费/不可逆副作用，采纳 Probe 结果后才产生新的主线计划修订。
- 终态 Run 不再出现“等待执行”；失败 Task、被取消 Task、未知副作用和等待人工处理在聊天中均有
  可理解的最终状态。
- 完成规定的迁移、恢复、重启、SSE、取消、局部重跑和真实浏览器验收，并保存证据。

## Verification

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest \
  backend.tests.test_agent_runtime \
  backend.tests.test_agent_runtime_recovery \
  backend.tests.test_agent_control_commands \
  backend.tests.test_agent_media_tasks \
  backend.tests.test_agent_image_quality
npm --prefix frontend test
npm --prefix frontend run build
./scripts/check.sh
git diff --check
```

Required fault drills:

- 选题 Gate、正文 Gate、Review Gate、图片质量 Gate 等待时重启。
- 纯模型 Attempt、图片 Tool prepared/running、图片结果 unknown 时重启。
- 取消排队图片、取消执行中的图片、Provider 迟到返回。
- 重复 Approve、并发修改、过期 Checkpoint revision、SSE cursor 缺口与刷新。
- Probe 创建、失败、放弃和明确采纳。

Browser QA:

- 在真实前后端完成一次完整文章到图片质量流程。
- 分别验证审批后继续、Review 局部修订、单 Panel 重跑、刷新/SSE 重连、后端重启恢复、取消与
  unknown Effect 提示。
- 保存真实 Conversation、Run、Task、Attempt、Checkpoint、Gate、Tool Effect 与截图，浏览器
  控制台不得有 error/warning。

## Handoff

本组 Runtime Sprint 完成后，进入 Deferred Evaluation 合同：冻结范围、构建回归数据集、运行
真实 Provider baseline，并给出 `GO_INTERNAL` 或 `NO_GO` 结论。
