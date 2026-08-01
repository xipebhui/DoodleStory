# Sprint 149 QA：单实例启动与安全恢复

## Verdict

Pass。合同范围已完成；存在一个非阻塞的页面验收限制：浏览器没有登录态，因此未在 UI 内展开
受保护的 Trace 详情，相关终态改由数据库、启动日志和事件稳定性验证。

## Passed

- 单实例互斥：已有实例持有同一数据库锁时，第二实例在 `app.main.startup` 的第一项动作中退出，
  退出码为 3，错误明确指出已有后端持有 startup recovery lock。
- 无恢复副作用：事故 Run 的事件数在第二实例测试前后均为 245，没有新增 `run.resumed`、
  `run.recovery_queued` 或 Provider 调用。
- 锁生命周期：5 项聚焦测试覆盖同库互斥、释放后重获、不同数据库隔离、锁文件 owner PID 和
  startup 初始化失败释放。
- 事故收敛：Run `d41010e722604b758d0d909ad10a388e` 为 `failed`，历史事件与 Trace 保留，
  Artifact 数仍为 0，没有自动重跑。
- 数据库：从 `o6p7q8r9s0t1` 备份按正式迁移链升级到 `t1u2v3w4x5y6 (head)`；11 张
  `agent_durable_*` 表存在，`PRAGMA integrity_check` 返回 `ok`。
- 服务：`GET /health` 返回 `{"status":"ok"}`；`8000` 和 `3000` 各一个监听进程；backend 与
  frontend launchd job 的 `runs=1`、`state=running`。
- 全量回归：`./scripts/check.sh` 通过 372 项后端测试、空库全迁移、14 项前端测试、前端生产
  构建、Remotion 类型检查和 5 项测试。
- 页面：目标 URL `http://127.0.0.1:3000/agent/203c78f2cad74940a23d33f05c6f23d8`
  返回 DoodleStory 登录页，浏览器 Console 0 error / 0 warning。

## Failed

- 无。

## Not Checked

- 未在已登录 UI 中展开事故 Run 的 Trace、控制状态和失败提示；当前浏览器没有可用登录态，且
  本 Sprint 不创建或重置用户凭据。
- 未重试事故 Run，也未调用真实模型、图片、视频或音频 Provider，避免产生额外费用和重复副作用。

## Findings

1. 根因不是单次 Writer 超时，而是旧 LaunchAgent 在端口被占用时每 10 秒重启；FastAPI startup
   又发生在 Uvicorn 绑定端口前，导致每轮失败启动都先执行恢复。
2. 未提交 Grok migration 与正式 Sprint 144 migration 使用相同 revision ID，Alembic 会出现
   “显示 head 但核心表缺失”的假迁移状态。运行库已恢复正确，源码整合前必须重命名该 revision
   并重新基于 `t1u2v3w4x5y6` 建立迁移。

## Next

- 将当前主工作区的 Grok 图片 Provider 改动移植到 Durable Runtime 分支时，创建新的唯一
  migration revision，并对真实备份副本验证 upgrade/downgrade/upgrade。
- 如需补做 UI Trace 验收，由用户在本地页面登录后重新打开目标 URL；不需要重新执行 Run。
