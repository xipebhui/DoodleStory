# Sprint 77 合同：xgapi 无参考图质量参数修复

## 目标

修复 xgapi 无参考图生图请求仍发送 `quality=1k`，导致人物参考图生成失败的问题。

## 背景

任务 `50c796217bdf4e299359c51e74e9f662` 在人物参考图阶段失败。该任务风格没有风格参考图，人物参考图请求不携带参考图，因此走 xgapi `/v1/images/generations` JSON 分支，而不是上一轮已修复的 `/v1/images/edits` multipart 分支。xgapi 返回 HTTP 400：`quality must be one of: auto, low, medium, high`，说明无参考图 generation 分支也不能发送 `1k`。

## 范围内

- 将 xgapi 质量参数转换抽成通用函数。
- `/v1/images/generations` 和 `/v1/images/edits` 都使用同一套 `auto/low/medium/high` 质量参数。
- 兼容现有 `XG_IMAGE_QUALITY=1k/2k/4k` 配置，统一转换为 `high`。
- 非支持质量配置继续明确报错。
- 更新单元测试覆盖无参考图 generation JSON 分支的质量参数。

## 范围外

- 不改变 provider 选择。
- 不引入模型兜底或自动切换。
- 不改变人物参考 prompt、风格参考 prompt 或任务重试语义。

## 交付物

- `backend/app/services/image_generation.py`
- `backend/tests/test_image_generation_gateway_only.py`
- `docs/spec.md`
- `docs/progress.md`

## 完成标准

- xgapi 无参考图请求不再发送 `quality=1k`。
- 任务 `50c796217bdf4e299359c51e74e9f662` 重试后人物参考图阶段能通过。
- 相关测试和全量检查通过。

## 验证

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_image_generation_gateway_only
backend/.venv/bin/python -m compileall backend/app
git diff --check
./scripts/check.sh
```
