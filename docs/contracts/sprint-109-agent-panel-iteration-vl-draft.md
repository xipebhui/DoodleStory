# Sprint 109：Agent Panel 迭代与 VL 闭环

## Status

Draft。由原 Sprint 108 顺延；只有 Sprint 108 正式 Agent 前端与已调试 Demo 对齐完成并通过验收后，才允许评审激活。

## Goal

在 Sprint 106 的真实两格漫画链路、Sprint 107 的统一前端工作台和 Sprint 108 的 Demo 对齐界面上，增加指定 Panel 修改、已有版本恢复和 `inspect_image` 证据闭环；所有副作用继续由 Runtime 执行权限、预算、幂等、取消和恢复约束。

## Proposed in scope

- 用户在对话中明确引用一个属于当前会话任务的 Panel，并提交修改方向。
- 只为目标 Panel 创建新的图片版本，其他 Panel 保持不变。
- 恢复已有图片版本时只切换当前版本，不调用图片 Provider、不扣积分。
- 增加唯一的新生产 Tool `inspect_image`，让 Agent 基于真实图片证据决定接受结果、请求一次受控修改或等待用户输入。
- 保存 VL Tool Call、Tool Output、Agent 决策、图片版本与目标 Panel 的完整 Step trace。
- 覆盖重启恢复、重复投递、取消、Provider 晚到结果和积分释放。

## Explicitly out of scope

- 固定角色、临时角色和真人参考图。
- 用户维度 Memory、创作习惯或自定义 Skill。
- `@任务/@图片版本` 以外的通用资源平台。
- 参考漫画、抖音、知识方案或旧 Pipeline 迁移。
- 抠图、Remotion、文字转语音、视频解说或其它多媒体 Tool。
- 多 Agent、外部队列、画布编辑和 Token 流。
- 未经合同评审的自动循环重试；自动修改次数和预算必须在激活前明确。

## Activation gate

激活前必须确认 Sprint 108 已完成，并评审 VL Provider/API shape、单轮 Tool 预算、最大自动修改次数、`waiting_for_input` 条件、取消与晚到结果状态机，以及对应 Evaluation 用例和真实 Provider 验收方法。

## Done means

1. 修改一个 Panel 不改变其它 Panel。
2. 同一修改 Tool Call 重放不重复创建版本或扣费。
3. 恢复旧版本不调用图片 Provider、不扣积分。
4. VL 结果、Agent 决策和版本变化可以从数据库完整追踪。
5. 取消或过期 Run 的 Provider 晚到结果不会保存资产、扣费或复活任务。
6. 页面刷新和服务重启后可以恢复目标 Panel、版本、检查结果和等待状态。

## Verification draft

- Panel 归属、目标局部性、版本恢复和 Tool 幂等单测。
- VL Tool 合同、预算、失败与 `waiting_for_input` 状态测试。
- 取消、晚到结果、积分释放和服务重启恢复测试。
- 真实 VL 与图片 Provider smoke test。
- 浏览器完成“引用 Panel → 修改 → 查看新版本 → 恢复旧版本”的回归。
- `git diff --check` 与 `./scripts/check.sh`。

## Handoff

- 激活前把 `Proposed in scope`、预算和验证草案改成最终合同。
- 固定角色和其它资源入口仍在本 Sprint 之后单独建立合同。
