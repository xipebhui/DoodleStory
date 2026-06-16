# 画一个故事 probe_collection

- experiment_id: `2026-06-16-huayigegushi-cycle-01`
- keyword: `画一个故事`
- collected_at: `2026-06-16`
- workflow_step: `probe_collection`

## 输入证据

- deep probe selection: `content-lab/market_scans/2026-06-16-huayigegushi-deep-probe-selection.md`
- search raw JSONL: `/Users/pengfei.shi/workspace/tmp-project/MediaCrawler/data_test/huayigegushi_week_20260616/douyin/jsonl/search_contents_2026-06-16.jsonl`
- detail contents: `/Users/pengfei.shi/workspace/tmp-project/MediaCrawler/data_test/huayigegushi_probe_20260616/douyin/jsonl/detail_contents_2026-06-16.jsonl`
- detail comments: `/Users/pengfei.shi/workspace/tmp-project/MediaCrawler/data_test/huayigegushi_probe_20260616/douyin/jsonl/detail_comments_2026-06-16.jsonl`
- creator profiles: `/Users/pengfei.shi/workspace/tmp-project/MediaCrawler/data_test/huayigegushi_creator_probe_20260616/douyin/jsonl/creator_creators_2026-06-16.jsonl`
- risk creator profile: `/Users/pengfei.shi/workspace/tmp-project/MediaCrawler/data_test/huayigegushi_creator_probe_risk_20260616/douyin/jsonl/creator_creators_2026-06-16.jsonl`
- probe scoring output: `output/douyin-hot-sample-analysis/huayigegushi-week-20260616-probe-scoring`
- preview VL output: `output/douyin-hot-sample-analysis/huayigegushi-week-20260616-probe-vl/preview_vl_results.json`

## 采集范围

| aweme_id | role | title | comments_collected | creator_probe | preview_vl |
| --- | --- | --- | ---: | --- | --- |
| `7649315939447871470` | primary | 命运里的家庭循环 | 50 | 完成 | 前 2 页、后 2 页 |
| `7650413089900236066` | primary | 婆媳间的三个回合 | 50 | 完成 | 前 2 页、后 2 页 |
| `7651192895256480858` | primary | 赌约是假的，心动是真的 | 50 | 完成 | 前 2 页、后 2 页 |
| `7651205691718698483` | risk_observation | 被伤害的人，为什么总要付出更大的代价？ | 50 | 完成 | 前 2 页、后 2 页 |

说明：`creator` 模式会继续拉作者作品明细。为避免把主页探测扩展成大规模历史作品采集，本轮在拿到主页卡后主动终止了长尾作品采集；主页字段可用，作品列表只作为辅助，不视为完整作者库。

## 账号可模仿度

| aweme_id | account | fans | works | total_interaction | mimicability | observation |
| --- | --- | ---: | ---: | ---: | --- | --- |
| `7649315939447871470` | 爱奔跑的小兰 | 728 | 26 | 133997 | high | 低粉、低作品数但单条高转发，说明机制本身可能强于账号势能。 |
| `7650413089900236066` | 分镜里的小晴 | 549 | 10 | 43799 | high | 低粉低作品数，且主页定位就是画故事/治愈，适合作为第一批可复制机制参考。 |
| `7651192895256480858` | 一二小布布 | 28125 | 130 | 1461505 | medium | 成熟账号、强角色 IP 和表情包生态，适合作为纯爱结构参考，不适合直接判断新号可复制性。 |
| `7651205691718698483` | 画不出她 | 3098 | 16 | 353798 | risk_observation | 低到中粉但社会安全题材强情绪，机制可观察，题材不进入第一轮生成 brief。 |

## 评论机制

### `7649315939447871470` 家庭循环

高赞评论集中在“规则怪谈式家庭循环”和荒诞伦理包袱：

- `你是房主吗，怎么老是踢人`：119936 赞，8240 回复。
- `我也要死吗`：14092 赞，240 回复。
- `流水的家人，铁打的你。`：10005 赞，120 回复。
- `规则怪谈：当房子人数为3时，自动抹除年龄最大者`：7537 赞，156 回复。

判断：这条的核心不是“家庭伦理苦情”，而是家庭关系被观众解读成荒诞规则。适合改造成“现实设定 + 规则怪谈式评论触发”的故事机制。

### `7650413089900236066` 婆媳三回合

