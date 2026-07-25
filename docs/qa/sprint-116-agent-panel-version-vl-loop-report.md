# Sprint 116 QA 闭合报告

## Sprint

`Sprint 116：Panel 版本操作、VL 检查与任务控制闭环`

合同：`docs/contracts/sprint-116-agent-panel-version-vl-loop.md`

实现提交：`4b17a8955fe267698a44cc878625dc7ae3a1800b`

复核日期：2026-07-26

## Verdict

`PASS`

Sprint 116 合同范围、验证要求和交接记录均已闭合，没有阻止合同关闭的问题。本报告本身不自动激活下一 Sprint；用户随后于 2026-07-26 明确授权，新的 Skill 管理与通用 Agent Loop Sprint 117 已在整合基线上激活。

## Scope Checked

- 目标 Panel 新版本只修改授权 Panel，保留其它 Panel 与历史版本。
- Conversation → Task → Panel → Version 完整归属链和跨用户拒绝。
- 再生成 Tool Call 幂等、generation number、current 和 accepted 状态。
- 恢复历史成功版本不调用图片 Provider、不占用或扣除积分。
- 真实 `inspect_image` 的五类检查、四类 verdict、严格 schema、Provider/model/延迟/错误记录和每版本一次预算。
- 只有显式授权时才允许一次额外自动修订，Agent 不替用户接受版本。
- pause/resume 幂等、terminal 拒绝、paused Run 不被恢复扫描启动。
- 取消、Provider 晚到、重启恢复、重复投递和 Worker 非阻塞唤醒边界。
- 检查器的成本确认、版本历史、VL 摘要、接受、恢复、引用、暂停/继续及失败输入保留。
- 安全公共事件、数据库恢复和 MLflow Tool span 对齐。
- migration、Python 编译、全量后端测试和前端生产构建。

## Contract Done Matrix

| Done means | 判定 | 证据 |
| --- | --- | --- |
| 1. 修改一个 Panel 不改变其它 Panel | PASS | `test_regeneration_tool_replay_creates_one_target_panel_version` 校验目标 Panel 新增 v2，另一 Panel 版本数和 current 状态不变；纯视觉修改文字边界另有测试。 |
| 2. Tool Call 重放不重复创建或扣费 | PASS | 同一 idempotency key 重放返回 replay，目标 Panel 仍仅 v1/v2，`image_call_count=1`。 |
| 3. 恢复不调用 Provider、不扣积分 | PASS | 恢复服务只在事务内切换 `is_current`；自动化检查状态幂等，真实浏览器验收余额在接受/恢复前后保持 27。 |
| 4. 接受/恢复完整鉴权 | PASS | owner、Conversation、Task、Panel、Version 逐级校验；错误 Panel 和错误 owner 均被拒绝。 |
| 5. VL 与版本变化可追踪 | PASS | AgentStep 保存 Tool Call/Result、Provider、model、latency/error；Event 保存安全摘要；Tool Runtime 使用现有 MLflow `agent.tool_call` span。 |
| 6. 单 Turn 自动修改不超过一次 | PASS | Runtime 图片预算固定为 2；测试覆盖首次 revise 后只创建一个自动版本，第二张检查后完成且 `image_call_count=2`。 |
| 7. pause/resume 从 checkpoint 恢复 | PASS | pause/resume owner、幂等、terminal 状态测试通过；恢复扫描排除 paused，resume 重新入队。 |
| 8. 取消/过期晚到不复活或重复扣费 | PASS | `test_agent_runner_recovery` 和 `test_task_worker_recovery` 覆盖取消 Run、取消前不调用 Provider、Provider 晚到释放预占且不扣费、重启恢复和重复处理。 |
| 9. 刷新/重启恢复版本与检查状态 | PASS | 检查结论保存为持久化 Event，版本/接受/current 保存于数据库；真实浏览器在后端重启和页面刷新后恢复 v1 current、v2 accepted、VL 摘要和活动事件。 |

## Evidence

### Commands run

```bash
SESSION_SECRET=sprint116-contract-closure ./scripts/check.sh
git status --short --branch
```

统一检查结果：

- Python `compileall`：通过。
- 后端单元测试：240 项通过。
- 空 SQLite `alembic upgrade head`：通过，包含 `a2b3c4d5e6f7`。
- 前端 `tsc -b && vite build`：通过。
- 检查前后工作树无非预期修改。

### Manual and real-provider evidence

- 隔离本地数据库中创建两格真实漫画，并用 `gpt-image-2` 为 Panel 1 创建 v2，余额 28→27。
- 真实 `gpt-5.4` VL 返回 `accept`：故事匹配 0.98、人物一致性 0.90、连续性 0.95、文字准确性 1.00、明显瑕疵 0.93。
- 接受 v2 后恢复 v1，余额保持 27；旧版本未删除。
- 生成期间 pause/resume 通过；页面刷新、SSE 断开和后端重启后，current、accepted、VL 摘要和活动事件恢复。
- 首次真实验收发现图片 Worker 同步等待 Agent/VL 可能误标已经成功的图片；实现已改为线程安全非阻塞入队，并新增回归测试。

## Findings

- 未发现阻止合同闭合的问题。
- 本次 2026-07-26 QA 闭合没有重复调用真实图片 Provider；真实 Provider 与浏览器证据来自同一 Sprint 实现分支在 2026-07-25 的验收。原因是用户明确允许跳过重复慢生图，且闭合复核没有代码变化需要重新生成图片。
- 没有做生产部署或内部开放判定；这些不属于 Sprint 116，内部开放门槛属于 Sprint 117。
- 正式产品代码没有 Mock、占位成功、备用 VL 或兼容回退。

## Follow-Up Required

- Sprint 116 无必需修复项。
- 只有用户明确授权后，才能激活 Sprint 117，实施版本化 Evaluation、故障注入矩阵和 `GO_INTERNAL/NO_GO` 判定。

## Notes For Next Sprint

- 复用 Sprint 116 的确定性版本操作和已有队列，不新增创作能力。
- 将权限、错误 Panel、重复生成/扣费、取消晚到、Provider 永久错误和重启恢复纳入 Sprint 117 阻断门槛。
- Sprint 117 应引用本报告作为 Sprint 116 的正式基线证据。
