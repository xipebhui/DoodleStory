# 画一个故事关键词图文赛道实验

- experiment_id: `2026-06-16-huayigegushi-cycle-01`
- status: `experiment_planned`
- created_at: `2026-06-16T11:20:39`

## 实验目标

验证 `画一个故事` 这个关键词背后的图文内容机制，是否能转成 DoodleStory 可持续生成和发布的选题方向。

当前市场扫描、评分、深挖样本选择、评论/账号/VL 探测和 topic_hypothesis 均已完成。第一轮实验不再泛测整个关键词，只验证 `family_marriage` 下两个机制：

- `H1-family-rule-loop`：异常家庭规则怪谈。
- `H2-marriage-boundary-three-rounds`：三回合家庭边界测试。

## 市场证据

已形成以下证据链：

- `content-lab/market_scans/2026-06-16-huayigegushi-market-scan.md`
- `content-lab/market_scans/2026-06-16-huayigegushi-market-scoring.md`
- `content-lab/market_scans/2026-06-16-huayigegushi-deep-probe-selection.md`
- `content-lab/market_scans/2026-06-16-huayigegushi-probe-collection.md`
- `content-lab/market_scans/2026-06-16-huayigegushi-topic-hypothesis.md`
- `content-lab/market_scans/2026-06-16-huayigegushi-experiment-plan.md`

## 本轮固定变量

- 账号：`行走的故事`、`小黄鸭与大熊`。
- 类目：`family_marriage`。
- 关键词标签：`画一个故事`。
- 视觉风格：统一使用一个 DoodleStory 手绘图文故事风格；生成前绑定具体 style，绑定后 H1/H2 不再更换。
- 发布时间窗口：晚间 `20:30-21:30`，Asia/Shanghai。
- 内容长度：每条 10 页。
- 复盘检查点：`2h`、`24h`、`72h`。

## 本轮只改变的主要变量

主要变量：故事机制。

- H1：现实家庭关系被设计成可被评论区规则化解释的异常循环。
- H2：三次具体生活冲突之后，用行动兑现家庭边界。

账号是观测维度，不是本轮主动优化变量。两个账号都发 H1 和 H2。

## 发布计划摘要

发布计划已形成，但仍不可直接发布。当前最小实验量为 4 条：

- `P1-H1-walking-story`：H1，账号 `行走的故事`。
- `P2-H1-duck-bear`：H1，账号 `小黄鸭与大熊`。
- `P3-H2-walking-story`：H2，账号 `行走的故事`。
- `P4-H2-duck-bear`：H2，账号 `小黄鸭与大熊`。

发布前还必须完成：

1. 选择先进入 `full_story_extract` 的源样本。
2. 完成 `full_story_extract`，获得完整原文结构。
3. 完成 `generation_brief`，形成 DoodleStory 原创故事方案。
4. 创建真实生成任务并回填 `content_id` 或 `task_id`。
5. 回填绝对 `planned_publish_time`。

## 复盘入口

发布后把真实数据放入 `post_results/`，再更新 `deviation_review.md` 和 `strategy_update.json`。

当前已有发布前预测和实验计划，但没有发布结果前，不能做复盘结论或规则升级。
