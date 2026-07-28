# Sprint 134：单 Skill 驱动的多 Agent 文案工作流与审批恢复

## Status

Implemented，2026-07-29 增补模型驱动 Skill 编译与完整模型调用 Metric。

## Goal

在现有 Native Agent Runtime 上交付第一条可真实运行、可中断恢复的多 Agent 文案纵向链路。
一个发布版总 Skill 同时定义主 Agent 的执行策略、可用角色、各角色子流程、协作顺序和质量门槛；
主 Agent 使用 OpenAI Agents SDK `agent.as_tool()` 调用子 Agent。每个已完成子 Agent 的正式输出
保存为数据库 Artifact，最终文案可暂停等待用户审批，并在用户稍后返回后从已保存检查点继续，
不依赖进程内存维持长时间等待。

## Product Flow

```text
用户提出创作要求
→ Director 根据总 Skill 调用 Writer 子 Agent
→ Writer 输出文案草稿 Artifact
→ Director 调用 Reviewer 子 Agent
→ Reviewer 输出审稿 Artifact
→ Director 形成最终文案 Artifact
→ Run 进入 waiting_for_input，等待用户审批
→ 用户批准：文案标记 approved，本次纯文本 Run 完成
→ 用户要求修改：保存反馈，重新调用 Writer / Reviewer，产生新版本后再次等待审批
```

## In Scope

- 新增一个发布版总 Skill，单文件包含：
  - Director 的总体执行策略；
  - Writer、Reviewer 的职责；
  - 每个角色内部的固定子流程；
  - 角色调用顺序、允许分支、完成条件和最大修改轮次。
- 每个 Run 首次执行时使用一次 Workflow Compiler 模型调用理解完整总 Skill，输出结构化的
  Director / Writer / Reviewer 局部 instructions、执行步骤、分支条件和质量门槛；Runtime
  只校验固定角色与 Tool 能力边界，不按 Markdown 标题程序化拆解 Skill。
- 编译计划连同 Skill content hash 保存到根 Run Checkpoint；中断恢复复用同一计划，不重复
  编译，也不允许同一 Run 静默替换为不同计划。
- Director 与子 Agent 分别只注入编译计划中属于自己的局部 instructions；当前任务目标和
  Artifact 引用作为子 Agent 输入，完整 Skill 只进入 Workflow Compiler。
- 使用 OpenAI Agents SDK `agent.as_tool()` 完成 manager-style 调用：
  - 主 Agent 保持流程控制权；
  - 子 Agent 只接收当前子任务所需输入；
  - 子 Agent 最终输出作为 Tool Output 返回主 Agent；
  - 不使用 handoff 转移用户会话所有权。
- 为 Native Agent 增加通用 Artifact 持久化，至少支持：
  - `article_draft`
  - `article_review`
  - `final_article`
- Artifact 使用固定外壳与灵活 JSON 内容：
  - `artifact_type`
  - `schema_version`
  - `version`
  - `status`
  - `producer_role`
  - `content_json`
  - `content_hash`
  - 创建时间
- 保存根 Run 的最小恢复检查点，记录当前阶段、已完成 Artifact 引用、待处理审批和修改轮次。
- 最终文案生成后创建待审批记录并将 Run 置为 `waiting_for_input`；等待期间不保持模型请求、
  Worker 协程或进程内对象。
- 用户稍后批准或要求修改时，重新入队同一个根 Run，并从数据库中的 Skill Version、
  SDK Session、Checkpoint、Artifact 和审批结果继续。
- 恢复时复用已经完成且 hash 有效的 Artifact，不重复执行对应子 Agent；中断时尚未产生正式
  Artifact 的纯文本子任务可以在有界次数内重新执行。
- 批准后的最终文案直接结束本次 Run；本 Sprint 不进入图片、语音、字幕或视频制作。
- 前端在现有 Agent 会话中展示：
  - 当前公开阶段和角色；
  - 已完成的文案与审稿结果；
  - 最终文案审批卡；
  - 批准、要求修改和恢复后的新版本；
  - 明确失败信息。
- 父流程、子 Agent 调用、Artifact、审批和恢复进入现有 Event 与 MLflow
  Trace，且不展示隐藏推理。
- SDK LLM 生命周期为 Compiler、Director、Writer、Reviewer 的每个真实请求写入
  `model.request.started/completed`；Run 总调用数、每次 execution attempt 和角色拆分进入
  数据库事件与 MLflow 根 Trace。

## Out of Scope

- 不接入本地 Markdown 创作知识库、全文检索、Embedding 或向量数据库。
- 不生成图片、语音、字幕或视频，也不调用媒体制作与发布 Tool。
- 不拆分多个 Skill 层级，不建设 Skill 组合 DSL、Agent Builder、工作流画布或角色管理后台。
- 不允许模型创建总 Skill 未声明的角色，也不支持子 Agent 继续创建孙 Agent。
- 不使用 handoff，不把用户会话控制权交给 Writer、Reviewer 或内容制作角色。
- 不引入 LangGraph、LangChain、Temporal、Celery、Redis 或外部工作流/消息队列。
- 不保存或展示模型隐藏推理；不把完整子 Agent 会话当作长期业务 Artifact。
- 不在本 Sprint 优化选题方法、钩子知识、文案 Rubric 或媒体生成质量。
- 不引入兼容性回退、Mock 成功结果、占位 Artifact 或静默忽略子 Agent 失败。

## Recovery Rules

