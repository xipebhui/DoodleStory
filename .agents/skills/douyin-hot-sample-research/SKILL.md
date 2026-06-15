---
name: douyin-hot-sample-research
description: Use when building or updating a Douyin image-text hot sample library for DoodleStory content experiments. Trigger when the user asks to research recent Douyin hot samples, search keywords or hot boards with douyin-downloader, filter image-text/gallery posts by freshness and engagement, download selected works, inspect comments/basic metrics, or decide whether to run lightweight first/last-page VL inspection or full DoodleStory story extraction.
---

# Douyin Hot Sample Research

## Purpose

Use `douyin-downloader` as the collection base for DoodleStory's hot sample library. The first step is always research: collect recent search/hot-board evidence, filter candidate image-text works, then download only selected samples for deeper understanding.

Downloaded image understanding should reuse DoodleStory's existing content-extraction VL path. Do not treat Codex manual image viewing as the runtime extraction pipeline.

This skill does not promise traffic or automate platform scraping beyond the local downloader's visible capabilities. Keep the workflow evidence-first and small enough to review.

## Read First

1. `/Users/pengfei.shi/workspace/tmp-project/douyin-downloader/README.zh-CN.md`
2. `/Users/pengfei.shi/workspace/tmp-project/douyin-downloader/core/discovery.py`
3. `/Users/pengfei.shi/workspace/tmp-project/douyin-downloader/core/api_client.py`
4. `/Users/pengfei.shi/workspace/tmp-project/douyin-downloader/core/comments_collector.py`
5. `/Users/pengfei.shi/workspace/tmp-project/DoodleStory/backend/app/services/media_text_extraction.py`
6. `/Users/pengfei.shi/workspace/tmp-project/DoodleStory/backend/app/api/content_extractions.py`
7. `/Users/pengfei.shi/workspace/tmp-project/DoodleStory/backend/app/prompts/parse_extracted_storyboard_v1.md`
8. `references/research-fields.md`

## Workflow

### 1. Research First

Start from keywords or hot-board terms. Prefer recent evidence:

- Priority 1: within 7 days.
- Priority 2: within 30 days.
- Priority 3: older samples only as structure references, not first-batch experiment candidates.

Use `douyin-downloader` search and hot-board commands:

```bash
cd /Users/pengfei.shi/workspace/tmp-project/douyin-downloader
.venv/bin/python run.py --hot-board 30 -p ./Downloaded
.venv/bin/python run.py --search "故事" --search-max 100 -p ./Downloaded
```

The CLI currently exposes `--search` and `--search-max`; the lower-level `search_aweme` function also supports `sort_type` and `publish_time`. If freshness is critical, call the Python API directly or add CLI flags in a separate implementation task.

### 2. Filter Candidates

Keep candidates that are likely useful for DoodleStory:

- `aweme_type` / metadata indicates gallery or image-text content.
- `create_time` is recent enough for the requested research window.
- `statistics` shows meaningful engagement: digg, comment, collect, share.
- The description/title has a reusable story structure, not only a one-off meme.
- The visual form can be recreated as original image-text content without relying on copyrighted clips or celebrity/IP footage.

Reject candidates that depend on unauthorized copyrighted material, scraped private data, or platform behavior that cannot be verified from the downloader output.

### 3. Download Selected Works

After filtering search JSONL, download selected `share_url`, `video/note` URL, or `aweme_id` URL with `douyin-downloader`. Turn on JSON metadata and comments when the research needs feedback signals:

```yaml
json: true
comments:
  enabled: true
  include_replies: false
  max_comments: 200
  page_size: 20
```

The downloader writes `*_data.json`, media files, optional `*_comments.json`, and `download_manifest.jsonl`.

### 4. Summarize Local Evidence

Use the bundled summarizer after search or download:

```bash
python .agents/skills/douyin-hot-sample-research/scripts/summarize_samples.py \
  --downloader-root /Users/pengfei.shi/workspace/tmp-project/douyin-downloader \
  --data-root /Users/pengfei.shi/workspace/tmp-project/douyin-import-service/storage \
  --format markdown
```

Use the summary as a starting point. Inspect raw JSON for any sample that will drive a decision.

### 5. Decide VL Scope

Choose the smallest image-understanding scope that answers the research question.

Use `preview_vl` when only judging whether a sample is worth deeper extraction:

- First-image hook: pass only the first page, or the first 2 pages if the hook spans pages.
- Ending / payoff: pass only the final page, or the final 2 pages if the reversal needs context.
- Middle turn: pass only the relevant local page window.
- Record the original page numbers because the VL output will number pages relative to the selected input set.
- Do not call this a full story document.

Use `full_story_document` only after the sample is promoted to a real candidate:

- The candidate is A/B and likely to drive an experiment or task creation.
- The whole page order matters to understand the story.
- You need complete OCR, dialogue, narration, panel layout, and visual description.
- You plan to convert the extraction into DoodleStory panels.

Avoid full extraction for low-confidence samples. The first pass should protect attention, model cost, and review time.

### 6. Reuse Existing DoodleStory VL

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

### 7. Codex Manual Inspection

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
5. Next download or VL-inspection actions, explicitly marked as `preview_vl` or `full_story_document`.
