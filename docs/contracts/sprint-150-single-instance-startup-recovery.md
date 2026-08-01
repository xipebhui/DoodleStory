# Sprint 150：单实例启动与安全恢复

## 状态

Complete

## 背景

本地开发环境同时存在手动启动的 Uvicorn 与 `KeepAlive` LaunchAgent。第二个进程会先执行
FastAPI startup 恢复，再因 `127.0.0.1:8000` 已被占用而退出；LaunchAgent 随后再次拉起，导致
同一 Native Agent Run 被反复恢复和重复调用 Provider。

## 目标

保证同一数据库在同一台主机上只有一个 DoodleStory 后端进程能够进入 startup 恢复阶段，并将
本次事故中的受损 Run 收敛到明确终态。

## In Scope

- 在任何队列初始化和任务恢复前获取基于数据库标识的跨进程单实例锁。
- 获取锁失败时明确阻止启动，不执行内容提取、风格测试、图片、视频或 Native Agent 恢复。
- 正常关闭、startup 失败时释放锁；进程异常退出时由操作系统释放锁。
- 单元测试覆盖互斥、释放后重获、不同数据库互不干扰和 startup 失败释放。
- 停用与手动开发服务冲突的旧 LaunchAgent，使用单一启动入口恢复本地服务。
- 将事故 Run 标记为失败并保留原 Trace、事件与执行事实。
- 升级真实开发库到 Sprint 148 migration head，并验证页面、Trace 与全量检查。

## Out of Scope

- 不引入 Redis、外部队列、分布式租约或多 Worker 调度。
- 不自动重试或重新执行事故 Run。
- 不合并当前主工作区未提交的 Grok 图片 Provider 改动。
- 不实施 Sprint 148 延后的 Probe 或 Evaluation。

## Done Means

- 第二个指向同一数据库的后端实例在任何恢复副作用发生前启动失败，并输出可操作错误。
- 第一个实例退出后，新实例能够正常取得锁并恢复合法任务。
- 事故 Run 不再处于 resumable 状态，且历史 Trace/事件仍可查询。
- 本地 `8000` 与 `3000` 各只有一个监听进程，LaunchAgent 不再循环重启。
- 开发库迁移到当前 head，`./scripts/check.sh` 与聚焦回归通过。

## Verification

1. 运行单实例锁和应用 startup 聚焦测试。
2. 对临时 SQLite 运行 Alembic 全量升级。
3. 运行 `./scripts/check.sh`。
4. 启动本地服务后尝试启动第二个后端，确认其在恢复前失败。
5. 查询事故 Run、事件数和 Artifact 数，确认终态稳定且没有新增恢复事件。
6. 浏览器打开事故会话，检查页面可达、终态与 Console。

## Handoff

Sprint 完成后，后续 Grok 图片 Provider 工作需要在独立迁移 revision 下与 Durable Runtime 分支
整合；不得复用 Sprint 144 已占用的 migration revision。
