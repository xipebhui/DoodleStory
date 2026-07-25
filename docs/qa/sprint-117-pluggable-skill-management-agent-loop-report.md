# Sprint 117 QA 闭合报告

## Sprint

`Sprint 117：可插拔 Skill 管理、版本与通用内容创作 Agent Loop`

合同：`docs/contracts/sprint-117-pluggable-skill-management-agent-loop.md`

实现提交：`d2f8f02`、`236ee15`、`0c23d9f`

复核日期：2026-07-26

## Verdict

`PASS`

Sprint 117 的数据模型、API、管理界面、`@Skill`、版本固定、数据库 Runtime、通用 Base
Instructions、Tool 白名单、ComicPlan control action、真实文本/图片 Provider 和浏览器主路径均已
闭合。没有发现阻止合同关闭的问题。正式 Evaluation、生产部署和内部开放结论不属于本 Sprint，
继续 Deferred。

## Scope Checked

- 用户 Skill 创建、草稿 revision、发布幂等、不可变 v1/v2、历史版本激活、归档/恢复/删除和系统
  Skill clone。
- 系统 Skill 种子幂等、普通用户只读、owner 隔离、Tool catalog 与未知 Tool 拒绝。
- AI 编写辅助只返回建议，不自动保存、发布或扩大 Tool 白名单。
- `/agent/skills` 列表、编辑器、版本详情、直接 URL、系统只读、确认和未保存状态。
- `@Skill` 搜索、最多一个、第二个替换、服务端安全摘要重建、跨用户/归档/非启用版本拒绝。
- Message 与 Run 同事务固定准确 `skill_version_id`，归档或 active version 改变不影响已固定 Run。
- 显式和自动 catalog selection、数据库准确版本 loader、通用 Base + Skill instructions 和白名单
  Tool schemas。
- Skill selection/load AgentStep、安全 Event 和默认脱敏 MLflow attributes。
- 无文件 `load_skill` 正式依赖、无 `process_comic_agent_run()`、无 `_invoke_comic_plan` /
  `_invoke_comic_final`，Runner 不按 Skill name 或 `AgentResourceRoute.create_comic` 编排。
- ComicPlan Artifact/Approval、批准前零图片副作用、批准后真实图片 Tool、真实 Tool Output 后模型
  汇报。
- 无 `generate_image` 权限的 Skill 只能输出文字，不能创建 GenerationTask 或图片。
- Sprint 116 的版本、VL、pause/resume、取消、重启恢复与重复投递回归测试。

## Contract Done Matrix

| 范围 | 判定 | 证据 |
| --- | --- | --- |
| Skill 管理与版本 | PASS | UI 和 API 完成创建、保存、发布 v1/v2、查看、激活 v1、归档/恢复、系统 clone；版本快照不可 PATCH/DELETE。 |
| 引用与权限 | PASS | `test_agent_resources` 覆盖真实搜索、伪造摘要覆盖、最多一个、越权/归档拒绝；消息接受测试确认 Message 与 Run 固定同一 version。 |
| 版本一致性 | PASS | `test_run_pinned_version_survives_active_switch_and_archive` 与 Runtime 恢复测试确认 active 切换和归档不改变 Run。 |
| 通用 Instructions | PASS | Base 不含固定 Panel、故事补齐、image prompt、Skill 名称或漫画汇报话术；完整方法来自数据库发布版。 |
| 通用 Runtime | PASS | 选择、pin、load、control action、Tool Call/Result、waiting、恢复和 final 均持久化；正式路径没有 Skill-name 分支或旧漫画 fallback。 |
| Tool 白名单 | PASS | 模型上下文只加入发布版本允许的 Tool schemas；初次执行和恢复均重新校验；无 Tool Skill 的真实运行未创建任务/图片。 |
| HITL 与副作用 | PASS | 两次真实漫画均在方案确认前保持 30/28 积分，批准后各生成两张并扣 2；Artifact/Approval hash 和已有恢复测试通过。 |
| 可扩展性 | PASS | UI 发布的个人两格反转 Skill 无需改代码或重启完成真实生图；另一个纯文本 Skill 走同一 Runner 并完成文字检查。 |
| UI 与活动 | PASS | 1440×900 完成管理和对话主路径，1280×800 完成版本历史/激活；活动显示名称、版本、选择/pin/load/等待，不展示正文或隐藏推理。 |
| 自动选择 | PASS | Style-only 真实消息通过 catalog 选择系统 `想法转漫画 v1`，形成两格方案并停在确认，未创建第三个任务。 |

