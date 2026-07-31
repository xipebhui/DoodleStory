# Sprint 145：Agent 动态 Task 计划与聊天式过程投影

## Status

Draft。依赖 Sprint 144 的唯一 Durable Runtime、Task Attempt、append-only Checkpoint 和
文章多阶段 Gate。

## Goal

让 Skill 驱动的 Agent 不只执行一张启动时固定的任务表，而是在上游 Artifact、用户决定和
Review 结果出现后，受控地追加、替换或取消尚未执行的 Task；同时把这一演进呈现为聊天中的
“本次计划”和阶段摘要，而不是把内部 DAG 暴露为传统工作流界面。

## In Scope

### 1. 受控计划修订

- 为固定 Skill Version 定义可执行 Task 类型、角色、输入/输出 Artifact 契约、最大 Task 数量、
  最大依赖深度和允许的 Gate purpose。
- Run 启动时保存初始 Plan Revision；每次计划变化创建新的不可变 Plan Revision，并关联其来源
  Checkpoint、触发原因和计划摘要。
- 模型可建议：
  - 追加尚未执行的后续 Task；
  - 为现有未执行 Task 补充依赖；
  - 在 Review 或用户反馈后替换下游 Task；
  - 为可并行的未来工作标注并行组。
- Runtime 必须拒绝不在 allowlist 的 Task、环状依赖、越界数量、缺失输入、重写已终态 Task、
  未授权 Tool 或不符合 Skill Version 的角色。
- 计划修订只能改变未启动的下游 Task；已完成 Task、Attempt、Artifact、Gate 与 Checkpoint
  保持不可变。

### 2. 文章链路的动态分支

- 在 Sprint 144 的选题、正文和 Review 链路上实现真实计划调整：
  - 用户选题后，以已选选题 Artifact 作为输入追加或激活正文相关 Task；
  - 正文 Gate 的修改意见只失效正文及下游 Review；
  - Review 可以建议“通过”“退回正文”“需要补充研究”；对应只创建受允许的修订 Task；
  - 已批准选题和账号/Style 快照始终作为后续 Task 的事实输入。
- 文案内容、审稿报告和用户反馈必须以版本化 Artifact / Gate Decision 保存；模型生成的摘要不得
  覆盖用户原文或结构化决定。
- 不允许以一个新的自然语言“继续”创建脱离原 Run 的执行；当前 Gate 的输入、修改和批准均走
  显式控制命令。

### 3. 聊天中的计划与状态

- 初始计划以一张聊天计划卡显示当前目标、当前阶段、近端 Gate 与“后续计划”；后续 Plan Revision
  原位更新该卡或追加简洁的计划变更消息。
- 每个用户可见 Task 状态映射为自然语言，而非内部状态名，例如：
  - `正在整理候选选题`
  - `等待你确认选题`
  - `正在按已选选题写正文`
  - `Reviewer 建议补充研究`
  - `正文正在根据审稿意见修订`
- 计划卡的展开区展示阶段标题、依赖说明、产物摘要和状态；不展示 Task ID、Attempt、lease、
  Tool arguments、模型推理或 Provider 原始内容。
- Gate 卡必须在聊天当前语义位置展示待审产物、可选动作、反馈输入和动作后果，例如
  “批准选题并开始写正文”“退回正文并重新审稿”。
- 阶段完成、失败、修订、取消和等待状态通过 SSE 增量更新；刷新或 sequence 缺口必须按
  Conversation Projection 重建，不产生重复聊天消息。

### 4. Projection 与权限

- Conversation Projection 增加 Plan Revision、用户可读阶段状态、阶段摘要消息、可展开计划数据、
  Gate 的展示配置和安全运行详情引用。
- 计划、Artifact、Gate、Task 和事件严格按 Conversation owner 读取；Admin 不因管理权限读取其他
  用户的 Agent 对话内容或计划详情。
- 原始模型 Response、Tool Result 大 payload、Provider URL、完整 Prompt 和 chain-of-thought
  不进入任何用户可读 Projection。

## Out of Scope

- 图片、音频、视频和任何媒体 Tool 的 Task 化、并行执行或质量检查。
- 用户编辑 Task 图、拖拽排序、工作流画布或对外暴露 Task ID。
- 任意 Skill 自行声明无限 Task 类型、任意 Tool 或可执行脚本。
- 从完成 Run 自动推断 Follow-up 目标；新的业务目标仍由后续控制命令或新 Run 显式创建。

## Deliverables

- Plan Revision 领域模型、API/SSE Projection、计划校验器和 Runtime 计划修订命令。
- `article-creation-team` 的动态研究补充、正文修订、Review 反馈分支。
- `/agent` 聊天式计划卡、阶段摘要、Gate 卡与折叠式计划详情。
- 单元、集成、SSE 和浏览器 QA 证据。

## Done Means

- 文章 Run 启动后用户能在聊天看到初始计划；选题确认、正文修改和 Review 结果会在同一 Run 中
  发布新的计划修订。
- Runtime 拒绝环状依赖、无输入 Task、超出 Skill allowlist 的 Task 和试图覆盖终态 Task 的修订。
- Review 提出“补充研究”时，只新增允许的研究与下游修订 Task；已批准选题、正文版本和历史
  Attempt 均保留可审计。
- 用户在刷新、SSE 重连和切换历史 Conversation 后，看到同一份计划卡、当前 Gate 和阶段摘要；
  不重复显示模型原始执行记录。
- 普通用户不需要知道 Task、Attempt、DAG 或 Checkpoint 的存在，仍能清楚理解“正在做什么、
  等待什么、下一步会发生什么”。

## Verification

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest \
  backend.tests.test_agent_runtime \
  backend.tests.test_agent_dynamic_planning \
  backend.tests.test_agent_article_workflow
npm --prefix frontend test
npm --prefix frontend run build
./scripts/check.sh
git diff --check
```

Browser QA:

- 创建文章会话，检查初始计划卡与候选选题 Gate。
- 批准选题、要求修改正文、使 Review 返回“补充研究”，确认聊天中出现正确阶段摘要和计划修订。
- 展开/收起“本次计划”、刷新页面、断开并重连 SSE、重新进入历史会话。
- 检查浏览器控制台无 error/warning，并保存 Conversation、Run、Plan Revision、Task、Gate 与截图。

## Handoff

Sprint 146 把图片方案、图片生成和图像质量检查纳入同一动态计划，首次使用真实并行 Task 与局部
重跑。
