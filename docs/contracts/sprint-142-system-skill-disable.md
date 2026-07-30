# Sprint 142：系统 Skill Disable / Enable

Status: Complete

## Goal

把现有 Skill 软归档能力统一呈现为 Disable / Enable，并允许管理员 Disable 系统 Skill。
Disabled Skill 保留定义、版本和历史 Run，但不再出现在 `@Skill` 资源菜单，也不能创建新的
Native Agent Run。

## In scope

- 复用 `AgentSkillStatus.archived` 与 `archived_at`，不新增数据库字段或迁移。
- 个人 Skill 的“归档/恢复”产品语言统一为 Disable / Enable。
- 管理员可以 Disable / Enable 系统 Skill；普通用户仍不能改变系统 Skill 状态。
- Skill 列表的个人与系统范围都可以按状态筛选，并显示 Disabled 状态。
- 系统 Skill 列表和详情提供明确、可恢复的 Disable / Enable 操作与确认说明。
- 系统 Skill 保持正文和版本只读；Disable 不等于允许编辑或删除版本。
- 系统 Skill 启动种子保持幂等，已 Disabled 的记录不能在服务重启时自动恢复为 published。
- 当前开发库中的全部系统 Skill 在浏览器验收中 Disable。

## State and authorization

- `published`：Enabled，可进入 `@Skill` 菜单并用于新 Run。
- `archived`：Disabled，不进入任何新资源查询或新 Run 创建。
- 有发布版本的 Skill Disable 后保留 `active_version_id`；Enable 后恢复 `published`。
- 没有发布版本的个人草稿 Disable 后，Enable 恢复 `draft`。
- 管理员只能管理自己的 Skill 和系统 Skill，不能管理其他用户的 Skill。
- 普通用户可以管理自己的 Skill，但系统 Skill 状态操作返回 403。

## Out of scope

- 不物理删除系统 Skill、历史版本或历史 Run。
- 不修改不可变 Skill Version。
- 不增加批量 API；当前三个系统 Skill 通过现有逐项状态操作完成。
- 不自动 Disable 新增的未来系统 Skill。
- 不改变 Tool 白名单、Runtime 或模型内容。

## Done means

- 管理员可以从系统 Skill 列表或详情 Disable / Enable。
- 普通用户不能 Disable / Enable 系统 Skill。
- Disabled 系统 Skill 仍可在管理页查看，但从 Native Agent 和旧 Agent 的 `@Skill` 查询中消失。
- 服务重启后 Disabled 状态保持。
- 当前开发库全部系统 Skill 为 Disabled，Agent `@` 菜单不再显示系统 Skill。
- 自动化、真实浏览器、服务重启和控制台验收通过。

## Verification

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest \
  backend.tests.test_agent_skill_management \
  backend.tests.test_native_agent_loop \
  backend.tests.test_agent_resources
npm --prefix frontend test
npm --prefix frontend run build
./scripts/check.sh
git diff --check
```

## Completion evidence

- 后端复用 `archived` 状态实现软删除，并把系统 Skill 状态变更限定为管理员；普通用户的
  越权请求由自动化测试覆盖。
- 系统 Skill 的幂等种子不会覆盖已有状态。真实服务重启前后，三个系统 Skill 均保持
  `archived`，历史版本和 `active_version_id` 保留。
- 真实浏览器通过系统 Skill 列表逐项 Disable `文案创作团队`、`简单图片故事` 和
  `想法转漫画`；重启后列表仍显示三个 Disabled 状态和对应 Enable 操作。
- Native Agent 的 `@` 资源菜单不再出现 Skill 分组，浏览器控制台为 0 error /
  0 warning；未运行收费模型或触发外部发布。
- 定向后端 44 项测试、前端 14 项测试和生产构建已通过；最终统一检查结果记录于
  `docs/progress.md`。