高赞评论集中在“丈夫立场”和真实婚姻经验投射：

- `我老公要是那样，我婆婆第一反应是喝老鼠药...`：3659 赞，238 回复。
- `可是有的男人就算你是对的，他还会向着他妈`：953 赞，79 回复。
- `我妈也不容易呀...有多少结婚的女性听过这句话？`：235 赞，30 回复。

判断：这条不是靠奇观，而是让用户在评论区代入“我的老公/婆婆/婆家”。适合验证“家庭冲突三回合 + 男方行动兑现”的图文结构。

### `7651192895256480858` 纯爱治愈

高赞评论集中在“甜到想破坏”和结尾反转金句：

- `我准备明天把这两个炖了，各位有什么忌口吗？`：6217 赞，795 回复。
- `那三百是我出的`：1789 赞，80 回复。
- `你俩过来一点，靠近一点，我有话跟你们说`：801 赞，171 回复。

判断：纯爱样本的评论强，但很依赖角色可爱度、账号 IP 和最后真人合照的可信度。可作为结构参考，不作为第一优先实验样本。

### `7651205691718698483` 社会安全风险样本

高赞评论集中在公共议题声援、复制传播和情绪动员：

- `老年女性的需求也要被看到好吗！`：5078 赞，269 回复。
- `奶油火鸡面还是原味火鸡面？`：3368 赞，953 回复。
- `这个世界还有救吗。。。`：1703 赞，33 回复。
- 大段复制评论围绕女性安全、加害者命名和二次伤害。

判断：这条证明公共议题可以带来强评论，但风险和平台不确定性都高。本轮只保留“评论动员机制”和“证据式结尾”观察，不进入生成候选。

## 首尾页 preview_vl

### `7649315939447871470`

- 前 2 页：父亲娶年轻后妈，主角无法开口叫妈。开头钩子是强伦理错位。
- 后 2 页：后后妈比主角更小，最后变成主角与后后妈相依为命。结尾不是实拍证据，而是荒诞循环继续升级。
- 结尾证据类型：插画。
- last_page_real_photo: `false`

### `7650413089900236066`

- 前 2 页：婆婆给弟媳旧床单，把新床单藏起来；弟媳沉默但拒绝躺上去。开头冲突具体、生活化。
- 后 2 页：母亲再没说过弟媳半句，年轻男性严肃出场，旁白强调“不吵架，但能把事办绝”。
- 结尾证据类型：插画人物态度兑现。
- last_page_real_photo: `false`

### `7651192895256480858`

- 前 2 页：宿舍打赌追校花，每人给 100，主角答应。开头是轻喜剧赌约。
- 后 2 页：女生揭示“三百是我出的”，最后一页是真人夜间合照。
- 结尾证据类型：真人合照。
- last_page_real_photo: `true`
- 风险：真人照片增强可信度，但对 DoodleStory 原创生成会带来肖像/隐私和不可复刻风险。

### `7651205691718698483`

- 前 2 页：退休年龄夫妻当保安，队长借贴消防标签把女保安骗入地下车库。开头直接进入社会伤害事件。
- 后 2 页：辞退通知书和一家人背影，强调讨回公道不容易。
- 结尾证据类型：文书式证据 + 插画背影。
- last_page_real_photo: `false`
- 风险：涉及性侵/公共事件/女性安全，不能作为第一轮可生成 brief。

## 控制器判断

`画一个故事` 关键词不是伪赛道。最近 7 天样本里存在多个高互动图文故事，且至少两个低粉低作品账号跑出了强互动，说明该关键词下有可实验空间。

本轮更适合从 `family_marriage` 方向进入，而不是先做纯爱或社会安全：

- `家庭循环`：最强在荒诞规则评论，适合做“家庭关系异常循环”的原创故事。
- `婆媳三回合`：最强在真实婚姻代入，适合做“三次冲突 + 不吵架的行动兑现”。
- `纯爱治愈`：有强结构，但账号成熟度和真人结尾依赖较大，放入第二优先。
- `社会安全`：评论动员强，但题材风险高，只观察，不生成。

## 下一步

进入 `topic_hypothesis`：

1. 输出 2 个可发布假设，优先围绕 `family_marriage`。
2. 每个假设写清预测机制、用户需求、风险边界和 2h/24h/72h 指标。
3. 暂不进入 `full_story_extract`，除非用户批准某个具体种子样本进入生成 brief。
