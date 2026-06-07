# Sprint 29 合同：Gateway 失败后的 XG 备用生图

## 目标

提升 `gpt-image-2` 等统一生图 Gateway 模型不稳定时的任务完成率。主路径仍使用统一生图 Gateway；当 Gateway 按现有重试策略最终仍失败时，再显式切换到 XG 平台备用生图。

## 范围内

- 保留统一生图 Gateway 作为主 provider。
- Gateway 请求或结果图下载在重试耗尽后，如果仍抛出 Provider 响应错误，则调用 XG 备用 provider。
- XG 备用 provider：
  - 没有参考图时调用 `POST /v1/images/generations`。
  - 有参考图时调用 `POST /v1/images/edits`。
  - 多张参考图按数组字段上传。
  - 请求 `response_format=url`，返回图片 URL 后立即下载并保存为 DoodleStory 资产。
- 新增 `XG_FALLBACK_IMAGE_MODEL` 环境变量，默认 `gemini-3.1-flash-image-preview`。
- 保留现有 `XG_API_KEY`、`XG_API_BASE_URL`、`XG_PROXY_URL`、`XG_REQUEST_MAX_ATTEMPTS` 和 `XG_REQUEST_RETRY_BACKOFF_SECONDS` 配置。
- 日志明确记录从 Gateway 切换到 XG 的原因、备用模型、参考图数量和请求结果。
- 补充单元测试覆盖 fallback 路由和 XG 请求参数。

## 范围外

- 不改变风格库中的图片模型字段和模型选择 UI。
- 不在普通用户界面暴露 provider 或 API key。
- 不把配置错误静默切换到 XG；Gateway 配置缺失、模型未接入等配置错误仍应明确失败。
- 不迁移历史任务或历史生成结果。

## 完成标准

- Gateway Provider 响应错误会进入 XG 备用生图。
- Gateway 配置错误不会进入 XG 备用生图。
- 无参考图走 XG `generations`，有参考图走 XG `edits`，多图使用数组字段。
- `backend/.venv/bin/python -m unittest discover -s backend/tests`、`backend/.venv/bin/python -m compileall backend/app`、`npm run build --prefix frontend`、`git diff --check` 和 `./scripts/check.sh` 通过。
