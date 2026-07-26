# Sprint 121：Skill 详情与编辑闭环

## Status

Complete（Closed）。用户于 2026-07-26 指出当前 Skill 管理缺少清晰的查看详情和编辑能力。

正式 Evaluation、评分规则和发布门槛继续保持 Deferred，本 Sprint 不实施 Evaluation。

## Goal

1. Skill 列表对每项提供明确的“查看详情”入口。
2. 个人且未归档的 Skill 在列表和详情页都提供明确的“编辑”入口。
3. Skill 详情与编辑使用不同稳定 URL，刷新、前进和后退均能恢复当前页面。
4. 系统 Skill 和已归档 Skill 详情保持只读；系统 Skill 可从详情复制为个人 Skill。

## Scope

- 新增 `/agent/skills/{skill_id}/edit` 编辑路由。
- 保留 `/agent/skills/{skill_id}` 作为只读详情路由。
- 详情展示名称、适用场景、状态、Tools、草稿 revision、当前发布版本、更新时间和完整正文。
- 个人可编辑 Skill 的详情提供“编辑 Skill”；列表同时提供“查看详情”和“编辑”。
- 现有草稿保存、发布、版本、归档、恢复、复制和未保存离开确认继续复用。
- 增加路由自动化和真实浏览器验收。

## Out of scope

- 修改 Skill 数据库、API、发布语义或 Runtime 加载逻辑。
- 系统 Skill 或归档 Skill 的原地编辑。
- Workflow DSL、多 Skill、脚本、MCP、自定义 Tool。
- Deferred Evaluation。

## Verification

1. 路由测试覆盖详情与编辑 URL，并拒绝不完整路径。
2. 个人 Skill 可从列表进入详情，再进入编辑、修改并保存，保存后返回详情。
3. 系统 Skill 详情无编辑入口，表单不可写，复制入口仍可用。
4. 浏览器刷新、返回和前进保持详情/编辑页面。
5. `./scripts/check.sh` 与 `git diff --check` 通过。

## Verification result

- 路由自动化覆盖详情、编辑、URL decode 和非法多余路径，共 4 项通过。
- 真实浏览器确认系统 `简单图片故事` 详情完整显示正文、权限、Tools 和版本，只有返回与复制动作。
- 从系统 Skill 复制个人草稿后，详情出现“编辑 Skill”；编辑描述并保存后自动返回详情，
  `draft_revision` 从 1 更新为 2。
- 详情刷新、保存后的后退与前进均恢复对应稳定 URL；浏览器控制台 0 error / 0 warning。
- `./scripts/check.sh` 通过 257 项后端测试、Python compileall、空 SQLite migration 和前端
  生产构建；`git diff --check` 通过。

## Done means

- 用户不再需要猜测同一个页面当前是查看还是编辑。
- 权限差异在按钮和页面状态中明确可见。
- 文档、规格、进度、实现和验证结果一致，并创建中文详细 commit。
