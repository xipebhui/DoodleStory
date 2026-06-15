# Multidimensional Analysis Strategy

This document defines the analysis layer after basic Douyin sample collection. The goal is not only to find a hot work, but to understand whether the account, story structure, comment discussion, and visual evidence can support the next DoodleStory content experiment.

## Stage Boundary

`basic_data_acquisition` covers:

- keyword or hot-board search
- freshness filtering
- image-text candidate detection
- basic metrics collection
- selected work download
- optional first batch comment/detail collection

`multidimensional_analysis` starts after at least one candidate has enough basic data to justify deeper review.

## Account Homepage Analysis

Analyze the creator behind an A or strong B sample before treating the work as a repeatable direction.

Why it matters:

- A single viral work may be accidental; a stable account pattern is stronger evidence.
- Homepage works show whether the creator has a repeatable topic formula, visual system, and posting rhythm.
- Traffic stability protects the experiment from copying an outlier that cannot be reproduced.

Evidence to collect:

- Creator identity: nickname, `sec_uid`, profile URL, bio, follower count, total favorited/interactions, total works count.
- Recent works: at least the latest 20 works when accessible; prefer 30-50 if the account posts frequently and the crawler can collect it cleanly.
- Work shape: image-text ratio, video ratio, story-topic ratio, average image count if available.
- Traffic distribution: median, p75, p90, max, coefficient of variation, and max-to-median ratio for likes, comments, collects, and shares.
- Topic concentration: whether recent titles/tags repeatedly use the same story archetype, relationship tension, suspense setup, or emotional payoff.
- Mimicability: whether the account has few works but unusually high traffic, which often makes the format more useful for early imitation than a large mature account.

Classification:

- `stable_template`: many recent works use similar structure and traffic stays above the account median.
- `viral_outlier`: one or two works dominate traffic while the rest are weak.
- `emerging_series`: recent works improve around the same topic or tag.
- `mixed_account`: account has scattered topics; sample can be used, but account-level confidence is low.

Strategy impact:

- `stable_template` increases replication priority and can raise the sample grade.
- `viral_outlier` should keep the work as a structure reference unless comments and VL evidence show a clear reusable mechanism.
- `emerging_series` suggests testing adjacent keywords and topic variants quickly.
- `mixed_account` should not drive keyword expansion by itself.
- `few_works_high_traffic` should move the account higher in the probe queue because the mechanism may be simpler to isolate.

## Comment Analysis

The comment section is a topic-direction signal, not just a sentiment source. For story image-text content, comments often reveal the actual reason users stayed, shared, argued, asked for a sequel, or projected their own experience onto the story.

Why it matters:

- High-like comments show the consensus interpretation or strongest emotional punch.
- High-reply comments show discussion triggers and conflict.
- User-added stories can become the next topic seed.
- Confusion, skepticism, and requests for context reveal what the next version must clarify or amplify.

Evidence to collect:

- Top comments by like count.
- Top comments by reply count.
- Author pinned comments when available.
- Repeated phrases, questions, debates, requests for follow-up, and personal-story additions.
- Comment-to-like and share-to-like context from the work metrics.

Comment cluster labels:

- `emotional_resonance`: users say it made them cry, angry, relieved, regretful, or healed.
- `identity_projection`: users map the story to themselves, parents, partners, friends, children, school, work, or marriage.
- `moral_judgment`: users argue who is right, wrong, selfish, kind, cruel, brave, or naive.
- `plot_question`: users ask what happened before, after, or why a character made a choice.
- `request_followup`: users ask for a sequel, ending, explanation, or full story.
- `real_story_probe`: users ask whether it is true, adapted from reality, or who the real person is.
- `topic_seed`: users contribute another story, case, phrase, or scenario that can become a new selection direction.
- `format_feedback`: users comment on drawing style, narration rhythm, image order, or readability.

Strategy impact:

- `topic_seed` and `request_followup` should feed the next keyword and title-structure queue.
- `moral_judgment` suggests stronger conflict framing.
- `plot_question` suggests the work's open loop may be the main engine; future versions should preserve or sharpen that loop.
- `real_story_probe` pairs with ending VL checks; if the final image looks like a real person/photo/evidence, rights and privacy risk must be reviewed.

