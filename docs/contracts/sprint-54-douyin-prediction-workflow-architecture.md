# Sprint 54 合同：抖音预测型内容链路架构

## 目标

把抖音热门样本 Skill 从“复杂研究输入”收敛为两个用户能理解的入口：新赛道关键词预测、账号复盘诊断。设计实验数量、后台数据接入位置、内容库沉淀方式，以及后续如何基于验证内容库和热点创造新内容。

## 范围内

- 明确 Skill 的两个入口和最小用户输入。
- 设计发布实验的最小结构，包括同一内容至少 2 个账号发布以隔离账号因素。
- 设计后台详细数据的接入位置和手工/自动接入兼容结构。
- 设计内容库目录结构，用于沉淀已验证内容、失败内容、可复用机制和热点结合记录。
- 明确现有 `DY爆款复刻` 的定位：作为单条样本拆解/执行器，不作为预测型策略入口。
- 更新 Skill 主流程和进度文档。

## 范围外

- 不开发新 API。
- 不修改数据库 schema。
- 不修改 `DY爆款复刻` 现有行为。
- 不实现自动读取抖音后台数据。
- 不实现热点抓取或自动发布。

## 交付物

- `.agents/skills/douyin-hot-sample-research/references/prediction-workflow-architecture.md`
- `.agents/skills/douyin-hot-sample-research/SKILL.md`
- `docs/progress.md`

## 完成标准

- 后续 agent 能区分“新赛道关键词预测”和“账号复盘诊断”两种入口。
- 后续 agent 知道后台数据应该进入实验结果层，而不是市场扫描层或素材层。
- 后续 agent 知道内容库不是资源包，而是经过验证的机制库、预测库和复盘库。
- 设计中明确如何进入迭代：预测、发布、回收、偏差诊断、策略更新。

## 验证

```bash
backend/.venv/bin/python /Users/pengfei.shi/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/douyin-hot-sample-research
git diff --check
```

Manual or QA checks:

- 人工阅读架构文档，确认输入复杂度已经降到两个自然入口。

## 风险 / 说明

- 这是架构设计 sprint，不声称后台数据接入、账号诊断或内容库检索已经自动化。
- 账号复盘需要用户提供后台数据或后续接入平台数据；没有真实发布数据时只能做市场预测，不能做账号适配诊断。

## Handoff

- 下一步：把 `topic_hypothesis` 和 `post_result` 的 JSON schema 固化为脚本输出，再实现一个最小 `topic_package_generator`。
