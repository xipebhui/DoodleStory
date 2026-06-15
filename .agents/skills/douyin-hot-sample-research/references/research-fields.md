# Research Fields

Use these fields when building a DoodleStory Douyin hot sample library.

## Candidate Identity

- `keyword`: search keyword or hot-board term.
- `aweme_id`: stable work ID.
- `source_url`: share/video/note URL when available.
- `search_source`: `browser_search`, `downloader_search`, `hot_board`, or `download_metadata`.
- `search_response_path`: raw response JSON or JSONL path used as evidence.
- `author_name`: author nickname.
- `author_sec_uid`: author `sec_uid` when available.
- `title`: first sentence or pre-hashtag part of `desc`.
- `description`: full `desc`.
- `tags`: hashtags from `text_extra`, manifest, or description.

## Freshness

- `create_time`: Unix timestamp from `*_data.json` or search result.
- `publish_date`: local date derived from `create_time`.
- `freshness_class`: `7d`, `30d`, `90d`, or `old-reference`.

## Media Shape

- `media_type`: gallery, video, note, or unknown.
- `aweme_type`: raw Douyin work type when available.
- `image_count`: number of downloaded gallery images or `images` entries.
- `has_local_media`: whether media files exist on disk.
- `has_metadata_json`: whether `*_data.json` exists.
- `has_comments_json`: whether `*_comments.json` exists.

## Engagement

Prefer raw counts. Do not invent metrics when fields are absent.

- `digg_count`: likes.
- `comment_count`: comment count from statistics.
- `collect_count`: favorites/collects.
- `share_count`: shares.
- `recommend_count`: visible recommendation count if present.
- `play_count`: often zero or absent for gallery; do not overinterpret.

## Browser-State Search Evidence

Use these fields when results come from `scripts/browser_search_collect.py`:

- `browser_storage_state`: path to the `storage_state` file used for the run. Do not copy cookie values into notes.
- `browser_search_url`: Douyin search page opened by the script.
- `browser_final_url`: final URL after UI search or direct URL load.
- `browser_entry_mode`: `ui` or `url`.
- `network_response_count`: number of captured `/aweme/v1/web/general/search/single/` responses.
- `all_aweme_path`: JSONL path for every parsed work.
- `gallery_jsonl_path`: JSONL path after image-text/gallery filtering.
- `browser_search_meta_path`: meta JSON path.
- `search_blocker`: explicit blocker if no network response or no aweme candidates were parsed.

## Qualitative Review

Fill these after manual Codex inspection or VL extraction:

- `first_image_hook`: what makes the first page stop-scroll.
- `ending_payoff`: whether the last page closes, reverses, or opens the story.
- `story_structure`: setup, conflict, turn, resolution, open loop.
- `visual_style`: layout and drawing style.
- `comment_signal`: praise,催更, debate, question, confusion, or conversion intent.
- `replication_difficulty`: low, medium, high.
- `rights_risk`: low, medium, high.
- `experiment_fit`: A, B, C, D.

## VL Scope

Use these fields to avoid confusing lightweight inspection with full story extraction:

- `vl_scope`: `none`, `preview_vl`, or `full_story_document`.
- `vl_input_orders`: original image order numbers sent to VL, such as `[1]`, `[1,2]`, `[14,15]`, or `all`.
- `vl_result_type`: `hook_judgment`, `ending_judgment`, `turning_point_judgment`, or `story_document`.
- `should_full_extract`: whether the sample deserves all-page extraction.
- `content_extraction_id`: DoodleStory content extraction ID when full extraction is run through the product path.
- `extracted_text_source`: path or DB source of the VL result.

`preview_vl` is research evidence only. `full_story_document` is the point where the result can become DoodleStory source material for panel creation.

## Notes

- Treat old high-engagement samples as structural references unless the same structure appears in recent search results.
- Prefer image-text/gallery works that can be recreated with original text and original generated images.
- Keep raw downloader paths in the table so later agents can re-open evidence.
- Keep browser search raw response paths in the table when the candidate came from page network listening.
- Reuse DoodleStory's existing content-extraction VL path. It requires ordered images with public HTTP(S) asset URLs; do not replace that with an implicit base64 or Codex-only path.
