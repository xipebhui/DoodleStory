# Sprint 15 合同：取消任务重试上限与 panel 生图并发

## 目标

远程任务点击重试时不再因为 `attempts >= max_attempts` 被拒绝；任务生成图片阶段支持同一任务内多个 panel 并发提交图片 Provider，减少多图任务总耗时。

## 范围内

- 取消任务人工重试次数上限：
  - `POST /api/v1/tasks/{task_id}/retry` 不再检查 `task.attempts >= task.max_attempts`。
  - 保留 `attempts` 自增用于排查和版本来源标记。
  - 不修改数据库字段，历史 `max_attempts` 字段暂时保留。
- panel 生图并发：
  - 新增 `IMAGE_GENERATION_CONCURRENCY` 配置。
  - 默认值为 `3`。
  - `1` 表示保持串行。
  - 并发只覆盖任务 `generate_images` 阶段的 panel 图片 Provider 请求。
  - 数据库写入仍在主 worker 线程完成，避免跨线程共享 SQLAlchemy Session。
- 更新规格、进度和当前合同记录。

## 范围外

- 不引入 Redis、Celery、外部队列或独立 worker 服务。
- 不改变单 panel 修改流程。
- 不改变图片 Provider 自身的内部重试次数。
- 不迁移或删除数据库中的 `max_attempts` 字段。
- 不把多个任务并行执行；本次只做单任务内 panel 生图并发。

## 完成标准

- 达到最大历史 `attempts` 的失败任务仍可点击重试。
- 任务 panel 生图请求最多按 `IMAGE_GENERATION_CONCURRENCY` 并发提交。
- 并发任务成功时仍绑定到原 panel，前端展示和下载继续按 panel 顺序读取当前图片。
- 任意 panel 失败仍会写入对应 `generated_images.error_message`，任务最终按成功数量变为 `succeeded`、`partial_succeeded` 或 `failed`。
- `backend/.venv/bin/python -m compileall backend/app` 和 `./scripts/check.sh` 通过。

## 验证

自动验证：

```bash
backend/.venv/bin/python -m compileall backend/app
./scripts/check.sh
```

功能验证：

1. 静态检查 retry 接口不再抛出“任务已达到最大重试次数”。
2. 单元级脚本模拟 5 个 panel 的 provider 调用，确认默认并发为 3 且不会串行提交全部请求。
