# Sprint 194：Windows SQLite 绝对路径 URL 解析修复

状态：Complete

## Goal

修复 `Settings.resolved_database_url` 在 Windows 上把盘符和反斜杠百分号编码成字面文件名的问题，使应用、
Alembic 和 G3 临时数据库都连接到请求的真实 SQLite 文件，同时不改变非 SQLite URL 或数据库业务结构。

## In scope

- SQLite 相对路径继续相对项目根目录解析。
- SQLite 绝对路径使用 SQLAlchemy 可识别的 `sqlite:///C:/...` 形式，不把 `C:`、目录分隔符编码为文件名。
- 新增 Windows 绝对路径、含空格路径、相对路径和非 SQLite URL 测试。
- 用 Alembic 对新的临时绝对路径执行 `upgrade head`，确认 `users` 和 `alembic_version` 位于目标文件。
- 保留 G3 Attempt 1 的 `stop_before_media` 报告；修复后创建新的 G3 Attempt 2，不覆盖旧证据。

## Out of scope

- 不修改 schema、迁移历史、生产数据库内容或默认数据库配置。
- 不搬迁、重命名或删除现有 `doodlestory.db`。
- 不发起 SiliconFlow、图片、语音、视频或发布调用。
- 不把 G3 Attempt 1 改写为通过。

## Done means

- 给定 Windows 绝对 SQLite 文件时，SQLAlchemy 只创建该目标文件，不在工作目录创建 `%3A` / `%5C` 名称。
- Alembic `upgrade head` 后目标文件包含当前 head 与核心表。
- 配置聚焦测试、完整后端回归、compileall 和 `git diff --check` 通过。
- G3 Attempt 1 报告仍可读且请求计数为 0。

## Verification

```powershell
& backend/.venv/Scripts/python.exe -m unittest backend.tests.test_config
& backend/.venv/Scripts/python.exe -m unittest discover -s backend/tests
& backend/.venv/Scripts/python.exe -m compileall backend/app
git diff --check
```

## Handoff

修复提交后，更新 G3 脚本来源 commit 并执行新的 Attempt 2。该修复只解除本地数据库前置阻断，不自动开放
G4 或任何媒体调用。

## Verification record

- 配置与 G3 聚焦测试：11 项通过。
- 完整后端：409 项通过。
- 真实 Alembic 临时绝对路径升级：64 张表、`users` 存在、head 为 `w4x5y6z7a8b9`。
- 编码路径孤儿检查：0；Python compileall 与 `git diff --check` 通过。
- G3 Attempt 1 失败报告已归档；Provider、图片、语音、视频和发布请求仍为 0。
