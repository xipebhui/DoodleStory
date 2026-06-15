# 抖音预测型内容链路架构

这个 Skill 是预测与实验系统，不是素材包系统。它有两个用户入口和一个共享内容库。默认文档、步骤提示和交付物说明都使用中文；保留必要的英文 step id、字段名和脚本参数，方便自动化执行。

## 目录

- [用户入口](#用户入口)
- [实验设计](#实验设计)
- [后台数据接入](#后台数据接入)
- [内容库设计](#内容库设计)
- [从内容库创造新热点](#从内容库创造新热点)
- [与 DoodleStory 现有模式的关系](#与-doodlestory-现有模式的关系)
- [迭代闭环](#迭代闭环)
- [账号探测原则](#账号探测原则)
- [生成前全量 VL 原文提取](#生成前全量-vl-原文提取)
- [分步用户体验](#分步用户体验)

## 用户入口

### 1. 新赛道预测

用户找到一个关键词，想判断这个赛道是否值得做时使用。

最小输入：

- `keyword`: one keyword or phrase, such as `画一个故事`, `婆媳关系`, or `纯爱漫画`.
- `goal`: how many publishable hypotheses to produce, usually 3-10.
- `experiment_count`: how many experiments to plan, default 3.
- `account_group`: optional accounts to publish with. Prefer at least 2 accounts per important hypothesis.

用户不需要提供复杂 JSON。Skill 默认推断：

- time window: latest 7 days
- sort modes: comprehensive, latest, most liked
- format: Douyin image-text
- generation route: DoodleStory story brief unless the user explicitly asks to replicate one sample

默认执行节奏：

- 每轮只执行一个小 step。
- 用户同意或回复 `继续` 后，才执行下一步。
- 只有用户明确说 `一次执行到位`、`跑完整流程`、`连续执行` 等，才连续执行。

输出：

- market snapshot
- category comparison
- source-origin hypotheses
- account-probe targets
- topic hypotheses
- experiment plan
- DoodleStory generation briefs

### 2. 账号复盘诊断

用户想诊断某个账号，或复盘一批已发布作品时使用。

最小输入：

- `account`: account name, account id, or a local account profile path.
- `review_window`: e.g. last 7 days, last 30 days, or a batch of post ids.
- `post_data`: exported backend data, pasted table, CSV path, or connected data source.
- `published_content`: optional links or local generated-content ids.

输出：

- account baseline
- market expectation for the same period
- actual performance
- prediction deviation
- account-fit diagnosis
- next experiment adjustments

## 实验设计

每个可发布假设都应该变成实验，而不只是一个内容条目。

推荐最低要求：

- Important hypothesis: publish on at least 2 accounts.
- Same core story mechanism, controlled variations allowed.
- Keep one variable clear: title/hook, first image, realistic ending, story category, or account.
- Record predicted metrics before publishing.
- Review at fixed checkpoints: 2h, 24h, 72h.

为什么至少两个账号：

- One account can underperform because of account mismatch, cold-start status, follower composition, or historical positioning.
- Two accounts help separate content mechanism failure from account distribution failure.
- If both accounts fail similarly, the content/hypothesis is suspect.
- If one account succeeds and one fails, account fit becomes the primary diagnosis.

## 后台数据接入

抖音后台发布数据属于实验结果层。

不要把后台数据混进市场扫描数据，也不要和原始下载素材混放。

Manual input options:

- pasted table from Douyin backend
- CSV/Excel export path
- JSON export path
- screenshots summarized into structured rows

Future automatic input options:

- platform API connector
- browser-assisted export collector
- internal publishing system callback

推荐目录结构：

```text
content-lab/
  accounts/
    <account_id>/
      profile.md
      baseline.json
      snapshots/
        2026-06-15.json
  experiments/
    <experiment_id>/
      experiment.md
      prediction.json
      generation_brief.md
      publish_plan.json
      post_results/
        <account_id>_<post_id>_2h.json
        <account_id>_<post_id>_24h.json
        <account_id>_<post_id>_72h.json
      review.md
      strategy_update.json
  market_scans/
    <date>_<keyword>/
      search_comprehensive.jsonl
      search_latest.jsonl
      search_most_liked.jsonl
      category_summary.json
      candidate_scores.json
  content_library/
    items/
      <content_id>/
        mechanism.json
        story_brief.md
        storyboard.json
        generation_notes.md
        publish_records.json
        learning.md
  strategy_state/
    keyword_weights.json
    category_weights.json
    account_fit_profile.json
    source_origin_map.json
    failed_hypotheses.jsonl
    successful_hypotheses.jsonl
```

原始导出、截图、生成图片和大媒体通常不进 Git；结构化摘要和复盘结论可以进 Git，方便后续 agent 继续使用。

## 内容库设计

内容库不是素材包，而是验证过的机制库。

Each content item should record:

- `content_id`
- `source_hypothesis_id`
- `market_category`
- `source_origin_hypothesis`
- `hook_mechanism`
- `story_archetype`
- `comment_trigger`
- `visual_mechanism`
- `realistic_scene_role`
- `generation_route`
- `account_fit`
- `predicted_result`
- `actual_result`
- `deviation_type`
- `reuse_status`: validated, mixed, failed, retired
- `reuse_notes`

目标是沉淀可复用原子：

- hooks that actually stop scroll
- story structures that produce comments
- visual endings that increase trust
- account/category fit rules
- source origins that repeatedly produce hot topics

## 从内容库创造新热点

当验证内容足够多后，新内容由三个输入组合：

1. validated content mechanisms
2. current market scan
3. current or upcoming hotspot

Example:

```text
validated mechanism:
  family_marriage, three conflict rounds, quiet husband acts at key moment, high share rate

current hotspot:
  college entrance exam family pressure

new hypothesis:
  mother-in-law dismisses daughter-in-law's exam dream three times; husband quietly creates study conditions; final realistic desk photo proves years of support
```

这是从追热点走向创造热点的路径：

- Find upstream source origins.
- Store validated mechanisms.
- Combine mechanisms with new social timing, comments, seasons, events, and account fit.
- Predict before publishing.
- Publish on at least 2 accounts when the hypothesis matters.
- Feed actual results back into the library.

## 与 DoodleStory 现有模式的关系

保留现有模式：

- `DY爆款复刻`: sample-level executor. Use it to download, extract, and reproduce one known sample structure.
- `提取分镜`: direct generation from extracted page-by-page content.
- `故事方案`: original creation route from a structured brief.

新增概念模式：

- `热门预测创作`: strategy route. It starts from a topic hypothesis and produces a DoodleStory story brief.

不要把 `DY爆款复刻` 改成预测系统。它仍然是单样本忠实执行路径。预测发生在任务创建之前。

## 迭代闭环

1. `market_scan`: collect 7-day results for a keyword across sort modes.
2. `topic_hypothesis`: produce predicted publishable topics.
3. `experiment_plan`: assign content to accounts, define checkpoints and expected metrics.
4. `full_story_extract`: run full VL on selected seed samples to obtain original story text and structure.
5. `generation_brief`: analyze original text and rewrite it into DoodleStory-ready original story plans.
6. `publish`: user or system publishes.
7. `post_result_intake`: user pastes/export/imports backend data.
8. `deviation_review`: compare prediction with actual result.
9. `strategy_update`: update category weights, account fit, source-origin map, and content-library reuse notes.

只有实验同时拥有“发布前预测”和“发布后真实结果”，才算进入迭代。只有市场扫描还只是研究。

## 账号探测原则

账号数据可以全量抓取，但分析默认只看最近 N 条，默认 N=20。

账号作品数、粉丝数、总获赞/互动不是单纯正向信号。它们说明账号有基础用户和长期积累，可能提高原样本流量，但会削弱“快速模仿”的可信度：

- 少作品 + 高流量：机制可能更容易拆出来，模仿优先级更高。
- 多作品/大粉丝 + 高流量：记录 `large_mature_account_penalty`，不能直接认为新号也能复现。
- 大号稳定模板仍有参考价值，但更适合学习结构，不适合直接预测新账号表现。
- 账号复盘时必须把账号历史中位数作为参照，而不是只看市场样本绝对数据。

## 生成前全量 VL 原文提取

`preview_vl` 只用于判断首尾钩子、结尾机制和是否值得深挖，不能直接生成最终故事。

进入 `generation_brief` 前必须先完成：

1. 对被批准作为种子样本的作品运行 `full_story_document`。
2. 用 DoodleStory 现有 VL 链路按原图顺序提取完整原文、对白、旁白、内心 OS、画面和分格。
3. 分析原文文案结构：开头、冲突、转折、节奏、结尾、评论触发点。
4. 再做优化和原创改写，输出 DoodleStory `故事方案`，而不是忠实复制源作品。

如果没有完成全量 VL，只能输出“选题假设”或“实验计划”，不能输出最终可生成故事。

## 分步用户体验

这个 Skill 应该像一个分步操作系统，而不是一个大表单。

For new lane prediction, the user can start with:

```text
用 douyin-hot-sample-research，关键词：画一个故事，做新赛道预测。
```

第一次响应通常只完成 `lane_intake`：规范目标、推断默认值、说明下一步 `market_scan` 要做什么。

For account review, the user can start with:

```text
用 douyin-hot-sample-research，账号：xxx，做账号复盘。
```

第一次响应通常只完成 `review_intake`：确认复盘窗口、定位后台数据、说明下一步 `account_baseline`。

Each step should end with:

```text
本轮完成：<one concrete artifact or decision>
下一步建议：<one next step>
你回复「继续」我就执行这一步；如果你说「一次执行到位」，我会连续跑完可执行步骤。
```

这样用户输入足够简单，同时在明确授权时仍能自动跑完整流程。
