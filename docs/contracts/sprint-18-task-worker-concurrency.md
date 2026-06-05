# Sprint 18 合同：任务 worker 并发

## 目标

将任务队列从单个进程内 worker 串行领取任务，调整为默认 3 个进程内 worker 并发领取任务，减少多个生成任务排队等待时间。

## 范围内

- 新增 `TASK_WORKER_CONCURRENCY` 配置。
- 默认值为 `3`。
- `1` 表示保持任务级串行。
- 应用启动时按配置创建同进程 worker 池。
- worker 日志带 `worker_index`，便于确认不同任务是否由不同 worker 同时处理。
- 同一进程内避免同一个任务 ID 被重复入队后同时执行两次。
- 保持 `IMAGE_GENERATION_CONCURRENCY` 语义不变：它只控制单个任务内 panel 生图 Provider 请求并发。
- 更新规格、进度和当前合同记录。

## 范围外

- 不引入 Redis、Celery、外部队列、独立 worker 服务或分布式锁。
- 不改变任务状态机和数据库表结构。
- 不改变单 panel 修改流程。
- 不改变图片 Provider 的 timeout 自动重试次数。
- 不改变单任务内 panel 生图并发配置。

## 完成标准

- 后端启动后默认创建 3 个任务 worker。
- 同时入队多个任务 ID 时，最多 3 个任务可同时进入 `process_task`。
- 同一个任务 ID 如果重复入队，在同一进程内不会并发执行两次。
- `backend/.venv/bin/python -m compileall backend/app` 和 `./scripts/check.sh` 通过。

## 验证

自动验证：

```bash
backend/.venv/bin/python -m compileall backend/app
./scripts/check.sh
```

功能验证：

1. 单元级 smoke 模拟 5 个任务入队，确认最大同时执行任务数为 3。
2. 确认配置项 `TASK_WORKER_CONCURRENCY` 默认值为 3。
