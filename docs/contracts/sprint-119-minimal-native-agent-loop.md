# Sprint 119：最小原生 Agent Loop

## Status

Complete（Closed）。用户于 2026-07-26 明确要求停止沿用旧漫画工作流的后端编排方式，创建隔离分支，
从“一个通用 Loop、一个真实生图 Tool、一个发布版 Skill”重新开始。

Deferred Agent Evaluation 不属于本 Sprint，不实施。

## Background

Sprint 117 虽然完成了 Skill 管理和版本固定，但正式执行仍由 Python 代码决定漫画规划、
方案审批、Panel 创建、图片队列和最终汇总。Tool schema 被写入 Instructions，而不是作为
Agents SDK 的真实 `tools` 传入；因此当前实现不是模型驱动的 Tool Loop。

## Goal

交付一条与旧 `GenerationTask / ComicPlan / AgentStep / GenericToolExecutor` 编排隔离的最小
纵向链路：

```text
用户输入 + 发布版 Skill + 可选 Style
→ Agents SDK Runner
→ 模型决定是否调用 generate_image
→ Runtime 执行真实生图
→ 图片作为 ToolOutputImage 回到同一个模型
→ 模型检查图片并决定继续生图或 final_output
```

## Architecture boundaries

1. Runtime 只负责加载上下文、运行 Agents SDK、执行一个 Tool、保存结果和返回终态。
2. 故事改写、分镜切割、图片 Prompt 编写、图片 Review 和是否重画全部由 Skill 指导模型。
3. Python 不根据 Skill 名称、Style 是否存在、Panel 数量或漫画阶段编写业务分支。
4. `generate_image` 必须通过 `Agent(tools=[...])` 注册为真实 Function Tool。
5. 生图结果必须使用 `ToolOutputImage` 回填同一 SDK Loop，不新增独立 VL Tool。
6. 第一版 Tool 串行执行；并发、队列、审批、恢复和 Evaluation 后续单独叠加，不提前实现。
7. 不复用旧 Agent Runtime 的 Artifact、Approval、Step、Task、Panel、GeneratedImage 或
   GenericToolExecutor 数据模型。
8. Skill 管理、用户、Style 和底层文件存储/图片 Provider 作为外围产品能力复用，但不能反向
   控制 Loop。

## Scope

- 新增独立的最小 Agent Loop 数据表：Conversation、Run、Item、Image。
- Run 固定一个已发布 Skill Version，并保存可选 Style 的执行快照。
- 新增独立 API：创建/查看会话、发送一轮消息并执行真实 Loop。
- 生图 Tool 使用 Style 固定的模型、比例和参考图；Prompt 由模型完整提供，Runtime 不做隐藏
  Prompt 拼接。
- 生图成功后保存文件资产和最小图片记录，并把图片内容返回模型视觉检查。
- 新增最小前端入口，复用现有认证、Skill 选择、Style 选择和图片资产展示。
- 新增自动化，证明 SDK 收到且执行真实 Tool、图片回到模型、没有调用旧漫画编排。

## Out of scope

- 旧 Agent 数据迁移或兼容转换。
- 自动 Skill 选择、多 Skill、用户自定义 Tool、MCP、脚本或 Workflow DSL。
- ComicPlan、人工审批、Panel 编辑、版本恢复、暂停、取消和跨进程恢复。
- 图片 Tool 并发、后台队列和 Provider fallback。
- 积分结算；第一版真实链路只验证 Loop 边界，积分接入在后续合同中单独设计。
- 正式 Evaluation、阈值或 GO/NO-GO。

## API

- `POST /api/v1/agent-loop/conversations`
- `GET /api/v1/agent-loop/conversations`
- `GET /api/v1/agent-loop/conversations/{conversation_id}`
- `POST /api/v1/agent-loop/conversations/{conversation_id}/runs`

发送 Run 必须显式提供：

- `content`
- `skill_version_id`
- 可选 `style_id`

Skill 未发布、无权访问或没有授权 `generate_image` 时明确失败；Style 不存在、未激活或无权读取
参考资产时明确失败。

## Verification

1. 单元测试使用可控模型验证纯文本 final 不调用 Tool。
2. 单元测试验证 `generate_image` 是真实 Function Tool，Tool 输出同时包含安全文本元数据和
   `ToolOutputImage`。
3. 单元测试验证 Runner 只收到该真实 Tool，并固定 `max_turns` 与串行 Tool 并发限制。
4. API 权限和新表 migration 测试通过。
5. 前端生产构建通过。
6. `./scripts/check.sh` 通过。

## Verification result

- 2026-07-26 `./scripts/check.sh` 通过：256 项后端测试、Python compileall、空 SQLite
  Alembic migration 与前端生产构建全部成功。
- 真实浏览器确认正常 `/agent` 入口、Skill/Style 选择、运行按钮状态、会话侧栏与
  `/agent/{conversation_id}` 详情入口；`/agent/skills` 可查看新的系统
  `简单图片故事 v1`，页面控制台无错误。
- 自动化确认 `generate_image` 是 Agents SDK `FunctionTool`，成功输出
  `ToolOutputImage(detail="high")`，Runner 只注册该一个 Tool 且 Tool 并发固定为 1。
- 本次没有点击浏览器“运行 Agent”，因此没有新增真实模型或图片 Provider 费用；外部 Provider
  实跑作为显式成本验收保留，不以 Mock 或占位结果冒充完成。

## Done means

- 正常入口可以创建并查看最小 Loop 会话。
- 执行路径不导入或调用旧漫画 Runner/Workflow。
- 代码、合同、规格和进度一致。
- 创建符合仓库规范的中文详细 commit。
