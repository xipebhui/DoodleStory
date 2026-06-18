# 画一个故事关键词图文赛道实验

- experiment_id: `2026-06-16-huayigegushi-cycle-01`
- status: `h2_p4_render_storyboard_ready_p3_legacy_task_created_h1_paused`
- created_at: `2026-06-16T11:20:39`

## 实验目标

验证 `画一个故事` 这个关键词背后的图文内容机制，是否能转成 DoodleStory 可持续生成和发布的选题方向。

当前市场扫描、评分、深挖样本选择、评论/账号/VL 探测、topic_hypothesis、experiment_plan、H1/H2 源样本 `full_story_extract` 和 4 个发布槽的 `generation_brief` 均已完成；发布前审核后，H1 暂停第一波发布，H2 brief 已按新版 Skill 注入 `intimacy_trial` / 亲密关系审判型。控制器流程已改为 `generation_brief -> render_storyboard_design -> generation_task_submission`，因此未提交的 P4 已重新生成 story-only brief，并产出可提交的 render storyboard。第一波不再同时验证 H1/H2，只先验证 H2：

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
- `content-lab/generation_briefs/2026-06-16-huayigegushi-p1-h1-walking-story.md`
- `content-lab/generation_briefs/2026-06-16-huayigegushi-p2-h1-duck-bear.md`
- `content-lab/generation_briefs/2026-06-16-huayigegushi-p3-h2-walking-story.md`
- `content-lab/generation_briefs/2026-06-16-huayigegushi-p4-h2-duck-bear.md`
- `content-lab/render_storyboards/2026-06-18-huayigegushi-p4-h2-duck-bear.md`
- `content-lab/prepublish_reviews/2026-06-16-huayigegushi-generation-brief-review.md`
- `content-lab/prepublish_reviews/2026-06-16-huayigegushi-persona-injection.md`

## 本轮固定变量

- 账号：`行走的故事`、`小黄鸭与大熊`。
- 类目：`family_marriage`。
- 关键词标签：`画一个故事`。
- 视觉风格：统一使用一个 DoodleStory 手绘图文故事风格；生成前绑定具体 style，绑定后 H1/H2 不再更换。
- 发布频率：第一波只发 H2 两条；H1 暂停后不强行凑满 `2-3` 条。
- 发布时间窗口：H2 第一波基础窗口 `12:10-13:10`、`20:30-21:30`，Asia/Shanghai；H1 重启前不排期。
- 内容长度：每条 10 页。
- 叙事人格：H2 第一波使用 `intimacy_trial` / 亲密关系审判型。
- 复盘检查点：`2h`、`24h`、`72h`。

## 本轮只改变的主要变量

主要变量：故事机制。发布前审核后，第一波只验证 H2 的结构修正版。

- H1：暂停。原始爆点更接近安全化后的伦理身份错位幻想，当前“规则循环”brief 不能代表有效机制。
- H2：三次具体生活冲突连续压抑，最后一次性用行动兑现家庭边界；叙事人格是亲密关系审判型，读者等待“他到底会不会站出来”。

账号是观测维度，不是本轮主动优化变量。账号昵称、头像、简介都可调整，内容机制和叙事人格优先于当前账号包装。

## 发布计划摘要

发布计划已调整，但仍不可直接发布。第一波最小实验量为 2 条：

- `P3-H2-walking-story`：H2，账号 `行走的故事`，已在旧流程下创建任务 `3784275df2914e80905347b1f4bc4381`，不在本轮自动重提。
- `P4-H2-duck-bear`：H2，账号 `小黄鸭与大熊`，已完成 story-only brief 与 render storyboard，可进入 `generation_task_submission`。

H1 源样本 `7649315939447871470` 已完成 8 页完整图集 VL 提取，但发布前审核认为当前 H1 brief 删除了核心诱因，不能进入第一波任务创建。H2 源样本 `7650413089900236066` 已完成 15 页完整图集 VL 提取，H2 两条 brief 已修订为“亲密关系审判型 + 压抑三连 + 延迟行动兑现”，可进入任务创建。

发布前还必须完成：

1. 用 P4 的 `render_storyboard.artifact` 创建真实生成任务并回填 `task_id`。
2. 若要让 P3 也完全符合新流程，需要显式确认重提后再补 `render_storyboard`，不能默认覆盖旧任务。
3. 回填 H2 两条绝对 `planned_publish_time`。
4. H1 补充同类样本或重写为安全化成年身份错位机制后，再决定是否重启。

## 复盘入口

发布后把真实数据放入 `post_results/`，再更新 `deviation_review.md` 和 `strategy_update.json`。

当前已有发布前预测和实验计划，但没有发布结果前，不能做复盘结论或规则升级。