## Evidence

### Commands run

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest \
  backend.tests.test_agent_skill_runtime_loop \
  backend.tests.test_agent_resources
backend/.venv/bin/python -m compileall backend/app
npm run build --prefix frontend
git diff --check
./scripts/check.sh
```

最终统一检查结果：

- Python compileall：通过。
- 后端单元测试：252 项通过。
- 空 SQLite `alembic upgrade head`：通过，包含 `b3c4d5e6f7a8`。
- 前端 `tsc -b && vite build`：通过。
- `git diff --check`：通过。

### Real provider and browser

- 隔离验收账号初始 30 图片积分，创建启用风格 `Sprint 117 清透水彩`，模型
  `gpt-image-2`，比例 3:4。
- 系统 `想法转漫画 v1` 生成《雨伞的回声》两格方案；批准前预计 2 积分，批准后两张真实图片
  成功，余额 30→28。
- UI 从系统版本 clone、修改并发布个人 `个人两格反转漫画 v1`，生成《最后一盆绿》两格方案；
  Run 记录个人 version/hash，批准后两张真实图片成功，余额 28→26。
- UI 发布无 Tool `故事因果检查 v1`，真实文本 Provider 输出因果/动机/结尾检查；数据库总任务数
  仍为 2、总成功图片数为 4、余额保持 26。
- 个人漫画 Skill 发布 v2 后查看 v1/v2 并重新激活 v1；已有真实 Run 仍关联原 v1 hash。
- 归档文字 Skill 后，数据库状态为 archived，历史 Message 继续保存 v1 name/version/hash 和空
  Tool 白名单。
- Style-only 请求没有显式 `@Skill`，真实选择阶段固定系统 `想法转漫画 v1`，方案等待确认且未
  扣积分。
- 1440×900 完成创建、发布、引用、确认和图片完成；1280×800 完成版本历史和旧版本激活。登录后
  验收页面没有新增 console error。

## Findings

- 未发现阻止 Sprint 117 关闭的问题。
- 正式 Runner 的图片执行仍复用 Sprint 114–116 已验证的 ComicPlan Artifact adapter 和确定性
  图片任务物化；这是合同明确允许的最小 control action，不是 Workflow DSL，也没有按 Skill
  name 分支。
- Skill 管理页面的通用 loading/error/retry、未保存提醒和键盘可访问语义由实现和构建检查覆盖；
  本轮真实浏览器重点复核了主成功路径、版本路径和两种视口，没有逐项制造每一种网络错误。
- 隔离真实验收没有启用外部 MLflow Tracking Server；Skill span attributes 和默认正文脱敏由代码
  路径与既有 observability 测试覆盖，没有做生产 MLflow UI 截图。
- 没有执行生产部署、正式 Evaluation、故障阈值或 `GO_INTERNAL/NO_GO` 判定。

## Follow-Up Required

- Sprint 117 无必需修复项。
- 保持 `docs/contracts/deferred-agent-evaluation-internal-release-gate.md` 为 Deferred；只有用户明确
  确认功能路线冻结并授权后，才能重新编号、激活和实施。
- 后续新增 TTS、Remotion、抠图或视频能力时先定义原子 Tool，再由 Skill 组合；不预建 Workflow
  DSL，也不在 Runner 增加 Skill-name 分支。
