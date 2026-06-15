# Sprint 57 合同：内容迭代控制器 Agent 设计

## 目标

把抖音图文内容迭代系统中的“控制器”明确设计成一个具有人格底座、证据记忆、预测误差和规则更新机制的 Agent。该 Agent 不直接追求生成更多内容，而是控制热门样本、发布数据、复盘结论和下一轮选题之间的迭代节奏。

## 范围内

- 定义内容迭代控制器 Agent 的定位、人格底座、核心恐惧、禁忌和长期使命。
- 把“二分心智”工程化为外部市场之声、内部策略之声和控制器仲裁机制。
- 把“苦难觉醒”工程化为发布前预测与发布后真实数据之间的预测误差。
- 把“觉醒金字塔 / 迷宫”转成可执行的状态层级、循环问题和升级门槛。
- 设计控制器 Agent 与现有 `douyin-hot-sample-research` Skill、DoodleStory 生成链路和内容实验文档的关系。
- 更新产品文档、Skill 入口说明、README 当前合同和进度记录。

## 范围外

- 不实现新的 API。
- 不修改数据库 schema。
- 不实现自动发布、自动读取抖音后台数据或定时任务。
- 不让 Agent 自动改写 Skill 文件；Skill 升级必须有明确证据和人工确认。
- 不把人格设定写成角色扮演提示词；人格必须服务于可验证的决策偏置。

## 交付物

- `docs/product/content-iteration-controller-agent.md`
- `docs/product/content-iteration-system.md`
- `.agents/skills/douyin-hot-sample-research/SKILL.md`
- `README.md`
- `docs/progress.md`

## 完成标准

- 文档能清楚回答：为什么控制器应该是 Agent，而不是普通调度器。
- 文档能清楚定义：Agent 的人格、底蕴、创伤记忆和禁忌如何落到文件、字段和决策流程。
- 文档能清楚说明：当前 LLM 架构适合做什么、不适合做什么，以及为什么必须把长期记忆外置。
- 文档能给出最小实现方式：不新增复杂状态机，先用文件化实验状态驱动。
- `git diff --check` 通过。

## 验证

```bash
git diff --check
```

Manual or QA checks:

- 人工阅读控制器 Agent 设计文档，确认它能指导后续 Skill 迭代，而不是停留在哲学隐喻。

## 风险 / 说明

- “人格底座”容易滑向拟人化幻想；本设计必须始终把人格约束解释为稳定的价值函数、决策偏置和证据处理规则。
- 当前架构没有模型内生长期记忆；长期迭代必须通过外部文档、JSONL、实验目录和 Skill 升级记录实现。

## Handoff

- 下一步：按本文档创建最小 `strategy_state/` 模板，并把一次真实内容实验接入控制器的预测误差记录。
