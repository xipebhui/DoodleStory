# Sprint 118：Skill 管理正常入口与导航闭环

## Status

Complete（Closed）。用户于 2026-07-26 反馈 Sprint 117 的 Skill 管理虽然可通过
`/agent/skills` 直接访问，但无法从传统工作台主导航直接进入，并明确要求修复和优化。

Deferred Agent Evaluation 不属于本 Sprint，不实施。

## Completion evidence

- 传统工作台主侧栏已新增稳定链接 `/agent/skills` 的 `Skill 管理` 入口。
- Skill 管理的 Agent Studio 侧栏已新增稳定链接 `/tasks` 的 `返回传统工作台` 入口。
- 真实浏览器已完成 `/tasks → /agent/skills → /tasks` 往返，并验证后退恢复 Skill 管理、
  前进恢复传统工作台。
- `npm run test:agent-routes` 4 项通过，`npm run build` 通过。
- `./scripts/check.sh` 通过 252 项后端测试、Python compileall、空 SQLite migration 和前端
  生产构建。

## Background

Sprint 117 已完成 Skill 管理、版本和通用 Agent Loop，但正式入口只存在于独立 Agent
Studio 左侧导航。用户从默认 `/tasks` 进入产品时，必须先理解并点击页面内容区的
`AI 构建`，再在另一套侧栏中找到 `Skill 管理`。这使已完成能力缺少正常、稳定且容易发现的
产品入口。

同时，Skill 管理页面的 Agent Studio 侧栏没有返回传统工作台的导航，进入后缺少明确的往返
路径。

## Goal

让已登录用户从默认传统工作台侧栏一键进入 Skill 管理，并能从 Skill 管理明确返回传统工作台。

## Scope

- 传统工作台主侧栏新增 `Skill 管理` 导航项，稳定链接到 `/agent/skills`。
- 主侧栏所有导航继续使用真实 URL，并通过现有前端路由保持刷新、前进和后退行为。
- Agent Studio 的 Skill 管理侧栏新增 `返回传统工作台` 导航，稳定链接到 `/tasks`。
- 保留 Agent Studio 内已有 `Skill 管理` 入口和独立 Shell，不把 Skill 编辑器复制进传统 Shell。
- 更新进度、路线图和交接状态。

## Out of scope

- Skill 数据、API、版本或 Runtime 语义变化。
- Agent Studio 信息架构重写。
- 新增 Skill 能力、Tool、Evaluation 或发布门槛。
- 移动或复制 Skill 编辑器页面。

## Acceptance criteria

1. 已登录用户访问 `/tasks` 时，主侧栏直接显示 `Skill 管理`。
2. 点击该入口后进入 `/agent/skills`，页面显示真实 Skill 列表和创建入口。
3. Skill 管理侧栏显示 `返回传统工作台`；点击后返回 `/tasks`。
4. `/agent/skills` 与 `/tasks` 直接访问、刷新、前进和后退保持稳定。
5. 普通用户和 Admin 均可看到同一入口，后端权限规则不变。
6. 前端生产构建、Agent 路由测试和真实浏览器往返验收通过。

## Verification

```bash
cd frontend
npm run test:agent-routes
npm run build
```

浏览器验收：

1. 登录后从 `/tasks` 主侧栏点击 `Skill 管理`。
2. 确认 URL 为 `/agent/skills` 且系统 Skill 可见。
3. 点击 `返回传统工作台`，确认 URL 为 `/tasks`。
4. 使用浏览器后退和前进确认两页可恢复。

## Done means

- Acceptance criteria 全部通过。
- `docs/progress.md`、路线图和交接文档记录结果。
- 创建符合仓库规范的中文详细提交。
