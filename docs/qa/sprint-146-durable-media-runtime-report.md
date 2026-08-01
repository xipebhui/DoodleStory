# Sprint 146：Durable 媒体与图片质量后端 QA 报告

## 范围

本 Sprint 只实现后端媒体状态、质量结论与局部重跑。现有 Agent 页面、Skill 管理、账号管理、
`@` 资源交互及图片展示页面均未修改。

## 后端事实

- 视觉方案 Artifact 和 `visual_plan_review` Gate。
- `agent_durable_media_bindings`：
  - 传统图片绑定 `GenerationTask / TaskPanel / GeneratedImage`；
  - Native Agent 图片绑定 `NativeAgentImage`；
  - 不复制图片资产或传统任务数据。
- `agent_durable_image_qualities`：版本化 verdict、摘要和结构化详情。
- `image_quality_review` Gate：仅在所有图片均为 `accepted` 后创建。
- Panel 局部重跑：只重置目标图片 Task 和目标质量 Task；其他 Panel 的 binding/verdict 不变。
- Native 图片 Tool Effect：使用 Native Tool Step 作为稳定幂等键，在 Provider 前保存
  `prepared/submitted`，成功后保存 Provider request ID 和图片/资产引用；明确失败与 unknown
  同步结束 Attempt，unknown 不允许自动重跑。
- Native 图片成功后自动执行逐图 VL，保存结构化 verdict、scores、issues、Provider、model 和
  latency；检查服务明确失败时保存 `blocked`，不伪装通过。
- owner-scoped API：视觉方案登记、媒体 Gate 决定、媒体状态、逐图质量决定和 Panel 局部重跑。

## 回归

- 两个传统 Panel 图片绑定后，将第一张标记为 `changes_required` 并请求重跑：
  - 第一张进入 `rerun_requested`；
  - 第二张保持 `accepted`；
  - Workflow 内仍只有两个媒体 binding。
- 所有 Panel 有质量结论前，质量汇总 Gate 明确拒绝创建；完成结论后才创建
  `image_quality_review` Gate。
- Native 图片 binding 使用 `NativeAgentImage.id`，不改变原图片 Tool 的幂等、Trace 或图片资产
  保存路径。
- Native Tool 完成事务会真实创建 Durable binding、质量 Task 和 succeeded Tool Effect；明确失败
  后再次调用会创建新的 retry Attempt，而不是覆盖失败历史。
- owner 隔离测试确认其它用户读取 Run 的媒体状态返回 404。

## 迁移

- Sprint 145 migration `q8r9s0t1u2v3` 保持不可变。
- 新 revision `r9s0t1u2v3w4` 创建 `agent_durable_media_bindings` 和
  `agent_durable_image_qualities`。
- 空库全量 upgrade 通过。
- 数据库停在 `q8r9s0t1u2v3` 后 upgrade → downgrade → upgrade 通过，最终两张表均存在。

## 验证

```text
PYTHONPATH=backend backend/.venv/bin/python -m unittest \
  backend.tests.test_durable_agent_runtime \
  backend.tests.test_native_agent_loop \
  backend.tests.test_task_worker_recovery
./scripts/check.sh
git diff --check
```

结果：通过。完整检查覆盖 354 项后端测试、14 项前端测试、前端构建、空库 migration、Remotion
类型检查与 5 项测试。聚焦 Durable/Native/恢复回归 54 项通过。

Playwright 使用本地 QA 用户验证：

- `/agent` 新对话页可加载；`@` 资源按钮、输入框和运行按钮状态正常。
- `/agent/skills` 可进入并展示列表、筛选、创建入口和返回传统工作台入口。
- 从 Skill 管理返回新对话页后状态正常。
- Console 中两条错误均为注册前 `/auth/me` 的预期 401；登录后未出现新的页面错误。
- 截图：`output/playwright/sprint-146-agent-page-regression.png`（本地 QA 产物，不纳入源码）。

未调用真实图片 Provider，也未产生模型或图片费用。逐图 VL 执行器使用与生产一致的真实 schema、
资产读取边界和状态写入路径，并通过注入式检查结果验证；正式 Provider 费用验证不属于本次无费用
回归。
