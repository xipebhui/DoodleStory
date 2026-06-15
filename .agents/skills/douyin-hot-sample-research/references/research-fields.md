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

## Seven-Day Search Processing

Fill these when comparing all results from a recent 7-day search run.

- `content_category`: `pure_love_healing`, `family_marriage`, `social_safety`, `suspense_horror`, `revenge_moral`, `workplace_social`, `life_growth`, `other_story`, or `uncategorized`.
- `category_candidate_count`: number of candidates in the category.
- `category_ab_count`: number of A/B candidates in the category.
- `category_total_likes`: total likes in the category.
- `category_total_comments`: total comments in the category.
- `category_total_shares`: total shares in the category.
- `category_avg_score`: average candidate score in the category.
- `category_top_aweme_ids`: representative high-signal works in the category.
- `account_probe_priority`: high, medium, low, or no_sec_uid.
- `mimicability_label`: `high_mimicability`, `medium_mimicability`, `low_mimicability`, or `needs_account_probe`.
- `mimicability_reason`: short reason such as `few_works_high_traffic`, `mid_work_count_high_traffic`, `large_mature_account`, or `creator_profile_not_provided`.
- `realistic_scene_role`: proof, after-story, contrast, identity evidence, relationship confirmation, or topic proof.
- `image2_real_scene_prompt_seed`: short prompt seed for generating a safe original realistic scene.
- `real_scene_rights_policy`: original_generated, authorized, anonymized, or reject.

Use category comparison before choosing individual works. Use account mimicability to decide which creators deserve homepage analysis.

## Account Homepage Analysis

Fill these only after a candidate is promoted for account-level review.

- `creator_profile_url`: Douyin account profile URL when available.
- `creator_bio`: visible author bio or signature.
- `creator_fans`: follower count from profile data.
- `creator_total_favorited`: total favorited/interactions from profile data.
- `creator_aweme_count`: works count from profile data.
- `creator_recent_work_count`: number of recent works collected for analysis.
- `creator_recent_image_text_count`: number of recent works that are image-text/gallery.
- `creator_recent_story_count`: number of recent works that appear to use story content.
- `creator_posting_cadence`: rough recent posting rhythm.
- `traffic_median`: median engagement count for the chosen metric, usually likes.
- `traffic_p75`: p75 engagement count.
- `traffic_p90`: p90 engagement count.
- `traffic_max`: maximum engagement count in the recent works window.
- `traffic_cv`: coefficient of variation for the chosen metric.
- `viral_outlier_ratio`: max engagement divided by median engagement.
- `topic_concentration`: low, medium, or high concentration around one topic/formula.
- `traffic_stability`: `stable_template`, `viral_outlier`, `emerging_series`, or `mixed_account`.
- `account_analysis_note`: concise explanation for the stability classification.

Account stability explains whether a sample is likely a repeatable formula or only a one-off hit.
For DoodleStory experiments, fewer works plus high traffic is a stronger mimicability signal than account size alone.

## Comment Analysis

Fill these after collecting comments for promoted samples.

- `comments_collected_count`: number of comments actually collected.
- `top_like_comments`: representative high-like comments with like and reply counts.
- `top_reply_comments`: representative high-reply comments with like and reply counts.
- `pinned_author_comment`: author pinned comment if available.
- `comment_clusters`: labels such as `emotional_resonance`, `identity_projection`, `moral_judgment`, `plot_question`, `request_followup`, `real_story_probe`, `topic_seed`, or `format_feedback`.
- `comment_trigger_type`: the cluster that best explains why users discussed the work.
- `audience_question`: repeated question users ask.
- `audience_disagreement`: repeated debate or moral conflict.
- `audience_added_story`: user-supplied story or scenario that can become a new topic seed.
- `topic_seeds_from_comments`: candidate next keywords or scenarios derived from comments.
- `comment_analysis_note`: concise explanation of what the comment section changes in the research decision.

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
- `first_page_hook_type`: confession, question, impossible choice, betrayal, deadline, evidence, contrast, warning, outcome-first, or other.
- `ending_payoff`: whether the last page closes, reverses, or opens the story.
- `ending_type`: `illustrated_resolution`, `illustrated_open_loop`, `real_photo_ending`, `screenshot_or_document_ending`, or `mixed_evidence_ending`.
- `last_page_real_photo`: whether the final page appears to be a real person/place/object photo.
- `last_page_evidence_type`: none, real photo, screenshot, chat record, document, news-like image, receipt, or other proof-like image.
- `story_structure`: setup, conflict, turn, resolution, open loop.
- `visual_style`: layout and drawing style.
- `comment_signal`: praise,催更, debate, question, confusion, or conversion intent.
- `replication_difficulty`: low, medium, high.
- `rights_risk`: low, medium, high.
- `privacy_or_likeness_risk`: low, medium, high, or unknown.
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

## Copy And Comment Synthesis

Fill these after combining work copy, story structure, comment clusters, and optional VL evidence.

- `topic_direction`: the next content direction implied by the sample.
- `story_archetype`: reusable story category, such as family debt, regret, hidden kindness, marriage test, school memory, revenge, sacrifice, secret identity, or moral dilemma.
- `hook_type`: the opening mechanism that stopped users.
- `payoff_type`: reversal, tear point, justice, regret, reconciliation, open loop, truth reveal, or proof reveal.
- `comment_trigger`: the comment cluster that best explains discussion.
- `audience_need`: emotional release, moral judgment, realism, continuation, explanation, identity projection, practical advice, or other.
- `replication_angle`: how to create an original work using the mechanism without copying the source story.
- `realistic_replication_angle`: how to recreate real-photo/evidence feeling with original or generated assets.
- `risk_note`: copyright, likeness, privacy, medical/legal/violent sensitivity, platform policy, weak evidence, or other risk.
- `next_iteration_hypothesis`: testable statement for the next collection or publishing round.
- `observed_signal`: repeated evidence that motivates a strategy change.
- `strategy_change`: what the Skill should do differently next time.
- `expected_effect`: expected improvement from the change.
- `review_after`: number of samples or publishing rounds before evaluating the strategy change.

## Notes

- Treat old high-engagement samples as structural references unless the same structure appears in recent search results.
- Prefer image-text/gallery works that can be recreated with original text and original generated images.
- Keep raw downloader paths in the table so later agents can re-open evidence.
- Keep browser search raw response paths in the table when the candidate came from page network listening.
- Reuse DoodleStory's existing content-extraction VL path. It requires ordered images with public HTTP(S) asset URLs; do not replace that with an implicit base64 or Codex-only path.
- Treat comment analysis as a topic-direction signal. A high-like comment can explain why users share, but it should be interpreted with the title, story payoff, account stability, and VL ending evidence.
