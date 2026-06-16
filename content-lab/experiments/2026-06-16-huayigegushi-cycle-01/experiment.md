# 画一个故事关键词图文赛道实验

- experiment_id: `2026-06-16-huayigegushi-cycle-01`
- status: `full_story_extracted`
- created_at: `2026-06-16T11:20:39`

## 实验目标

验证 `画一个故事` 这个关键词背后的图文内容机制，是否能转成 DoodleStory 可持续生成和发布的选题方向。

当前市场扫描、评分、深挖样本选择、评论/账号/VL 探测、topic_hypothesis、experiment_plan 和 H1/H2 源样本 `full_story_extract` 均已完成。第一轮实验不再泛测整个关键词，只验证 `family_marriage` 下两个机制：

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
- `content-lab/full_story_extracts/2026-06-16-huayigegushi-h1-7649315939447871470.md`
- `content-lab/full_story_extracts/2026-06-16-huayigegushi-h2-7650413089900236066.md`

## 本轮固定变量

- 账号：`行走的故事`、`小黄鸭与大熊`。
- 类目：`family_marriage`。
- 关键词标签：`画一个故事`。
- 视觉风格：统一使用一个 DoodleStory 手绘图文故事风格；生成前绑定具体 style，绑定后 H1/H2 不再更换。
- 发布频率：总账号池每天 `2-3` 条。
- 发布时间窗口：基础窗口 `12:10-13:10`、`20:30-21:30`；加速窗口 `22:00-22:40`，Asia/Shanghai。
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

H1 源样本 `7649315939447871470` 已完成 8 页完整图集 VL 提取，H2 源样本 `7650413089900236066` 已完成 15 页完整图集 VL 提取，均可进入 `generation_brief`。这些证据只能用于分析结构和原创改写，不能直接照搬源故事桥段、人物关系或具体生活细节。H1 后续只能提炼“家庭身份规则循环”机制，不能沿用年轻后妈、后后妈、未成年人或暧昧继亲关系等高风险桥段。

发布前还必须完成：

1. 完成 H1/H2 `generation_brief`，形成 DoodleStory 原创故事方案。
2. 创建真实生成任务并回填 `content_id` 或 `task_id`。
3. 回填绝对 `planned_publish_time`。
4. 根据素材完成和审核情况确认是否启用第 3 条加速窗口。

## 复盘入口

发布后把真实数据放入 `post_results/`，再更新 `deviation_review.md` 和 `strategy_update.json`。

当前已有发布前预测和实验计划，但没有发布结果前，不能做复盘结论或规则升级。
