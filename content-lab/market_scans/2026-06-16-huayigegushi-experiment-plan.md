# 画一个故事 experiment_plan

- experiment_id: `2026-06-16-huayigegushi-cycle-01`
- keyword: `画一个故事`
- created_at: `2026-06-16`
- workflow_step: `h2_p4_render_storyboard_ready_p3_legacy_task_created_h1_paused`
- evidence_source: `content-lab/market_scans/2026-06-16-huayigegushi-topic-hypothesis.md`

## 用户输入

本轮可用账号只有两个：

1. `行走的故事`
2. `小黄鸭与大熊`

控制器采用两账号交叉验证，但发布前审核后改为第一波只用两个账号验证 H2。账号昵称、头像、简介都可调整，不能用当前账号包装反推内容形态。

## 实验目标

验证 `画一个故事` 第一波是否应该主攻 `family_marriage` 中的 H2 机制，并使用 `intimacy_trial` / 亲密关系审判型叙事人格。当前执行流程已调整为 `generation_brief -> render_storyboard_design -> generation_task_submission`，brief 只负责故事策划，真实提交任务前必须先生成可画分镜：

- `H1-family-rule-loop`：暂停。当前提炼偏离源样本诱因，需二次验证。
- `H2-marriage-boundary-three-rounds`：三回合家庭边界测试。

本轮不验证纯爱治愈，不验证社会安全题材，不同时测试多种画风、页数、发布时间或标题结构。

## 固定变量

| variable | value |
| --- | --- |
| account_group | `行走的故事`、`小黄鸭与大熊` |
| category | `family_marriage` |
| keyword_tag | `画一个故事` |
| visual_style | 统一使用一个 DoodleStory 手绘图文故事风格；生成前绑定具体 style，绑定后 H1/H2 不再更换 |
| story_length | 每条 10 页 |
| narrative_persona | H2 第一波使用 `intimacy_trial` / 亲密关系审判型 |
| publish_frequency | 第一波只发 H2 两条；H1 暂停后不强行凑满 `2-3` 条 |
| publish_window | H2 第一波基础窗口：`12:10-13:10`、`20:30-21:30`，Asia/Shanghai；H1 重启前不排期 |
| review_checkpoints | `2h`、`24h`、`72h` |
| CTA | 不做强引导关注或私信，只保留自然评论触发 |
| source_handling | 不复刻源故事细节；只复用机制，生成前需走原创改写 |

## 改变变量

唯一主要改变变量：故事机制。发布前审核后，第一波只验证 H2 的结构修正版。

- H1：暂停。源样本更像“伦理身份错位幻想”，当前规则循环 brief 不代表有效机制。
- H2：三次具体生活冲突连续压抑，最后一次性用行动兑现家庭边界；叙事人格为亲密关系审判型，让读者等待“他到底会不会站出来”。

账号是观测维度，不是本轮主动优化变量。内容机制和叙事人格优先于账号昵称、头像和简介；必要时账号包装服务内容。

## 内容槽

| slot_id | hypothesis_id | account | planned_publish_window | page_count | controlled_variation | current_status |
| --- | --- | --- | --- | ---: | --- | --- |
| `P1-H1-walking-story` | `H1-family-rule-loop` | 行走的故事 | 暂不排期 | 10 | H1 暂停，需重定义为安全化成年身份错位机制 | paused_needs_mechanism_revalidation |
| `P3-H2-walking-story` | `H2-marriage-boundary-three-rounds` | 行走的故事 | 生成完成后第 1 天 `12:10-13:10` | 10 | 亲密关系审判型；压抑三连 + 延迟行动兑现，真实县城婚姻故事 | task_created_legacy_flow |
| `P2-H1-duck-bear` | `H1-family-rule-loop` | 小黄鸭与大熊 | 暂不排期 | 10 | H1 暂停；账号名不再决定拟人化内容形态 | paused_needs_mechanism_revalidation |
| `P4-H2-duck-bear` | `H2-marriage-boundary-three-rounds` | 小黄鸭与大熊 | 生成完成后第 1 天 `20:30-21:30` | 10 | 亲密关系审判型；同机制第二账号版本，内容人格优先于账号昵称 | ready_for_task_submission |

说明：第一波只发布 H2。两个账号不发布完全相同素材，保留同一“压抑累积 + 延迟兑现”结构，但故事表层、角色和具体冲突要原创变化，降低重复内容风险。

## 发布频率护栏

- 基础节奏：第一波总账号池当天 2 条，只发布 H2 两个账号版本。
- 加速节奏：H1 暂停期间不启用第 3 条加速窗口，不为了频率发布机制不确定内容。
- 单账号同日最多 2 条；同账号两条之间至少间隔 3 小时。
- 同一假设的两个账号版本不要连续挨着发，避免互相干扰判断。
- 24h 数据复盘时必须按实际发布时间计算窗口，不能按自然日粗略统计。

## 账号适配假设

| account | 初始判断 | 需要验证 |
| --- | --- | --- |
| 行走的故事 | 当前账号包装可调整，不作为内容形态约束。 | H2 的真实家庭关系叙事是否能触发真实经历评论，而不是只获得低互动浏览。 |
| 小黄鸭与大熊 | 当前账号包装可调整，不再反推为拟人化角色内容。 | 同一 H2 机制换表层故事后，是否仍能在第二账号触发代入、评论和转发。 |

