# Sprint 94 合同：风格测试异步历史列表

## Goal

把风格测试从同步请求改成可持续读取状态的异步流程。用户发起测试后，即使切换页面或点击其它区域，也能在当前风格下看到所有测试用例、运行状态、结果图和失败原因。

## In Scope

- `POST /styles/{style_id}/tests` 只创建风格测试记录并触发后台执行，立即返回 `queued` 或 `running` 状态。
- 新增 `GET /styles/{style_id}/tests`，按当前风格读取最近测试历史列表，包含测试文本、状态、结果图、失败原因和时间。
- 前端风格测试页展示当前风格下的历史测试列表，并在有 `queued` / `running` 测试时轮询刷新。
- 用户发起测试后清空输入框，但不清空历史列表。
- 风格测试仍使用既有 `style_tests` 表、积分占用/扣费/释放逻辑和当前风格参考方式。
- 服务启动时把历史遗留 `queued` / `running` 风格测试标记为失败并释放可识别的积分占用，避免界面长期显示卡住。

## Out of Scope

- 不新增外部队列、独立 worker、Redis、Celery 或复杂工作流引擎。
- 不把风格测试迁移到 `generated_images` 图片 job 表。
- 不新增风格测试重试、取消或批量删除。
- 不跨风格展示全局测试历史。

## Deliverables

- 后端风格测试后台执行函数与启动恢复。
- 风格测试历史列表 API。
- 前端风格测试页历史列表、运行态轮询和结果展示。
- 单元测试覆盖异步创建、后台成功/失败结算和历史列表读取。
- 规格和进度记录更新。

## Done Means

- 点击生成测试图后，接口立即返回，页面显示该测试正在生成。
- 测试过程中切换交互不会丢失当前风格测试记录。
- 当前风格下历史测试结果可读取，成功项展示结果图，失败项展示失败原因。
- `./scripts/check.sh` 通过。

## Verification

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_style_delete backend.tests.test_credits
backend/.venv/bin/python -m compileall backend/app
npm run build --prefix frontend
git diff --check
./scripts/check.sh
```
