---
name: douyin-hot-sample-research
description: Use when building or updating a Douyin image-text hot sample library for DoodleStory content experiments. Trigger when the user asks to research recent Douyin hot samples, search keywords or hot boards with douyin-downloader, filter image-text/gallery posts by freshness and engagement, download selected works, inspect comments/basic metrics, or decide whether to run lightweight first/last-page VL inspection or full DoodleStory story extraction.
---

# Douyin Hot Sample Research

## Purpose

Use `douyin-downloader` and MediaCrawler as the collection base for DoodleStory's hot sample library. The first step is basic data acquisition: collect recent search/hot-board evidence, filter candidate image-text works, download only selected samples, and collect metrics or comments needed for the next analysis layer.

For keyword search, prefer the browser-state collector in this skill when direct `douyin-downloader` search is blocked by Douyin verification. It opens Douyin search with an existing logged-in browser `storage_state`, listens to the real page search response, and writes candidate evidence for review.

Downloaded image understanding should reuse DoodleStory's existing content-extraction VL path. Do not treat Codex manual image viewing as the runtime extraction pipeline.

After basic data acquisition, analyze the account, comments, opening/ending visuals, and the relationship between copy and discussion. These analysis notes are what later let the Skill evolve its own keyword, scoring, VL-scope, and topic-direction strategy.

This skill does not promise traffic or automate platform scraping beyond the local crawler/downloader's visible capabilities. Keep the workflow evidence-first and small enough to review.

## Read First

1. `/Users/pengfei.shi/workspace/tmp-project/douyin-downloader/README.zh-CN.md`
2. `/Users/pengfei.shi/workspace/tmp-project/douyin-downloader/core/discovery.py`
3. `/Users/pengfei.shi/workspace/tmp-project/douyin-downloader/core/api_client.py`
4. `/Users/pengfei.shi/workspace/tmp-project/douyin-downloader/core/comments_collector.py`
5. `/Users/pengfei.shi/workspace/tmp-project/DoodleStory/backend/app/services/media_text_extraction.py`
6. `/Users/pengfei.shi/workspace/tmp-project/DoodleStory/backend/app/api/content_extractions.py`
7. `/Users/pengfei.shi/workspace/tmp-project/DoodleStory/backend/app/prompts/parse_extracted_storyboard_v1.md`
8. `references/research-fields.md`
9. `references/multidimensional-analysis-strategy.md`
10. `references/seven-day-search-processing.md`
11. `references/prediction-workflow-architecture.md`

## Workflow

### 0. Choose The User Entrypoint

This Skill has two natural user-facing entrypoints. Do not ask the user for a complex JSON input.

Use `new_lane_prediction` when the user has a keyword and wants to expand into a new lane:

- Minimal input: keyword, desired number of topic hypotheses, optional account group.
- Default window: latest 7 days.
- Default sort modes: comprehensive, latest, most liked.
- Output: market snapshot, topic hypotheses, experiment plan, and DoodleStory generation briefs.

Use `account_review` when the user wants to diagnose an account or published batch:

- Minimal input: account name/id/path, review window, and post performance data.
- Post data can be pasted manually, loaded from CSV/JSON, or later provided by a connector.
- Output: account baseline, market expectation, actual performance, deviation diagnosis, and next experiment adjustments.

Important boundary:

- `DY爆款复刻` remains a single-sample executor: download, VL extract, and create an `extracted_storyboard` task.
- Prediction work should happen before task creation. The prediction route should produce a story brief for DoodleStory's `故事方案` path unless the user explicitly wants faithful sample reproduction.

See `references/prediction-workflow-architecture.md` for the experiment, data-intake, and content-library design.

### 1. Basic Data Acquisition: Research First

Start from keywords or hot-board terms. Prefer recent evidence:

- Priority 1: within 7 days.
- Priority 2: within 30 days.
- Priority 3: older samples only as structure references, not first-batch experiment candidates.

Use browser-state search for keyword research:

```bash
/Users/pengfei.shi/workspace/tmp-project/social-auto-upload/.venv/bin/python \
  .agents/skills/douyin-hot-sample-research/scripts/browser_search_collect.py \
  --keyword "故事" \
  --storage-state /Users/pengfei.shi/workspace/tmp-project/social-auto-upload/cookies/douyin_douyin_test.json
```

