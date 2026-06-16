# 画一个故事 experiment_plan

- experiment_id: `2026-06-16-huayigegushi-cycle-01`
- keyword: `画一个故事`
- created_at: `2026-06-16`
- workflow_step: `full_story_extracted`
- evidence_source: `content-lab/market_scans/2026-06-16-huayigegushi-topic-hypothesis.md`

## 用户输入

本轮可用账号只有两个：

1. `行走的故事`
2. `小黄鸭与大熊`

控制器采用两账号交叉验证，而不是一个账号只测一个假设。这样可以初步拆开“内容机制问题”和“账号适配问题”。

## 实验目标

验证 `画一个故事` 第一轮是否应该主攻 `family_marriage` 中的两个机制：

- `H1-family-rule-loop`：异常家庭规则怪谈。
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
| publish_frequency | 总账号池每天 `2-3` 条 |
| publish_window | 基础窗口：`12:10-13:10`、`20:30-21:30`；加速窗口：`22:00-22:40`，Asia/Shanghai |
| review_checkpoints | `2h`、`24h`、`72h` |
| CTA | 不做强引导关注或私信，只保留自然评论触发 |
| source_handling | 不复刻源故事细节；只复用机制，生成前需走原创改写 |

## 改变变量

唯一主要改变变量：故事机制。

- H1：现实家庭关系被设计成可被评论区规则化解释的异常循环。
- H2：三次具体生活冲突之后，用行动兑现家庭边界。

账号是观测维度，不是本轮主动优化变量。两个账号都发 H1 和 H2。

## 内容槽

| slot_id | hypothesis_id | account | planned_publish_window | page_count | controlled_variation | current_status |
| --- | --- | --- | --- | ---: | --- | --- |
| `P1-H1-walking-story` | `H1-family-rule-loop` | 行走的故事 | 生成完成后第 1 天 `12:10-13:10` | 10 | 异常家庭规则怪谈，偏真人故事叙述口吻 | needs_generation_brief |
| `P3-H2-walking-story` | `H2-marriage-boundary-three-rounds` | 行走的故事 | 生成完成后第 1 天 `20:30-21:30` | 10 | 三回合家庭边界，偏现实婚姻故事口吻 | needs_generation_brief |
| `P2-H1-duck-bear` | `H1-family-rule-loop` | 小黄鸭与大熊 | 生成完成后第 2 天 `12:10-13:10`；加速时可提前到第 1 天 `22:00-22:40` | 10 | 同机制，表层故事和角色重新原创，避免重复发布同一素材 | needs_generation_brief |
| `P4-H2-duck-bear` | `H2-marriage-boundary-three-rounds` | 小黄鸭与大熊 | 生成完成后第 2 天 `20:30-21:30` | 10 | 同机制，表层故事和角色重新原创，避免重复发布同一素材 | needs_generation_brief |

说明：不建议两个账号发布完全相同的图文素材。每个假设保留同一 hook/payoff/comment_trigger，但故事表层、角色和具体冲突要原创变化，降低重复内容风险。

## 发布频率护栏

- 基础节奏：总账号池每天 2 条，2 天完成 4 条最小实验。
- 加速节奏：总账号池每天最多 3 条；仅在当天素材已完成审核、没有明显平台风险时使用。
- 单账号同日最多 2 条；同账号两条之间至少间隔 3 小时。
- 同一假设的两个账号版本不要连续挨着发，避免互相干扰判断。
- 24h 数据复盘时必须按实际发布时间计算窗口，不能按自然日粗略统计。

## 账号适配假设

| account | 初始判断 | 需要验证 |
| --- | --- | --- |
| 行走的故事 | 账号名更像真人故事、情感故事容器，可能更适合 H2，也能承接 H1 的现实家庭叙述。 | 是否能触发真实经历评论，而不是只获得低互动浏览。 |
| 小黄鸭与大熊 | 账号名更像角色化、拟人化或轻漫画容器，可能更适合 H1 的荒诞规则，也可测试 H2 是否能被角色故事承接。 | 角色感是否削弱家庭婚姻现实代入，或反而降低尖锐题材风险。 |

以上只是账号名推断，不作为结论。结论必须来自发布后数据。

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

- 2h：出现至少 3 条非作者引导的规则化评论；点赞 >= 20；转发 >= 3。
- 24h：点赞 >= 120；评论 >= 10；转发 >= 20。
- 72h：点赞 >= 300；评论 >= 25；转发 >= 60。

### H1 爆点信号

- 评论里自然出现 2 个以上规则梗。
- 72h 转发 >= 点赞的 0.5 倍。
- 两个账号中至少一个账号出现稳定复读句式。

### H2 最低继续线

- 2h：出现至少 2 条“我老公/我婆婆/我家”代入评论；点赞 >= 20；收藏 >= 3。
- 24h：点赞 >= 100；评论 >= 8；转发 >= 20；收藏 >= 10。
- 72h：点赞 >= 250；评论 >= 20；转发 >= 60；收藏 >= 25。

### H2 爆点信号

- 评论区出现真实经历长评。
- 24h 收藏 >= 30。
- 72h 转发 >= 点赞的 0.3 倍。

## 诊断规则

- 两个账号同一假设都低于最低继续线：优先判断机制或执行失败。
- 一个账号过线、一个账号不过线：优先判断账号适配差异。
- H1 评论多但转发弱：规则梗可能成立，但故事转发动机不足。
- H2 收藏强但评论弱：实用判断成立，但情绪讨论弱，需要强化冲突和行动兑现。
- 任何一条出现平台风险、限流或明显争议：先暂停同类发布，不进入规则升级。

## 已完成 full_story_extract

- H1 源样本 `7649315939447871470`：已完成 8 页完整图集 VL 提取，证据文件为 `content-lab/full_story_extracts/2026-06-16-huayigegushi-h1-7649315939447871470.md` 和 `.json`。后续只提炼“家庭身份规则循环”机制，不能沿用年轻后妈、后后妈、未成年人或暧昧继亲关系等高风险桥段。
- H2 源样本 `7650413089900236066`：已完成 15 页完整图集 VL 提取，证据文件为 `content-lab/full_story_extracts/2026-06-16-huayigegushi-h2-7650413089900236066.md` 和 `.json`。

## 当前阻塞

本计划仍不能直接发布。进入发布前还需要：

1. 写 H1/H2 `generation_brief`，把源机制改写为 DoodleStory 原创故事方案。
2. 创建真实生成任务并得到 `content_id` 或 `task_id`。
3. 根据实际完成时间回填绝对 `planned_publish_time`，并确认是否启用第 3 条加速窗口。

## 下一步

进入 `generation_brief`：

- H1：从 `7649315939447871470` 提炼身份规则循环、递归升级和评论区规则梗触发，不复用源故事具体继亲关系。
- H2：从 `7650413089900236066` 提炼三回合生活冲突、行动兑现和真实家庭经验投射，不复用源故事具体婆媳桥段。
