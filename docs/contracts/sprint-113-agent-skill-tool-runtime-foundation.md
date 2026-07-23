# Sprint 113：通用 Skill / Tool Runtime 基础

## Status

Planned。只有 Sprint 112 Complete 后才能激活。

## Goal

在保留现有 Conversation、Run、Step、进程内队列、主备模型路由和图片 job 可靠性契约的基础上，建立一个最小、可测试的 Skill/Tool 运行内核，使 Agent 能按需加载创作 Skill，并通过统一 Tool 执行边界调用现有 `generate_image` 能力。此 Sprint 不交付新的创作流程，不引入业务 Workflow DSL。

## Architecture decision

本项目后续采用：

```text
通用创作 Agent
  + 按需加载的 Skill（方法、步骤、质量门槛）
  + 原子 Tool（真实外部能力）
  + 通用 Runtime（权限、预算、幂等、等待、恢复、取消、观测）
```

明确不采用：

- 为每种创作方式写一套硬编码 Workflow。
- 把旧 Pipeline 的故事补齐、分镜、Prompt 拼接包装成多个伪 Tool。
- 通用低代码工作流编辑器。
- 多 Agent。
- 复杂 Skill DSL 或远程 Skill 市场。

## User-visible outcome

本 Sprint 主要是运行内核重构，正式用户行为保持不变。开发者可以：

- 列出 Runtime 可用 Skill 元数据。
- 让 Agent 通过 `load_skill` 读取一个 Skill 的完整说明。
- 看到已加载 Skill 的 ID、版本和内容 hash 被持久化并进入 MLflow trace。
- 通过统一 Tool Executor 执行或恢复一个真实 `generate_image` Tool Call。
- 证明同一 Tool Call 重放不重复创建图片 job 或扣费。

## Skill package contract

Runtime Skill 放在：

```text
backend/app/agent_skills/<skill-id>/SKILL.md
```

它与仓库根目录 `.agents/skills/` 不同：

- `.agents/skills/` 服务 Codex 开发协作。
- `backend/app/agent_skills/` 是 DoodleStory 产品运行时读取的创作 Skill。

`SKILL.md` 使用最小 frontmatter：

```yaml
---
name: idea-to-comic
description: 把一个想法整理为连续漫画方案并在用户确认后生成图片。
version: 1
---
```

规则：

- `name` 与目录名一致。
- `description` 用于基础 instructions 中的 Skill catalog。
- `version` 为正整数；内容发生会影响行为的变化时必须递增。
- Runtime 自动计算完整文件 SHA-256，不要求作者手写 hash。
- `SKILL.md` 必须完整读取；可选 `references/` 只由 Skill 明确引用时加载。
- 本 Sprint 不增加 manifest DSL、条件表达式或图结构。

## In scope

### 1. Skill Registry

实现小型代码级 `SkillRegistry`，职责：

- 启动时扫描受控 Skill 根目录。
- 校验目录名、frontmatter、版本、重复 name 和文件大小上限。
- 生成有界 catalog：`name/description/version/content_hash`。
- 按精确 Skill name 加载完整正文。
- 拒绝路径穿越、任意绝对路径和未注册 Skill。
- 测试环境允许显式注入临时 Skill 根目录。

不做：

- 数据库里的用户 Skill。
- 在线编辑、上传或热更新。
- Skill 市场。

### 2. Progressive disclosure

基础 Agent instructions 只注入 Skill catalog 和使用规则，不注入所有 Skill 正文。

模型可见只读 Tool：

```json
{
  "name": "load_skill",
  "arguments": {
    "skill_name": "idea-to-comic"
  }
}
```

成功输出：

```json
{
  "name": "idea-to-comic",
  "version": 1,
  "content_hash": "sha256:...",
  "instructions": "完整 Skill 正文"
}
```

加载行为必须写入 AgentStep 和 MLflow span，不能只存在内存。

### 3. 最小 Tool Registry

实现代码级 Tool 定义与执行映射，第一版只注册：

- `load_skill`：只读、同步、无费用。
- `generate_image`：有外部副作用、异步图片 job、有积分与幂等要求。

每个 ToolDefinition 至少声明：

- tool name；
- 模型可见 input schema；
- 用户安全 output schema；
- 是否有副作用；
- 是否需要授权资源；
- 是否可能等待异步 job；
- 预算计数种类。

不允许把数据库 Session、Provider、API key、用户 ID 或幂等键暴露给模型参数。

### 4. Generic Tool Executor

统一执行器必须：

1. 在副作用前持久化 `tool_call` AgentStep。
2. 从 Run、Conversation 和已解析资源构造 RuntimeContext。
3. 校验 Tool 是否注册、参数 schema、资源权限和预算。
4. 为副作用产生稳定幂等键。
5. 调用 Tool adapter。
6. 如需等待，把 Run 置为 `waiting_for_tool` 并保存 wait checkpoint。
7. Tool 完成后先持久化 `tool_result`，再恢复模型。
8. 重放时复用已有 Step/job/result，不重复副作用。
9. 将 Skill/Tool 元数据写入 MLflow trace。

### 5. 现有 `generate_image` adapter