The default output directory is `/Users/pengfei.shi/workspace/tmp-project/douyin-downloader/Downloaded/browser_search`. The script writes raw responses, all parsed works, gallery/image-text candidates, meta, and a Markdown summary. It does not print cookie values. If it captures no search response, treat that as a hard blocker and inspect login or verification state; do not invent replacement data.

The collector defaults to `--entry-mode ui`: it opens the Douyin home page, types the keyword into the search box, and presses Enter. Directly opening the search URL can load the search shell without triggering result responses; use `--entry-mode url` only for diagnosis.

Use `douyin-downloader` hot-board commands and selected direct search only when they work:

```bash
cd /Users/pengfei.shi/workspace/tmp-project/douyin-downloader
.venv/bin/python run.py --hot-board 30 -p ./Downloaded
.venv/bin/python run.py --search "故事" --search-max 100 -p ./Downloaded
```

The CLI currently exposes `--search` and `--search-max`; the lower-level `search_aweme` function also supports `sort_type` and `publish_time`. If freshness is critical, call the Python API directly or add CLI flags in a separate implementation task.

### 2. Basic Data Acquisition: Filter Candidates

Keep candidates that are likely useful for DoodleStory:

- `aweme_type` / metadata indicates gallery or image-text content.
- `create_time` is recent enough for the requested research window.
- `statistics` shows meaningful engagement: digg, comment, collect, share.
- The description/title has a reusable story structure, not only a one-off meme.
- The visual form can be recreated as original image-text content without relying on copyrighted clips or celebrity/IP footage.

Reject candidates that depend on unauthorized copyrighted material, scraped private data, or platform behavior that cannot be verified from the downloader output.

After MediaCrawler keyword search, use the analyzer to convert raw JSONL into a candidate score table:

```bash
python .agents/skills/douyin-hot-sample-research/scripts/analyze_search_results.py \
  --contents /Users/pengfei.shi/workspace/tmp-project/MediaCrawler/data_test/huayigegushi_week/douyin/jsonl/search_contents_2026-06-15.jsonl \
  --out-dir output/douyin-hot-sample-analysis/huayigegushi-week
```

If comments have been collected for promoted samples, pass the comments JSONL too:

```bash
python .agents/skills/douyin-hot-sample-research/scripts/analyze_search_results.py \
  --contents /Users/pengfei.shi/workspace/tmp-project/MediaCrawler/data_test/huayigegushi_week/douyin/jsonl/search_contents_2026-06-15.jsonl \
  --comments /Users/pengfei.shi/workspace/tmp-project/MediaCrawler/data_test/comment_probe_top_a/douyin/jsonl/detail_comments_2026-06-15.jsonl \
  --out-dir output/douyin-hot-sample-analysis/huayigegushi-week-with-comments
```

The analyzer writes `candidate_scores.csv`, `candidate_scores.json`, and `analysis_report.md`. It grades samples A/B/C/D using freshness, media type, likes, comments, collections, shares, share rate, collection rate, comment rate, tags, and optional collected-comment signals.

If creator profiles have already been collected for some authors, pass them too. The analyzer will add creator works count, follower count, and account mimicability labels:

```bash
python .agents/skills/douyin-hot-sample-research/scripts/analyze_search_results.py \
  --contents /Users/pengfei.shi/workspace/tmp-project/MediaCrawler/data_test/huayigegushi_week/douyin/jsonl/search_contents_2026-06-15.jsonl \
  --creators /Users/pengfei.shi/workspace/tmp-project/MediaCrawler/data_test/account_probe_yierbubu/douyin/jsonl/creator_creators_2026-06-15.jsonl \
  --out-dir output/douyin-hot-sample-analysis/huayigegushi-week-seven-day-processing
```

The analyzer also writes `category_summary.csv` and `category_summary.json`. Use these files to compare which content categories are hot across the whole 7-day result set before choosing individual samples.

### 3. Seven-Day Search Decision Layer

After a recent search run, process the whole result set before diving into a single work:

