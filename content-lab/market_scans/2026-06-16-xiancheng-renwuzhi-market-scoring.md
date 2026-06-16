# 县城人物志市场评分

- scan_id: `2026-06-16-xiancheng-renwuzhi-market-scoring`
- experiment_id: `2026-06-16-xiancheng-renwuzhi-cycle-01`
- created_at: `2026-06-16`
- step: `market_scoring`
- input_raw_jsonl: `/Users/pengfei.shi/workspace/tmp-project/MediaCrawler/data_test/xiancheng_renwuzhi_week_20260616/douyin/jsonl/search_contents_2026-06-16.jsonl`
- scoring_output_dir: `output/douyin-hot-sample-analysis/xiancheng-renwuzhi-week-market-scoring`

## 评分结果

- raw_candidates: 66
- total_candidates_after_dedup: 48
- deduplicated: true
- grade_counts:
  - A: 0
  - B: 0
  - C: 1
  - D: 47
- category_count: 7

## 类目横向对比

| category | candidates | A/B | likes | comments | shares | avg_score | top_titles |
|---|---:|---:|---:|---:|---:|---:|---|
| uncategorized | 25 | 0 | 272617 | 8203 | 103840 | 87.93 | 赛博人物志第163期；当你在小县城上学；赛博人物志之刘雨鑫 |
| family_marriage | 3 | 0 | 57948 | 3175 | 29960 | 146.91 | 县城婚姻，是一场普通人cosplay小资的闹剧；山西孩子最爱的夜宵炒饼丝；王明礼 |
| life_growth | 14 | 0 | 46141 | 3538 | 21991 | 111.31 | 县城里最值得学习的三种人生哲学；拜访云南一个小镇上的守护人；小县城生活有多充实 |
| workplace_social | 1 | 0 | 14506 | 170 | 6057 | 190.87 | 实体店老板拍日常vlog开头怎么写 |
| suspense_horror | 1 | 0 | 1603 | 50 | 78 | 127.72 | 毛岸英人物故事 |
| other_story | 3 | 0 | 103 | 1 | 4 | 19.91 | 家乡英雄故事；明星故事；民间故事美女县长 |
| pure_love_healing | 1 | 0 | 4 | 3 | 0 | 18.6 | 小城慢生活 |

## 对标账号相关样本

| aweme_id | account | grade | reason | media_type | liked | comment | collect | share | title |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 7650896432228381093 | 写手一条城 | D | not_image_text | video_or_other | 45477 | 2887 | 8359 | 28973 | 县城婚姻，是一场普通人cosplay小资的闹剧 |
| 7649899694922927402 | 写手一条城 | D | not_image_text | video_or_other | 21402 | 655 | 5246 | 9132 | 县城里最值得学习的三种人生哲学 |

## 控制器判断

本轮不能把 `写手一条城` 的热度直接解释成“图文赛道成立”。

当前证据更精确地支持：

- `县城人物类型化` 这个内容机制有可观察热度。
- 对标账号的两条相关内容互动强，尤其收藏和转发不低。
- 但这两条被脚本识别为 `video_or_other`，不是 DoodleStory 当前优先验证的图文样本。
- 搜索结果中大量内容被归到 `uncategorized`，说明现有评分桶对“县城人物类型化 / 县城文学 / 人设标签”不够贴合。

因此，本轮不允许：

- 直接进入 DoodleStory 生成。
- 直接发布县城人物志图文。
- 把该机制写入成功规则。

允许进入：

- `deep_probe_selection`：选择少量高互动样本做账号主页、评论和形式探测。

## 建议深挖对象

1. `7650896432228381093`：`写手一条城`，县城婚姻、小资 cosplay，互动强，最贴近用户提出的类型化方向。
2. `7649899694922927402`：`写手一条城`，县城人生哲学，验证同一账号是否有连续机制。
3. `7650806595601506724`：县城人脉王的一生，标题机制贴近“县城人物类型命名”，但互动弱于前两条。
4. `7649343076632137001`：当你在小县城上学，非同一账号但县城生活观察流量强，可作为横向机制对照。

## 下一步

执行 `deep_probe_selection`，先确定需要采集评论和账号主页的 2-4 个样本。若后续仍找不到图文形态样本，只能把本方向定义为“视频/口播机制可改编为图文的假设”，不能定义为“图文赛道已验证”。
