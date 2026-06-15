---
name: douyin-hot-sample-research
description: Use when building or updating a Douyin image-text hot sample library for DoodleStory content experiments. Trigger when the user asks to research recent Douyin hot samples, search keywords or hot boards with douyin-downloader, filter image-text/gallery posts by freshness and engagement, download selected works, inspect comments/basic metrics, or decide whether downloaded images should be understood by Codex or a VL model.
---

# Douyin Hot Sample Research

## Purpose

Use `douyin-downloader` as the collection base for DoodleStory's hot sample library. The first step is always research: collect recent search/hot-board evidence, filter candidate image-text works, then download only selected samples for deeper understanding.

This skill does not promise traffic or automate platform scraping beyond the local downloader's visible capabilities. Keep the workflow evidence-first and small enough to review.

## Read First

1. `/Users/pengfei.shi/workspace/tmp-project/douyin-downloader/README.zh-CN.md`
2. `/Users/pengfei.shi/workspace/tmp-project/douyin-downloader/core/discovery.py`
3. `/Users/pengfei.shi/workspace/tmp-project/douyin-downloader/core/api_client.py`
4. `/Users/pengfei.shi/workspace/tmp-project/douyin-downloader/core/comments_collector.py`
5. `references/research-fields.md`

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

### 5. Image Understanding

Use Codex for manual or low-volume understanding:

- Inspect several downloaded images with `view_image`.
- Describe story structure, first-image hook, visual style, panel order, and whether the work can be recreated.
- Use Codex for qualitative judgment and sample-library notes.

Use a dedicated VL model when the process becomes recurring or batch-oriented:

- More than roughly 10 works or 100 images per research cycle.
- Need stable JSON fields per page.
- Need scheduled runs without the user watching.
- Need reproducible OCR / image-text extraction inside DoodleStory.

Do not pretend Codex manual image inspection is a production data pipeline. It is good for exploration and review; a VL model is the right runtime component for repeated extraction.

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
5. Next download or VL-inspection actions.