- Compare categories horizontally: count A/B works, total likes, comments, shares, median likes, and representative titles.
- Prioritize categories with multiple A/B works over categories carried by one isolated outlier.
- Mark account probing priority for high-signal samples. Works with high traffic and available `sec_uid` should be probed first.
- Prefer accounts that are easier to imitate: fewer works plus high traffic, clear repeated format, image-text-heavy output, and no dependency on celebrity/IP footage.
- Treat `needs_account_probe` as an explicit next action, not as a final judgment.

For realistic endings:

- If the last page is a real photo, screenshot, document, chat record, or proof-like image, record it as a reusable format mechanism.
- Do not copy the original real person or private evidence.
- Recreate the authenticity function with original assets, authorized material, or image-2 realistic-scene generation.
- The research question is: what hot mechanism can become an original real-feeling scene?

See `references/seven-day-search-processing.md` for category labels, mimicability labels, and realistic-ending generation strategy.

For new-lane prediction, convert this layer into topic hypotheses and experiments:

- Each important hypothesis should be tested on at least 2 accounts when possible.
- Record expected results before publishing.
- Store actual backend data after publishing under the experiment result layer.
- If actual results seriously diverge from prediction, diagnose whether the market read, account fit, story mechanism, visual execution, or realistic ending failed.

### 4. Basic Data Acquisition: Download Selected Works

After filtering browser search JSONL or downloader search JSONL, download selected `share_url`, `video/note` URL, or `aweme_id` URL with `douyin-downloader`. Turn on JSON metadata and comments when the research needs feedback signals:

```yaml
json: true
comments:
  enabled: true
  include_replies: false
  max_comments: 200
  page_size: 20
```

The downloader writes `*_data.json`, media files, optional `*_comments.json`, and `download_manifest.jsonl`.

### 5. Basic Data Acquisition: Summarize Local Evidence

Use the bundled summarizer after direct downloader search or download:

```bash
python .agents/skills/douyin-hot-sample-research/scripts/summarize_samples.py \
  --downloader-root /Users/pengfei.shi/workspace/tmp-project/douyin-downloader \
  --data-root /Users/pengfei.shi/workspace/tmp-project/douyin-import-service/storage \
  --format markdown
```

Use the summary as a starting point. Inspect raw JSON for any sample that will drive a decision.

For browser-state search output, start from the generated `*_summary.md` and `*_gallery.jsonl` files under `Downloaded/browser_search`, then inspect the matching `*_raw_responses.json` before making a sample-library decision.

### 6. Account And Discussion Analysis

Run this layer only for A candidates and strong B candidates. Do not spend full analysis effort on every search hit.

Account homepage analysis answers whether the sample is a repeatable account pattern or a one-off viral work:

- Collect creator profile basics when available: `sec_uid`, nickname, bio, follower count, total favorited/interactions, and works count.
- Inspect recent works from the same account, preferably the latest 20 works before expanding wider.
- Compare traffic distribution across recent works: median, p75, p90, max, max-to-median ratio, and coefficient of variation for likes, comments, collects, and shares.
- Classify the account pattern as `stable_template`, `viral_outlier`, `emerging_series`, or `mixed_account`.
- Treat stable repeated structures as stronger experiment evidence than isolated old hits.
- Give extra priority to accounts with fewer works but high traffic. This often means the format is newer, simpler, and less dependent on mature account memory.

Comment analysis is a first-class topic-direction signal:

- Start with high-like comments and high-reply comments for promoted samples.
- Label comment clusters such as `emotional_resonance`, `identity_projection`, `moral_judgment`, `plot_question`, `request_followup`, `real_story_probe`, `topic_seed`, and `format_feedback`.
- Record what users are actually discussing, not only whether comments are positive.
- Use comment-derived `topic_seed` and `request_followup` signals to propose the next keyword and selection direction.

Combine copy and comments before deciding the next experiment:

- Compare the title/first-page promise, story payoff, and top comment discussion.
- Output `topic_direction`, `story_archetype`, `hook_type`, `payoff_type`, `comment_trigger`, `audience_need`, `replication_angle`, `risk_note`, and `next_iteration_hypothesis`.
- Explain every strategy change with `observed_signal`, `strategy_change`, `expected_effect`, and `review_after`.

