# Sprint 100 合同：图文任务失败飞书告警

## Goal

当正式图文生成任务进入 `failed` 状态时，向配置的飞书自定义机器人 webhook 发送一次告警，帮助运营及时发现线上任务失败。

## In Scope

- 为 `generation_tasks` 增加 `failure_alert_sent_at`，记录同一次失败状态是否已经发送过告警。
- 新增任务失败告警服务：
  - 使用 `TASK_FAILURE_ALERT_WEBHOOK_URL` 配置飞书 webhook。
  - 使用飞书自定义机器人文本消息格式发送告警。
  - 告警包含任务 ID、标题、用户 ID、输入模式、当前步骤、生图模型、风格、错误码、错误信息、失败时间和可选任务链接。
  - 不包含用户原始全文，避免把长文本或敏感内容推到群里。
- 接入生成任务 worker 中会把 `GenerationTask` 标记为 `failed` 的路径：
  - 人物参考图全部失败。
  - panel 图片全部失败。
  - 服务重启恢复时不可恢复的中断任务。
  - 任务步骤异常失败。
  - worker 未处理异常失败。
- 任务手动重试时清空 `failure_alert_sent_at`，如果重试后再次失败，应再次告警。
- 更新部署文档、规格和进度记录。

## Out of Scope

- 不给 `partial_succeeded` 发送告警。
- 不给内容提取任务、视频任务或风格测试失败发送告警。
- 不把飞书 webhook URL 写入仓库；线上通过环境变量配置。
- 不因告警发送失败改变任务原本失败状态或覆盖原错误原因。

## Deliverables

- 后端配置、迁移、模型字段、告警服务和 worker 接入。
- 后端单元测试。
- 部署文档、规格和进度记录同步。

## Done Means

- 配置 webhook 后，图文生成任务首次进入 `failed` 会发送一条飞书文本告警。
- 同一个 failed 状态重复被恢复/检查时不会重复发送。
- 用户点击重试后如果再次失败，会重新发送告警。
- webhook 调用失败时，任务仍保持原失败状态，日志记录告警发送失败，并保留未发送状态以便后续失败处理再次尝试。

## Verification

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_task_failure_alerts backend.tests.test_task_worker_recovery
backend/.venv/bin/python -m compileall backend/app
git diff --check
./scripts/check.sh
```

## Risks / Notes

- 飞书 webhook URL 是部署密钥，只能配置在环境变量或远程 `.env`，不能提交到 git。
- 任务链接依赖 `TASK_FAILURE_ALERT_TASK_BASE_URL` 或 `FRONTEND_ORIGIN`，未配置时告警只包含任务 ID。
