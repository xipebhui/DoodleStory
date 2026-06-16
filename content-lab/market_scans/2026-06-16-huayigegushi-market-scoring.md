# 画一个故事市场评分

- scan_id: `2026-06-16-huayigegushi-market-scoring`
- experiment_id: `2026-06-16-huayigegushi-cycle-01`
- created_at: `2026-06-16`
- step: `market_scoring`
- input_raw_jsonl: `/Users/pengfei.shi/workspace/tmp-project/MediaCrawler/data_test/huayigegushi_week_20260616/douyin/jsonl/search_contents_2026-06-16.jsonl`
- scoring_output_dir: `output/douyin-hot-sample-analysis/huayigegushi-week-20260616-market-scoring`

## 评分结果

- raw_candidates: 43
- total_candidates_after_dedup: 33
- deduplicated: true
- grade_counts:
  - A: 8
  - B: 13
  - C: 7
  - D: 5
- media_type_by_grade:
  - A: `image_text` 8
  - B: `image_text` 13
  - C: `image_text` 7
  - D: `video_or_other` 5
- category_count: 5

## 类目横向对比

| category | candidates | A/B | A | B | likes | comments | shares | avg_score | top_titles |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| pure_love_healing | 12 | 8 | 3 | 5 | 220512 | 26201 | 32775 | 200.72 | 赌约是假的，心动是真的；圆心长久；不夜祈福 |
| family_marriage | 9 | 6 | 3 | 3 | 231393 | 22579 | 186350 | 218.19 | 命运里的家庭循环；婆媳间的三个回合；烂泥扶不上墙也有人推你前进 |
| other_story | 10 | 5 | 1 | 4 | 5137491 | 100521 | 2482311 | 206.4 | 浮华表象多假意；童年恶心事；听兰奇怪 |
| social_safety | 1 | 1 | 1 | 0 | 71381 | 10550 | 3539 | 235.17 | 被伤害的人为什么总要付出更大的代价 |
| suspense_horror | 1 | 1 | 0 | 1 | 5277 | 163 | 1526 | 205.64 | 要命房间 |

## A 类样本

| aweme_id | category | account | liked | comment | collect | share | image_count | title |
|---|---|---|---:|---:|---:|---:|---:|---|
| 7649315939447871470 | family_marriage | 爱奔跑的小兰 | 57294 | 14169 | 1702 | 73903 | 8 | 命运里的家庭循环 |
| 7651192895256480858 | pure_love_healing | 一二小布布 | 48377 | 11771 | 2148 | 14110 | 15 | 赌约是假的，心动是真的 |
| 7650413089900236066 | family_marriage | 分镜里的小晴 | 37188 | 1629 | 4452 | 51013 | 15 | 婆媳间的三个回合 |
| 7650160948988811435 | family_marriage | 瞎画制造机 | 65573 | 1947 | 4902 | 31160 | 15 | 哪怕你烂泥扶不上墙，也总有人愿意推你前进 |
| 7650819645629471857 | pure_love_healing | 灵梦叶 | 39222 | 4145 | 5806 | 5279 | 7 | 圆心长久 |
| 7651140880128209402 | pure_love_healing | 凌悦 | 32325 | 3566 | 7810 | 3574 | 10 | 不夜祈福 |
| 7651448651148462326 | other_story | 有梦想的画渣 | 9090 | 2625 | 436 | 76906 | 1 | 你小时候有做过最恶心的事儿吗 |
| 7651205691718698483 | social_safety | 画不出她 | 71381 | 10550 | 925 | 3539 | 7 | 被伤害的人为什么总要付出更大的代价 |

## 关键判断

当前证据支持 `画一个故事` 进入深挖，不支持直接发布。

支持点：

- A/B 共 21 个，其中 A 8 个、B 13 个。
- A/B 全部为 `image_text`，说明该关键词确实有图文故事样本，不只是视频、口播或绘画过程。
- `family_marriage` 和 `pure_love_healing` 都有多个 A/B 样本，优先级高于单个孤立爆款。
- `social_safety` 虽只有 1 个 A，但互动强，适合谨慎观察，不适合马上复刻。
- 507 万赞的 `拾光故事馆` 样本被识别为 `video_or_other`，不进入图文 A/B 证据，避免单条异常值带偏。

限制：

- 还没有评论数据，不能判断评论触发点。
- 还没有账号主页数据，不能判断账号积累和可模仿性。
- 还没有首尾页 VL，不能判断真实感结尾、结构转折和图文可改写价值。
- 还没有全量故事提取，不能进入 DoodleStory 生成 brief。

## 建议深挖对象

1. `7649315939447871470`：家庭循环，A，8 图，评论和转发都高，适合探测家庭/代际循环机制。
2. `7650413089900236066`：婆媳三回合，A，15 图，转发高，适合探测家庭婚姻结构和男性角色解决问题机制。
3. `7651192895256480858`：纯爱治愈，A，15 图，评论高，复用历史链路里已有样本认知，可做连续验证。
4. `7651205691718698483`：女性安全，A，7 图，评论高但题材敏感，适合只做风险和评论机制观察，不直接生成。

## 下一步

执行 `deep_probe_selection`，从 A 类样本中确定 2-4 个进入评论、账号主页和首尾页 `preview_vl` 探测。
