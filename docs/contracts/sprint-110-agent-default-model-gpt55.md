# Sprint 110：Agent 默认模型切换为 gpt-5.5

## Status

Complete（2026-07-22）。

## Goal

将 Agent Runtime 在火苗主平台和 LIO 备用平台共用的默认模型统一从 `gpt-5.6-terra` 切换为 `gpt-5.5`，并重启本地开发服务。

## In scope

- 更新 `AGENT_MODEL` 代码默认值与环境变量示例。
- 更新 Agent 漫画 Panel 的模型快照和默认探测脚本。
- 同步受影响的测试、产品规格与进度记录。
- 重启本地前后端服务，检查端口、健康接口和实际加载的配置。

## Out of scope

- 不改动旧 Pipeline 的 `TEXT_FALLBACK_MODEL=gpt-5.4`。
- 不重写历史兼容性报告中的真实模型记录。
- 不修改模型错误分类、重试或 fallback 策略。

## Verification

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest \
  backend.tests.test_agent_model_router \
  backend.tests.test_agent_runner_recovery \
  backend.tests.test_agent_sdk_compatibility
./scripts/check.sh
./scripts/restart-dev.sh
```
