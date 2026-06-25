# Sprint 75 合同：xgapi 参考图 multipart 提交修复

## 目标

修复本地 `IMAGE_PROVIDER=xgapi` 时，带人物参考图或风格参考图的生图请求失败的问题。

## 背景

本地任务 `c670fff321c644e3abc215f4abcb411d` 的人物参考图和 panel 生图都需要携带参考图。xgapi 的 `/v1/images/edits` 接口不接受 JSON URL 数组形式的参考图，会返回 `failed to parse multipart form` / `convert_request_failed`。真实 curl 验证显示该接口需要 `multipart/form-data`，并且 `image` 字段必须上传真实图片文件；同时 edit 接口的 `quality` 只接受 `auto`、`low`、`medium`、`high`。

## 范围内

- xgapi 有参考图时，继续调用 `/v1/images/edits`，但改为下载参考图 URL 后以 multipart 文件字段提交。
- xgapi 无参考图时，继续使用 `/v1/images/generations` JSON 请求。
- xgapi edit 请求把生成接口使用的 `1k`、`2k`、`4k` 质量配置转换为 edit 接口支持的 `high`。
- 非支持质量配置继续明确报错。
- 增加单元测试覆盖 xgapi 参考图 multipart 请求结构和 edit quality 转换。
- 用真实本地任务重试验证人物参考图和 panel 图都能成功生成。

## 范围外

- 不改变当前 provider 选择。
- 不引入 QY/xgapi 自动切换或模型兜底。
- 不改变人物参考、风格参考和最终 prompt 编译规则。
- 不自动重跑历史任务。

## 交付物

- `backend/app/services/image_generation.py`
- `backend/tests/test_image_generation_gateway_only.py`
- `docs/spec.md`
- `docs/progress.md`

## 完成标准

- xgapi 带参考图请求不再因 multipart 解析失败而失败。
- 人物参考图和 panel 生图都能携带参考图真实生成。
- 本地任务 `c670fff321c644e3abc215f4abcb411d` 重试后成功。
- 相关测试和全量检查通过。

## 验证

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_image_generation_gateway_only backend.tests.test_task_worker_prompt
backend/.venv/bin/python -m compileall backend/app
git diff --check
./scripts/check.sh
```
