# Sprint 147：统一控制与恢复 QA 报告

## 结论

通过。Sprint 147 的六类控制命令、恢复/取消/unknown 收敛、真实链路阻塞修复、页面控制和 SSE
重同步均已实现。Follow-up Run 与 Probe 按合同留给下一 Sprint。

## 已通过

- `agent_durable_commands` 保存 owner、命令、目标、幂等键、期望 state version、payload hash 和
  首次结果；相同 key/payload 重放不会再次入队或取消 Worker，不同 payload 明确冲突。
- `approve_gate`、`request_changes`、`retry_task`、`cancel_run`、`resume_run`、
  `resolve_unknown_effect` 统一由后端 `allowed_actions + state_version` 决定。
- 旧文案审批、媒体 Gate、Panel 局部重跑和取消入口均委托统一命令服务；Panel 命令仍由
  Durable binding adapter 同时重置目标图片与质量 Task，其他 Panel 不变。
- Review Artifact 映射 `editorial_review_gate`；非文案 Skill 创建空 Durable Workflow，不创建
  ARTICLE_TASKS，并在 Native Run 成功时同步 Workflow 终态。
- 相同文本/语速的成功 TTS 在后续调用中复用；同一音频字幕失败两次后拒绝继续自动尝试。
- Native `inspect_image` 保存 verdict/scores/issues/provider/model/latency；Skill 暴露该 Tool 时，
  未得到 `accept` 的图片不能进入视频渲染。
- SSE cursor 缺口发送 `run.resync_required`；前端重新读取 Conversation Projection 和控制状态。
- 页面按权威 allowed actions 展示操作，并显示运行 Tool 名称、真实等待秒数、图片单次超时和最大
  Provider 尝试数；终态 Run 不显示残留运行等待。

## 故障矩阵

| 场景 | 结果 |
| --- | --- |
| 重复 Gate 命令 | 返回首次结果，不重复产生 Attempt/入队 |
| 同一 state version 的后发命令 | 409 过期状态，不覆盖先到命令 |
| failed/blocked Task 重试 | 追加 retry Attempt |
| unknown Effect 存在时重试 | 拒绝；人工标 failed 后才开放 retry/resume |
| queued/running 取消 | 未开始工作取消；submitted Effect 进入 unknown |
| 终态刷新 | 状态版本和恢复按钮从数据库恢复，不显示“正在执行” |
| SSE cursor 缺口 | 发出 resync 事件并重拉投影 |
| 纯媒体 Run 完成 | 无 ARTICLE_TASKS，可正常收敛终态 |
| 字幕连续失败 | 第三次自动尝试被拒绝；成功语音不重复生成 |
| 图片未检查直接渲染 | 明确拒绝；仅 `verdict=accept` 可继续 |

## 自动验证

`./scripts/check.sh` 通过：361 项后端测试、空 SQLite 全量迁移、14 项前端测试、前端生产构建、
Remotion TypeScript 检查和 5 项测试。Sprint 147 浏览器修正后再次运行完整检查，结果仍通过。
`git diff --check` 通过。

## 浏览器验收

使用隔离 SQLite、真实 FastAPI/Vite、真实登录会话和持久化 fixture；未使用 Mock API，也未调用
模型、图片、语音、VL 或视频 Provider。

- User：`5bb07328b94245d1b3d737395f8a96d1`
- Conversation：`598efe38b32b43c7b6000b5187abd419`
- Run：`6472f91358e64e35987f81d8122f1cee`
- Workflow：`82448046f5e646eeb7fc85252f08a39a`
- Task：`c19e07a123c248aaa3b89fa3ae970bf5`
- Attempt：`559691fcab37478a96119d8e671bbbc4`
- Effect：`41ef1b5516e242efbcf2d9a1c1de3abb`

初始页面显示 state version 9、unknown 处理、取消按钮和持续递增的 Tool 等待秒数。点击“确认未知
结果失败”后，状态变为 failed/state version 10，只显示“重试失败任务”和“从检查点恢复”。首次
验收发现终态仍显示旧 Native Step 正在运行；已补充后端 Step 同步和前端终态过滤，复验及刷新后
不再显示等待。登录后的最终 Console 为 0 error / 0 warning。

截图保存在本地 QA 目录，不纳入源码：

- `output/playwright/sprint-147-unknown-long-tool.png`
- `output/playwright/sprint-147-resolved-recovery-actions.png`

## 未执行

- 未再次调用真实收费 Provider；Sprint 146 已完成真实全媒体链并暴露本 Sprint 修复的问题，本次
  用生产数据库/API/UI 路径和注入式 Provider 边界回归验证修复。
- 未对生产数据库或生产 Worker 做故障注入；备份、迁移和恢复边界已写入操作手册。

## 下一步

下一 Sprint 单独实现 Follow-up Run 与受控 Probe，不在本 Sprint 的控制命令中隐式加入分支语义。
