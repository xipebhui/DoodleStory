# 画一个故事发布前审核：叙事人格注入

- experiment_id: `2026-06-16-huayigegushi-cycle-01`
- reviewed_at: `2026-06-16`
- trigger: `content-iteration-controller Skill 新增 narrative_persona_profile 必填`
- review_type: `persona_injection`

## 决策

本轮不重跑市场扫描、样本评分、探测采集或 full_story_extract。这些是事实证据，不受叙事人格规则影响。

需要重做的是发布前预测和生成 brief 层：

- `prediction.json` 补齐 `narrative_persona_profile`。
- H2 两条 `generation_brief` 按 `intimacy_trial` / 亲密关系审判型重生。
- H1 继续暂停，不在本轮注入人格后生成。

## H2 叙事人格

- profile_id: `intimacy_trial`
- label: `亲密关系审判型`
- crowd_desire: 他到底会不会为了我站出来；我想看到小事背后真正的态度。
- moral_position: 站在被忽视的一方，但不把复杂家庭关系写成无差别仇恨。
- emotion_curve: 压抑 -> 怀疑 -> 失望 -> 审判 -> 释放。
- taboo_boundary: 不鼓励现实操控、跟踪、报复或危险测试；不煽动性别对立；不使用真实家庭投稿的可识别细节。
- comment_trigger: 他到底有没有把你当小家的人；男人的态度决定边界；我以为他又不管了。
- account_packaging: 账号昵称、头像和简介服务该叙事人格；必要时调整账号包装，不用当前账号名反推拟人角色。

## 影响范围

- `P3-H2-walking-story`：继续作为第一波 H2 任务候选，brief 已注入亲密关系审判型。
- `P4-H2-duck-bear`：继续作为第一波 H2 任务候选，brief 已注入亲密关系审判型，且不再使用账号名导出的拟人角色。
- `P1-H1-walking-story` / `P2-H1-duck-bear`：继续暂停。若重启，应重新定义为安全化成年身份错位机制，并在 `cold_observer` 或 `absurd_fate` 中选择叙事人格。

## 下一步

只为 H2 两条 persona-injected brief 创建 DoodleStory `故事方案` 模式任务，并回填 `task_id`。
