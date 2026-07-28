# Sprint 131：API UTC 时间与东八区展示

## Status

Complete。用户于 2026-07-28 确认系统所有时间应按东八区展示，并同意采用“数据库保存 UTC、
API 返回明确 UTC 时区、前端按 Asia/Shanghai 展示”的方案。

## Goal

消除数据库无时区 UTC 时间经 API 返回后被浏览器误当成本地时间的问题，使系统时间在任意浏览器
运行时区下都稳定显示为中国标准时间。

## In scope

- 保持 SQLite `CURRENT_TIMESTAMP` 和现有 `datetime.utcnow()` 的 UTC 存储语义，不修改历史值。
- `ApiData`、`ApiList` 中所有 datetime 在响应序列化前统一规范为 UTC，并输出 `Z`。
- Native Agent SSE 和普通 Agent SSE 的 datetime 使用同一 UTC 序列化规则。
- 前端日期、时间、今天/昨天分组固定使用 `Asia/Shanghai`，不依赖浏览器或服务器本地时区。
- 增加后端测试，覆盖 naive UTC、带时区 datetime 和嵌套响应。

## Out of scope

- 把数据库历史时间整体加 8 小时。
- 修改操作系统、Docker 或数据库 Session 时区。
- 增加用户自选时区设置。

## Done means

- API datetime 字符串包含 `Z`，不再返回无时区 ISO 字符串。
- 东八区 `15:00` 对应的 UTC `07:00Z` 在前端显示为 `15:00`。
- 今天/昨天分组以 `Asia/Shanghai` 的自然日为准。
- 后端测试、前端构建、`./scripts/check.sh` 和 `git diff --check` 通过。

## Verification

- 4 项 API 时间序列化测试通过，覆盖 naive UTC、带 `+08:00` 时区、嵌套列表、FastAPI
  response model 和 SSE 共用格式。
- Native Agent SSE 测试确认 Run snapshot 与 Event 的 `created_at` 均以 `Z` 结尾。
- `./scripts/check.sh` 通过：289 项后端测试、空库 Alembic 升级、前端生产构建、
  Remotion TypeScript 检查和 5 项 Remotion 测试。
- `git diff --check` 通过。
