# Sprint 55 合同：抖音 Skill 分步执行协议

## 背景

`douyin-hot-sample-research` 已经具备新赛道预测和账号复盘两个入口，但如果一次暴露完整输入结构，用户理解成本过高。需要把 Skill 的默认执行方式改成“小步推进”：每次只执行一个可检查步骤，完成后提示用户下一步；只有用户明确说“一次执行到位”时才连续执行完整链路。

## 目标

- 为 Skill 增加默认分步执行协议。
- 明确哪些话术代表一次执行到位。
- 把 `new_lane_prediction` 和 `account_review` 分别拆成有序步骤。
- 规定每一步的输出结构，方便用户知道当前完成了什么、下一步该做什么。
- 保留已有预测链路、实验设计、后台数据接入和内容库沉淀设计。

## 非目标

- 不实现新的采集脚本。
- 不实现自动读取抖音后台数据。
- 不改 DoodleStory 业务代码或数据库。
- 不新增兜底采集策略。

## 影响范围

- `.agents/skills/douyin-hot-sample-research/SKILL.md`
- `.agents/skills/douyin-hot-sample-research/references/prediction-workflow-architecture.md`
- `docs/progress.md`

## 验收标准

- Skill 文档明确默认一次只执行一个 step。
- Skill 文档明确用户说“继续”时只执行上次建议的下一步。
- Skill 文档明确用户说“一次执行到位/跑完整流程/连续执行/直接跑完”时可以连续执行。
- 两个入口都有清晰 step 列表。
- 每一步输出字段包含 `input_used`、`artifact`、`decision`、`blocked_by`、`next_step`。

## 验证

```bash
backend/.venv/bin/python /Users/pengfei.shi/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/douyin-hot-sample-research
git diff --check
```
