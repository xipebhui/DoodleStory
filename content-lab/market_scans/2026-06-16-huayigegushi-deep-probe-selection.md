# 画一个故事深挖样本选择

- scan_id: `2026-06-16-huayigegushi-deep-probe-selection`
- experiment_id: `2026-06-16-huayigegushi-cycle-01`
- created_at: `2026-06-16`
- step: `deep_probe_selection`
- input_scoring: `content-lab/market_scans/2026-06-16-huayigegushi-market-scoring.md`
- scoring_output_dir: `output/douyin-hot-sample-analysis/huayigegushi-week-20260616-market-scoring`

## 选择原则

本轮只选择少量样本进入下一步采集，不直接生成内容。

选择标准：

- 必须是 `image_text`。
- 优先 A 类。
- 优先覆盖多个已被评分支撑的类目，而不是只追单条最高数据。
- 每个样本下一步都必须采集评论、账号主页和首尾页 `preview_vl`。
- 敏感题材只做风险和评论机制观察，不直接进入生成。

## 入选样本

| role | aweme_id | category | account | liked | comment | collect | share | image_count | reason |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| primary | 7649315939447871470 | family_marriage | 爱奔跑的小兰 | 57294 | 14169 | 1702 | 73903 | 8 | 家庭/代际循环，评论和转发都高，适合验证家庭循环机制是否能触发讨论和转发。 |
| primary | 7650413089900236066 | family_marriage | 分镜里的小晴 | 37188 | 1629 | 4452 | 51013 | 15 | 婆媳三回合，转发高，适合验证家庭婚姻里的“三回合冲突 + 男性解决问题”结构。 |
| primary | 7651192895256480858 | pure_love_healing | 一二小布布 | 48377 | 11771 | 2148 | 14110 | 15 | 纯爱治愈，评论高，适合和历史链路中已有的纯爱样本认知做连续验证。 |
| risk_observation | 7651205691718698483 | social_safety | 画不出她 | 71381 | 10550 | 925 | 3539 | 13 | 女性安全，互动强但题材敏感；只做风险、评论触发和平台边界观察，不直接生成。 |

## 暂缓样本

| aweme_id | category | account | reason |
|---|---|---|---|
| 7650160948988811435 | family_marriage | 瞎画制造机 | A 类且数据强，但本轮已有两个家庭婚姻样本；先防止同类过密。 |
| 7650819645629471857 | pure_love_healing | 灵梦叶 | A 类纯爱样本，但 `image_count` 很高，下一步采集和 VL 成本更高；先用 `一二小布布` 作为纯爱主样本。 |
| 7651448651148462326 | other_story | 有梦想的画渣 | A 类但只有 1 图，可能更像单页梗/回忆触发，不优先代表 DoodleStory 连续图文故事。 |
| 7651140880128209402 | pure_love_healing | 凌悦 | A 类，但本轮纯爱已选一个主样本；作为后续替补。 |

## 下一步采集项

对 3 个 primary 样本执行：

- 评论采集：至少高赞评论和高回复讨论。
- 账号主页：账号作品数、近期作品稳定性、是否依赖成熟账号积累。
- 首尾页 `preview_vl`：判断开头承诺、结尾形式、是否存在真实感证据页或强转折。

对 1 个 `risk_observation` 样本执行：

- 评论采集：只看用户讨论点和风险边界。
- 首尾页 `preview_vl`：只看表达方式，不做生成 brief。
- 不进入 DoodleStory 内容生成，除非后续人工明确批准并完成安全改写边界。

## 控制器判断

允许进入 `probe_collection`。

不允许：

- 直接生成故事方案。
- 直接发布实验内容。
- 把任一单条 A 类样本升级为规则。
- 用 `social_safety` 样本直接做仿写或复刻。

## 下一步

执行 `probe_collection`：对入选样本采集评论、账号主页和首尾页 `preview_vl`。
