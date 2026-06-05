# Sprint 17 合同：生图 timeout 自动重试

## 目标

图片 Provider 生图或结果图下载出现 timeout 时，自动重试 3 次，任一重试成功即停止，减少偶发网络超时导致的失败图片。

## 范围内

- 新增 `IMAGE_PROVIDER_TIMEOUT_RETRY_ATTEMPTS` 配置，默认 `3`。
- timeout 判定覆盖：
  - `requests.Timeout` 异常。
  - HTTP `408` 和 `504` 响应。
  - Provider 错误响应正文中明确包含 `timeout`、`timed out`、`read timed out` 或 `connection timed out`。
- 生图请求和结果图下载均使用 timeout 专用重试次数。
- 非 timeout 错误仍按现有错误处理，不因为本次改动被无限或静默重试。
- 更新规格、进度和当前合同记录。

## 范围外

- 不引入外部队列、独立 worker 或新的任务状态机。
- 不改变用户手动重试接口。
- 不改变图片生成并发配置。
- 不隐藏最终失败错误；timeout 重试耗尽后仍写入明确失败信息。

## 完成标准

- timeout 失败最多自动重试 3 次，成功后不继续重试。
- 非 timeout 的 provider 配置错误、校验错误和永久失败不会走 timeout 重试。
- `backend/.venv/bin/python -m compileall backend/app` 和 `./scripts/check.sh` 通过。

## 验证

自动验证：

```bash
backend/.venv/bin/python -m compileall backend/app
./scripts/check.sh
```

功能验证：

1. 用单元级 smoke 模拟连续 timeout 后成功，确认总调用次数为 4。
2. 用单元级 smoke 模拟非 timeout 请求异常，确认不会使用 timeout 专用 4 次尝试。
