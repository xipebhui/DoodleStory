# Sprint 90 合同：任务取消停止图片 Job 与积分扣费

## Goal

确保用户取消图文任务后，任务下尚未完成的图片 job 不会继续生图、不会在取消后落库成功结果，也不会因为取消后的生图结果扣除用户积分。

## In Scope

- `/tasks/{task_id}/cancel` 同步标记任务下 `queued` / `running` 图片 job 为 `cancelled`。
- 已有积分占用的图片 job 在取消时释放占用。
- 图片 job worker 领取任务时跳过已取消或取消中的任务。
- 图片 Provider 返回后再次检查任务取消状态；若已取消，只释放占用并保持图片 job 取消，不保存成功资产、不扣费、不复活任务状态。
- 服务重启恢复 running 图片 job 时，已取消任务下的 job 继续保持取消，不重新排队。
- 增加单元测试覆盖取消后的图片 job 领取、执行前取消和 Provider 返回前取消三种时序。

## Out of Scope

- 不新增外部队列、独立 worker 或工作流引擎。
- 不实现第三方图片 Provider 侧的请求撤销 API；当前代码没有可用的上游取消句柄，已发出的 HTTP 请求只能在返回后被本地丢弃并避免扣费。
- 不改变风格测试、单 panel 修改的独立取消能力。
- 不删除已经成功产出的历史图片资产。

## Deliverables

- 后端任务取消逻辑和图片 job worker 取消检查。
- 规格与进度记录更新。
- 取消相关单元测试。

## Done Means

- 用户取消任务后，排队图片 job 不会再被 worker 领取执行。
- 已领取但尚未调用 Provider 的图片 job 会直接取消。
- 已调用 Provider 的图片 job 即使返回成功，若任务已取消也不会保存成功图或扣积分。
- 已取消任务不会被恢复流程重新排队。

## Verification

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_task_worker_recovery
backend/.venv/bin/python -m compileall backend/app
git diff --check
./scripts/check.sh
```

## Risks / Notes

- Python 线程中已经发出的同步 HTTP Provider 请求无法被本地状态变更强制杀掉；本 sprint 保证的是取消后的本地状态、资产落库和积分扣费边界。