## VL Opening And Ending Inspection

Use the existing DoodleStory VL path. The first pass should be small: inspect the first 1-2 pages and the last 1-2 pages before full extraction.

Opening inspection asks:

- What stops the scroll on page 1?
- Is the hook a sentence, visual contradiction, relationship tension, danger, mystery, confession, or promise of reversal?
- Does page 2 deepen the hook or merely continue exposition?

Ending inspection asks:

- Does the final page close the story, reverse the interpretation, ask for follow-up, or show proof?
- Is the final page an illustration, a real-world photo, a screenshot, a document, a chat record, a news-like image, or another evidence form?
- If it is a real person/photo/evidence ending, does the work imply true-story adaptation?

Ending labels:

- `illustrated_resolution`: drawn ending, no obvious real-world evidence.
- `illustrated_open_loop`: drawn ending that asks for continuation or leaves a strong unresolved question.
- `real_photo_ending`: final page appears to be a real person/place/object photo.
- `screenshot_or_document_ending`: final page looks like chat, note, document, news screenshot, or case evidence.
- `mixed_evidence_ending`: drawn story plus a final real-world proof-like image.

Strategy impact:

- Real-photo or evidence endings can strengthen authenticity and discussion, but they increase privacy, likeness, and rights risk.
- If the hook is weak but comments are strong, the discussion may come from the topic rather than the execution.
- If the hook and ending are both strong, promote the sample for full extraction.

## Realistic Ending As A Replication Mechanism

When the final page is a real photo, screenshot, document, chat record, or proof-like image, treat it as a format mechanism rather than only a risk.

Strategy:

- Keep the emotional function: proof, after-story, relationship confirmation, real-life trace, or topic evidence.
- Do not copy the original real person, private screenshot, document, or unlicensed image.
- Use original photography, authorized material, anonymized composites, or image-2 realistic-scene generation to recreate the same function.
- Record the generated-realness plan in `realistic_replication_angle` and `image2_real_scene_prompt_seed`.

For hot story samples, the question is not "can we reuse this real image"; it is "what original real-feeling image would create the same trust or discussion effect."

## Copy And Comment Synthesis

Do not analyze title/copy and comments separately at the final decision point. A useful sample should produce a joined interpretation:

- What the creator promised in the title or first page.
- What the story actually delivered.
- What users chose to discuss.
- Which discussion points can become the next DoodleStory topic or format test.

Recommended synthesis fields:

- `topic_direction`: the next content direction implied by the sample.
- `story_archetype`: revenge, regret, family debt, school memory, marriage test, hidden kindness, sacrifice, secret identity, moral dilemma, etc.
- `hook_type`: confession, question, impossible choice, betrayal, deadline, evidence, contrast, warning, or outcome-first.
- `payoff_type`: reversal, tear point, justice, regret, reconciliation, open loop, truth reveal, or proof reveal.
- `comment_trigger`: the comment cluster that best explains why users talked.
- `audience_need`: what users want more of: emotional release, judgment, realism, continuation, explanation, identity projection, or practical advice.
- `replication_angle`: how to create an original work from the mechanism without copying the source story.
- `risk_note`: copyright, likeness, privacy, medical/legal/violent sensitivity, platform policy, or weak evidence.
- `next_iteration_hypothesis`: a testable statement for the next publishing or collection round.

## Skill Evolution Rules

The Skill should optimize direction with explicit evidence, not intuition alone.

Use accumulated analysis to update:

- Keyword expansion: add terms that repeatedly appear in high-signal titles, comments, and topic seeds.
- Scoring weights: raise the weight of comment clusters that correlate with shares, collects, or stable account traffic.
- Rejection reasons: record why a tempting sample should not be copied, such as old data, one-off account traffic, non-image-text dependency, or real-photo rights risk.
- VL scope: if many samples in a niche rely on final-page evidence, ending inspection becomes mandatory for that niche.
- Topic buckets: merge or split story archetypes based on real comment behavior.

Every evolution should state:

- `observed_signal`: what repeated evidence was seen.
- `strategy_change`: what the Skill will do differently next time.
- `expected_effect`: what improvement the change should produce.
- `review_after`: how many new samples or publishing rounds should pass before evaluating the change.