- 数据库是 Run、Artifact、审批和恢复阶段的事实来源；内存队列只传稳定 Run ID。
- 子 Agent 成功但父 Agent 尚未继续时，恢复后直接读取已经保存的 Artifact。
- 子 Agent 在纯文本生成过程中中断且没有正式 Artifact 时，记录失败 attempt，并在预算内重新执行。
- 已进入现有外部媒体 Tool 的调用继续遵守当前 `prepared/running/succeeded/unknown` 语义；
  无法确认副作用结果时不得自动重放。
- `waiting_for_input` Run 在服务重启时保持等待，不自动继续；只有真实用户审批或修改请求才能
  重新入队。
- 修改文案必须创建新 Artifact 版本，不覆盖已经审批或历史成功版本。

## Deliverables

- Native Agent 主/子 Agent 构建与 `agent.as_tool()` 调用实现。
- 单文件总 Skill、模型驱动 Workflow Compiler、编译计划持久化与局部角色 instructions 注入。
- Artifact、Checkpoint 与文案 Approval 数据模型和迁移。
- 子 Agent 输出保存、父 Agent Tool Output 回传与恢复逻辑。
- 文案审批 API、现有会话 UI 和持久化事件展示。
- 自动化测试、真实模型纵向 smoke 记录和项目文档更新。

## Done Means

- 用户提交一个创作要求后，Director 真实调用 Writer 和 Reviewer 子 Agent，并得到数据库中可查看
  的草稿与审稿 Artifact。
- 子 Agent 的角色方法来自模型编译后的总 Skill；用户输入中不伪装角色规则或复制整份 Skill，
  Writer/Reviewer instructions 不包含其他角色完整规则。
- 最终文案出现审批卡，在用户未操作期间 Run 稳定保持 `waiting_for_input`，服务和浏览器均可关闭。
- 服务重启后，已完成的 Writer/Reviewer Artifact 不会重复生成；用户回来批准后同一根 Run
  从审批点继续。
- 用户要求修改时保存反馈并生成新版本，旧版本保持可追踪。
- 批准后同一个根 Run 以纯文本结果完成，媒体调用计数全部保持为零。
- 子 Agent 失败、输出不符合约定或恢复条件不足时明确失败，不生成占位结果。
- 前端、数据库 Event 和 MLflow 能通过同一个根 Run 定位完整执行过程。
- 页面模型调用数等于 Compiler、Director 与全部子 Agent 的真实请求总和；MLflow 中每个
  execution attempt 可独立辨认，并能看到角色调用拆分。

## Verification

```bash
./scripts/check.sh
git diff --check
```

自动化场景：

- Director 调用 Writer，子 Agent final output 被保存为 `article_draft` 并作为 Tool Output 返回。
- Workflow Compiler 输出固定结构计划并按 Skill hash 持久化，恢复时复用。
- Writer 与 Reviewer instructions 互不包含对方或 Director 的完整规则。
- SDK start/end 回调跨异步任务执行时仍能正确关联 Metric；并发子调用不会丢失计数。
- Reviewer 消费草稿并保存 `article_review`，Director 据此生成 `final_article`。
- 最终文案进入 `waiting_for_input` 后不占用活动 Worker。
- 模拟服务重启后，等待审批状态、Artifact 版本和 SDK Session 均可恢复。
- 用户批准后继续内容制作；用户要求修改后产生新文案版本并再次等待审批。
- 已完成子任务在父 Run 恢复时不会重复执行。
- 中断且没有 Artifact 的纯文本子任务只在有界预算内重试。
- 已有外部 Tool 处于不确定状态时保持 `unknown`，不会被多 Agent 恢复逻辑重复调用。
- Owner 隔离、取消、SSE 游标补发和现有单 Agent 内容制作回归通过。

真实 smoke：

- 使用一个真实用户、一个发布版总 Skill 和真实模型完成
  `Writer → Reviewer → 文案审批`。
- 在最终文案等待审批时重启后端，确认用户返回后可以批准并继续。
- 保存 Run ID、Artifact ID、Approval ID、Trace ID 和最终文案作为验收证据。

2026-07-29 增补真实 smoke：

- 页面 Conversation `b0515a8119f34a4b919e2a7750f1693b` 的 Run
  `a714a716fecc41a7898fe24277fefa3a` 完成
  `Workflow Compiler → Director → Writer → Director → Reviewer → Director → Director`，
  进入 `waiting_for_article_approval`。
- 数据库与页面均显示真实模型调用 7 次，角色拆分为 Compiler 1、Director 4、Writer 1、
  Reviewer 1；started/completed 事件各 7 条，图片、语音、字幕、视频调用均为 0。
- MLflow 只有 1 个根 Trace，`execution_attempt=1`，根 Span 的总数、完成数与角色拆分和数据库
  一致；完整 Skill 只用于 Compiler 输入，Writer 和 Reviewer 分别只含自己的局部 role。

## Risks / Notes

- `agent.as_tool()` 提供模型层的主子 Agent 调用，但长期等待和恢复由 DoodleStory 数据库状态负责，
  不能依赖嵌套调用一直驻留内存。
- 总 Skill 会同时包含总体策略和多个角色流程，第一版保持单文件；Workflow Compiler 负责在
  Run 开始时理解并局部化，不要求作者维护多层 Skill 或程序化 DSL。
- 本 Sprint 将 Human in the Loop 设在最终文案边界，避免在子 Agent 内部暂停导致嵌套恢复语义
  过度复杂。

## Handoff

- 下一步优先根据真实文案运行记录接入本地 Markdown 创作知识检索，而不是继续扩展 Agent 层级。
- 后续 Sprint 再决定是否把已批准文案显式交给独立媒体制作 Run；本 Sprint 在文本审批完成处断开。
