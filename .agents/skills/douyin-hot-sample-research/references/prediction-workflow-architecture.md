# Prediction Workflow Architecture

This Skill is a prediction and experiment system, not a resource-pack builder. It has two user-facing entrypoints and one shared content library.

## User Entrypoints

### 1. New Lane Prediction

Use when the user wants to expand into a new content lane and has found a keyword.

Minimal user input:

- `keyword`: one keyword or phrase, such as `画一个故事`, `婆媳关系`, or `纯爱漫画`.
- `goal`: how many publishable hypotheses to produce, usually 3-10.
- `experiment_count`: how many experiments to plan, default 3.
- `account_group`: optional accounts to publish with. Prefer at least 2 accounts per important hypothesis.

The user should not need to provide complex JSON. The Skill can infer defaults:

- time window: latest 7 days
- sort modes: comprehensive, latest, most liked
- format: Douyin image-text
- generation route: DoodleStory story brief unless the user explicitly asks to replicate one sample

Default execution mode:

- Run one small step per user turn.
- Continue to the next step only after the user approves or says `继续`.
- Run the full sequence only when the user explicitly says `一次执行到位`, `跑完整流程`, `连续执行`, or an equivalent instruction.

Output:

- market snapshot
- category comparison
- source-origin hypotheses
- account-probe targets
- topic hypotheses
- experiment plan
- DoodleStory generation briefs

### 2. Account Review And Diagnosis

Use when the user wants to diagnose one account or review recently published works.

Minimal user input:

- `account`: account name, account id, or a local account profile path.
- `review_window`: e.g. last 7 days, last 30 days, or a batch of post ids.
- `post_data`: exported backend data, pasted table, CSV path, or connected data source.
- `published_content`: optional links or local generated-content ids.

Output:

- account baseline
- market expectation for the same period
- actual performance
- prediction deviation
- account-fit diagnosis
- next experiment adjustments

## Experiment Design

Every publishable hypothesis should become an experiment, not only a content item.

Recommended minimum:

- Important hypothesis: publish on at least 2 accounts.
- Same core story mechanism, controlled variations allowed.
- Keep one variable clear: title/hook, first image, realistic ending, story category, or account.
- Record predicted metrics before publishing.
- Review at fixed checkpoints: 2h, 24h, 72h.

Why two accounts:

- One account can underperform because of account mismatch, cold-start status, follower composition, or historical positioning.
- Two accounts help separate content mechanism failure from account distribution failure.
- If both accounts fail similarly, the content/hypothesis is suspect.
- If one account succeeds and one fails, account fit becomes the primary diagnosis.

## Backend Data Intake

Backend publishing data belongs to the experiment result layer.

It should not be stored as market scan data and should not be mixed with raw sample downloads.

Manual input options:

- pasted table from Douyin backend
- CSV/Excel export path
- JSON export path
- screenshots summarized into structured rows

Future automatic input options:

- platform API connector
- browser-assisted export collector
- internal publishing system callback

Recommended storage location:

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

Raw exports, screenshots, generated images, and large media should usually stay out of Git. Keep structured summaries and reviewed notes in Git when they are useful for future agents.

## Content Library Design

The content library is not a resource pack. It is a validated mechanism library.

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

The goal is to accumulate reusable atoms:

- hooks that actually stop scroll
- story structures that produce comments
- visual endings that increase trust
- account/category fit rules
- source origins that repeatedly produce hot topics

## Creating Hot Content From The Library

After enough validated content exists, new content should be generated from three inputs:

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

This is the path from following hot topics to creating hot topics:

- Find upstream source origins.
- Store validated mechanisms.
- Combine mechanisms with new social timing, comments, seasons, events, and account fit.
- Predict before publishing.
- Publish on at least 2 accounts when the hypothesis matters.
- Feed actual results back into the library.

## Relationship To Existing DoodleStory Modes

Keep existing modes:

- `DY爆款复刻`: sample-level executor. Use it to download, extract, and reproduce one known sample structure.
- `提取分镜`: direct generation from extracted page-by-page content.
- `故事方案`: original creation route from a structured brief.

Add conceptual mode:

- `热门预测创作`: strategy route. It starts from a topic hypothesis and produces a DoodleStory story brief.

Do not change `DY爆款复刻` to mean prediction. It should remain the faithful single-sample path. Prediction should happen before task creation.

## Iteration Loop

1. `market_scan`: collect 7-day results for a keyword across sort modes.
2. `topic_hypothesis`: produce predicted publishable topics.
3. `experiment_plan`: assign content to accounts, define checkpoints and expected metrics.
4. `generation_brief`: create DoodleStory-ready story plans.
5. `publish`: user or system publishes.
6. `post_result_intake`: user pastes/export/imports backend data.
7. `deviation_review`: compare prediction with actual result.
8. `strategy_update`: update category weights, account fit, source-origin map, and content-library reuse notes.

Iteration begins only when an experiment has both prediction and actual result. Market scan without publishing is research, not iteration.

## Stepwise User Experience

The Skill should feel like a guided operating system, not a large form.

For new lane prediction, the user can start with:

```text
用 douyin-hot-sample-research，关键词：画一个故事，做新赛道预测。
```

The first response should usually finish only `lane_intake`: normalize the goal, infer defaults, and say what `market_scan` will do next.

For account review, the user can start with:

```text
用 douyin-hot-sample-research，账号：xxx，做账号复盘。
```

The first response should usually finish only `review_intake`: confirm the review window, ask for or locate backend data, and say what `account_baseline` will do next.

Each step should end with:

```text
本轮完成：<one concrete artifact or decision>
下一步建议：<one next step>
你回复「继续」我就执行这一步；如果你说「一次执行到位」，我会连续跑完可执行步骤。
```

This keeps the user-facing input small while still allowing full automation when explicitly requested.