账号名、头像、简介只是包装层，不作为机制判断依据。结论必须来自发布后数据。

## 指标记录表

每条发布后至少记录：

| field | required |
| --- | --- |
| account | yes |
| slot_id | yes |
| hypothesis_id | yes |
| post_url_or_id | yes |
| publish_time | yes |
| checkpoint | `2h` / `24h` / `72h` |
| views | yes |
| likes | yes |
| comments | yes |
| collects | yes |
| shares | yes |
| followers_delta | optional |
| top_comments | optional but recommended |
| risk_or_limit_note | optional but recommended |

## 成功判断

### H1 最低继续线

H1 第一波暂停，不记录发布指标。重启前需重新定义为安全化成年身份错位机制，并补同类证据。

### H1 爆点信号

H1 第一波暂停，不判断爆点信号。

### H2 最低继续线

- 2h：出现至少 2 条“我老公/我婆婆/我家”代入评论；点赞 >= 20；收藏 >= 3。
- 24h：点赞 >= 100；评论 >= 8；转发 >= 20；收藏 >= 10。
- 72h：点赞 >= 250；评论 >= 20；转发 >= 60；收藏 >= 25。

### H2 爆点信号

- 评论区出现真实经历长评。
- 24h 收藏 >= 30。
- 72h 转发 >= 点赞的 0.3 倍。
- 完读相关表现强于逐回合解决版预期：评论出现“我以为他又不管了”“憋到最后才爽”等压抑释放反馈。

## 诊断规则

- 两个账号的 H2 都低于最低继续线：优先判断 H2 机制或执行失败。
- 一个账号过线、一个账号不过线：先检查内容执行和发布时间，再谨慎判断账号适配差异。
- H1 不参与第一波诊断。
- H2 收藏强但评论弱：实用判断成立，但情绪讨论弱，需要强化冲突和行动兑现。
- 任何一条出现平台风险、限流或明显争议：先暂停同类发布，不进入规则升级。

## 已完成 full_story_extract

- H1 源样本 `7649315939447871470`：已完成 8 页完整图集 VL 提取，证据文件为 `content-lab/full_story_extracts/2026-06-16-huayigegushi-h1-7649315939447871470.md` 和 `.json`。后续只提炼“家庭身份规则循环”机制，不能沿用年轻后妈、后后妈、未成年人或暧昧继亲关系等高风险桥段。
- H2 源样本 `7650413089900236066`：已完成 15 页完整图集 VL 提取，证据文件为 `content-lab/full_story_extracts/2026-06-16-huayigegushi-h2-7650413089900236066.md` 和 `.json`。

## 已完成 generation_brief

- `P1-H1-walking-story`：`content-lab/generation_briefs/2026-06-16-huayigegushi-p1-h1-walking-story.md`，已暂停。
- `P2-H1-duck-bear`：`content-lab/generation_briefs/2026-06-16-huayigegushi-p2-h1-duck-bear.md`，已暂停。
- `P3-H2-walking-story`：`content-lab/generation_briefs/2026-06-16-huayigegushi-p3-h2-walking-story.md`，已注入 `intimacy_trial` / 亲密关系审判型。
- `P4-H2-duck-bear`：`content-lab/generation_briefs/2026-06-16-huayigegushi-p4-h2-duck-bear.md`，已按新流程重新生成 story-only brief，只保留故事机制、旁白主线、情绪功能和禁用项，不再直接作为 DoodleStory 任务输入。

## 已完成 render_storyboard_design

- `P4-H2-duck-bear`：`content-lab/render_storyboards/2026-06-18-huayigegushi-p4-h2-duck-bear.md`，已按“旁白讲故事，画面给证据”生成 10 页可画分镜，可进入 `generation_task_submission`。
- `P3-H2-walking-story`：已在旧流程下创建任务 `3784275df2914e80905347b1f4bc4381`。如需完全重跑新流程，必须显式确认重提，再补 `render_storyboard`，不能默认覆盖旧任务。

## 发布前审核

- 审核记录：`content-lab/prepublish_reviews/2026-06-16-huayigegushi-generation-brief-review.md`
- 人格注入记录：`content-lab/prepublish_reviews/2026-06-16-huayigegushi-persona-injection.md`
- 决策：H1 暂停；H2 注入亲密关系审判型后进入第一波任务创建；内容机制和叙事人格优先于账号包装。

## 当前阻塞

本计划仍不能直接发布。进入发布前还需要：

1. 用 P4 的 `render_storyboard.artifact` 创建真实生成任务并得到 `task_id`。
2. 根据实际完成时间回填 H2 两条绝对 `planned_publish_time`。
3. H1 补充同类样本或重写机制后再决定是否重启。

## 下一步

进入 `generation_task_submission`：

- 先用 `P4-H2-duck-bear` 的 render storyboard 创建 DoodleStory 提取分镜模式任务，并回填 `task_id`。
- P3 旧流程任务暂时保留；除非显式 force-resubmit，否则不重复创建。
- 素材完成后根据实际完成时间回填绝对发布时间。