See `references/multidimensional-analysis-strategy.md` for the strategy rationale and labels. The point is to make future Skill evolution inspectable rather than implicit.

### 7. Decide VL Scope

Choose the smallest image-understanding scope that answers the research question.

Use `preview_vl` when only judging whether a sample is worth deeper extraction:

- First-image hook: pass only the first page, or the first 2 pages if the hook spans pages.
- Ending / payoff: pass only the final page, or the final 2 pages if the reversal needs context.
- Ending evidence check: explicitly label whether the final page is an illustration, real-world photo, screenshot, document, chat record, or proof-like image.
- Real-photo ending check: mark `last_page_real_photo=true` when the final page appears to show a real person, real place, or real object photo. Many true-story/adapted-story works use this as authenticity evidence, so also record privacy and likeness risk.
- Middle turn: pass only the relevant local page window.
- Record the original page numbers because the VL output will number pages relative to the selected input set.
- Do not call this a full story document.

Use `full_story_document` only after the sample is promoted to a real candidate:

- The candidate is A/B and likely to drive an experiment or task creation.
- The whole page order matters to understand the story.
- You need complete OCR, dialogue, narration, panel layout, and visual description.
- You plan to convert the extraction into DoodleStory panels.

Avoid full extraction for low-confidence samples. The first pass should protect attention, model cost, and review time.

### 8. Reuse Existing DoodleStory VL

DoodleStory already has a VL path for Douyin image-text extraction:

- `backend/app/services/media_text_extraction.py`
  - `extract_ordered_gallery_comic_content(images)` receives ordered `ImageExtractionReference` entries.
  - It submits `image_url.url` entries to the configured `siliconflow_vision_model`.
  - It rejects non-public image URLs and images beyond `MAX_CONTENT_EXTRACTION_IMAGES`.
- `backend/app/api/content_extractions.py`
  - `apply_content_text_extraction(content, db)` loads ordered image media, requires each asset to have public HTTP(S) `public_url`, and writes the VL result to `content.extracted_text`.
- `backend/app/services/llm.py`
  - `parse_extracted_storyboard(...)` converts full extracted text into structured DoodleStory panels when creating a task from extracted content.

For `preview_vl`, pass only the selected ordered images to the same low-level VL pattern. Keep the result as research evidence.

For `full_story_document`, run the full content-extraction path on all ordered gallery images. Only after that should the result be treated as the source story document and optionally converted into panels through `parse_extracted_storyboard`.

Do not add a second VL implementation unless the existing path cannot satisfy a stated requirement. If a sample only has local files and no public asset URL, the current DoodleStory VL path requires uploading/registering those images as assets first; do not silently fall back to base64 or Codex screenshots.

### 9. Codex Manual Inspection

Use Codex for manual or low-volume understanding:

- Inspect several downloaded images with `view_image`.
- Describe story structure, first-image hook, ending payoff, visual style, panel order, and whether the work can be recreated.
- Use Codex for qualitative judgment and sample-library notes.

Codex is for exploration, review, and deciding the next action. When the workflow needs OCR, page-by-page extraction, or story-document creation, use the existing DoodleStory VL path above.

## Output

Return a concise research report:

1. Keywords and hot-board terms checked.
2. Freshness window used.
3. Candidate table with aweme ID, title, author, date, metrics, media type, tags, and source path.
4. A/B/C/D classification:
   - A: recent, high engagement, image-text, directly experimentable.
   - B: strong structure, needs adaptation.
   - C: useful reference only.
   - D: reject due to age, rights risk, weak structure, or non-image-text dependency.
5. Category comparison across the whole 7-day search result set.
6. Account mimicability and account-probe priority.
7. Account-level judgment: `stable_template`, `viral_outlier`, `emerging_series`, or `mixed_account` when creator evidence has been collected.
8. Comment-cluster summary: high-like/high-reply discussion, topic seeds, and the comment trigger that most likely explains sharing or debate.
9. Opening/ending VL summary, including whether the last page is a real-photo or evidence-style ending.
10. Realistic-scene replication route when the sample uses a real-photo or evidence-style ending.
11. Copy-comment synthesis fields and next iteration hypothesis.
12. Next download, comment, account, or VL-inspection actions, explicitly marked as `preview_vl` or `full_story_document`.