- 复用现有 GenerationTask、TaskPanel、GeneratedImage、图片 worker、资产和积分基础设施。
- 现有 Provider 重试、取消和晚到结果规则保持不变。
- 只把“创建/等待/返回一个图片版本”收敛进统一 Tool adapter。
- 不把旧故事拆分、Storyboard planning、最终 Prompt 编译或 policy 重写整体包装成 Tool。
- 本 Sprint 可以保留当前两格漫画业务入口，但其真实图片副作用必须能通过统一 Executor 的测试路径执行。

### 6. Persistence

默认不新增表：

- Skill 加载记录写入 `agent_steps.input_ref/output_ref` 的结构化安全 JSON。
- 记录 `skill_name`、`skill_version`、`content_hash`、`loaded_at`。
- Tool Call/Result 继续使用 AgentStep。

如果现有 AgentStep 无法表达一个必要不变量，先更新合同评审；不得提前创建通用 Skill 表或 Tool 表。

### 7. Runtime API boundary

- 不新增用户可编辑 Skill API。
- 可增加仅测试或内部使用的 service 接口，不暴露任意文件读取。
- 正式 Agent API 响应可以在 Run Step 中返回安全的 Skill/Tool 名称，但不得返回完整 Skill instructions。

## Initial bundled Skill

为验证 Registry，本 Sprint 可以加入一个最小 `idea-to-comic` Skill 包骨架，但只能包含：

- name、description、version；
- 当前阶段的高层创作目标；
- 明确写“尚未在本 Sprint 切换正式生产链路”。

它不得在正式 Agent 中被自动选择或改变现有两格行为。完整生产流程由 Sprint 114 实现。

## Out of scope

- 完整 `idea-to-comic` 生产 Skill。
- Human-in-the-loop、方案卡和事件流。
- `inspect_image`、TTS、Remotion、抠图或媒体提取 Tool。
- 用户自定义 Skill、Memory、Skill 在线管理。
- 通用 Workflow/DAG DSL。
- 资源引用扩展和 Panel 版本操作。
- 删除旧 `_invoke_comic_plan`；正式切换在 Sprint 114。

## Deliverables

- Runtime Skill 包目录和格式说明。
- `SkillRegistry`、catalog 和安全加载器。
- `load_skill` Tool。
- 最小 `ToolRegistry` 与 Generic Tool Executor。
- `generate_image` adapter 的统一执行/恢复测试。
- Skill/Tool AgentStep 与 MLflow trace。
- 测试、规格、路线与进度更新。

## Recommended implementation order

1. 定义 Skill 包格式、Registry 和路径安全测试。
2. 实现 catalog 与 `load_skill`。
3. 定义最小 ToolDefinition 和 RuntimeContext。
4. 抽取 Generic Tool Executor。
5. 将现有生图副作用适配到 Executor，不改变正式行为。
6. 做重复投递、等待恢复、取消和 trace 回归。

## Done means

1. Runtime 能扫描并校验受控 Skill 目录。
2. 基础上下文只包含 catalog；只有调用 `load_skill` 后才出现完整正文。
3. 加载 Skill 的 name/version/hash 可从 AgentStep 和 MLflow 查到。
4. 非法 Skill 名、路径穿越、重复 name 和不合法 frontmatter 明确失败。
5. `generate_image` 通过统一 Tool Executor 创建、等待和返回真实图片 job。
6. 相同 idempotency key 重放不重复创建图片 job、不重复积分占用或扣费。
7. 当前两格真实 Agent 链路无用户行为回归。
8. 未引入 Workflow DSL、外部队列、多 Agent 或通用 Tool 管理后台。

## Verification

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest \
  backend.tests.test_agent_runner_recovery \
  backend.tests.test_agent_comic_creation
backend/.venv/bin/python -m compileall backend/app
git diff --check
./scripts/check.sh
```

新增测试至少覆盖：

- catalog 有界且不泄露完整正文。
- `load_skill` 成功记录版本与 hash。
- 路径穿越、缺失文件、重复 name、错误版本拒绝。
- 未注册 Tool 和额外参数拒绝。
- 有副作用 Tool 先写 call Step 再执行。
- waiting checkpoint 与服务重启恢复。
- 重复 Tool Call 复用 result。
- 取消 Run 不启动新的图片副作用。
- MLflow span 与 AgentStep ID 对齐。

## Handoff

- Sprint 113 Complete 后，Sprint 114 才能把正式 Agent 切到 `idea-to-comic` Skill。
- 完成时明确记录哪些旧硬编码入口仍在使用，不能误报已经完成业务迁移。
- 下一 Sprint 将新增真正的方案产物、用户确认和安全事件流。

## New-window start prompt

> 请实施 Sprint 113。先完整阅读项目基线、Agent V1 路线图、`docs/contracts/sprint-113-agent-skill-tool-runtime-foundation.md`、Runtime 架构/Tool 契约、Python/数据库/后端工作流规范，以及当前 Agent Runner、Router、ComicCreation、AgentStep 和 MLflow 集成。只构建最小 SkillRegistry、`load_skill`、ToolRegistry、Generic Tool Executor 和现有 `generate_image` adapter；不要做 Workflow DSL、用户 Skill、HITL、SSE、VL、TTS、Remotion 或正式创作流程切换。保持现有真实两格行为，完成恢复/幂等/取消/观测验证后更新文档并创建中文详细 commit。
