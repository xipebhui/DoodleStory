# 最近 7 天搜索结果处理

采集完一批最近 7 天抖音搜索结果后，使用这个流程。目标不只是给单个作品排序，而是判断哪些类目、账号和结尾形式值得深挖。

## 目录

- [决策顺序](#decision-order)
- [类目横向对比](#category-comparison)
- [账号模仿度筛选](#account-mimicability-screening)
- [真实感结尾策略](#realistic-ending-strategy)
- [先看热门，再看真实感](#hotness-first-then-realness)

## Decision Order

1. Horizontal category comparison.
2. Account mimicability screening.
3. Work-level comment and VL inspection.
4. Replication route design, including realistic-scene generation.

Do not jump directly from one high-metric work to production. First ask whether its category is hot across the search result, whether the creator pattern is easy to imitate, and whether the visual mechanism can be recreated.

## Category Comparison

Classify every result into a content category before choosing samples:

- `pure_love_healing`: pure love, healing, romance, crush, long-distance love, couple daily life.
- `family_marriage`: parents, marriage, in-laws, spouse, children, family pressure.
- `social_safety`: women safety, harm, silence/refusal-to-stay-silent, bullying, victim protection, public-risk stories.
- `suspense_horror`: suspense, horror, strange story, mystery, case-like content.
- `revenge_moral`: revenge, slap-back, moral judgment, betrayal, punishment, conflict reversal.
- `workplace_social`: workplace, colleague, boss, high-EQ response, social conflict.
- `life_growth`: life reflection, anxiety, growth, study, exam, self-improvement.
- `other_story`: story content that does not fit the buckets above.

For each category, compare:

- candidate count
- A/B candidate count
- total and median likes
- total shares
- total comments
- average score
- representative top works

Decision rule:

- A category with multiple A/B works is stronger than a category with only one extreme outlier.
- A category with high share rate deserves attention even if likes are lower.
- A category that appears across several creators is more useful than one carried by one account only.

## Account Mimicability Screening

After category comparison, pick accounts for homepage probing.

The most interesting accounts are not always the largest accounts. For DoodleStory experiments, a creator with fewer works but high traffic can be more useful because the formula may be simpler, newer, and less dependent on a mature brand. Large follower count, high total interaction, and many historical works should weaken direct mimicability even if the sampled work is hot.

High-priority account signals:

- Few works, high engagement: low `videos_count` or `creator_aweme_count`, but the sampled work has high likes, comments, shares, or collection rate.
- Small or mid-size account, high breakout: follower count is not huge, but recent works break out.
- Repeated format: several recent works use the same category, hook, or ending device.
- Image-text first: account mainly publishes image-text/gallery works, not video formats DoodleStory cannot reuse.

Lower-priority account signals:

- Huge mature account where traffic may come from brand memory rather than format.
- Many scattered topics with no repeated story mechanism.
- The hot work depends on celebrity/IP/copyrighted footage or unrepeatable real-life access.

Collection rule:

- It is acceptable to collect all creator works when the crawler cannot hard-limit pagination.
- The analysis window should still default to the latest 20 works, or another explicitly stated N.
- Record both total collected works and analyzed recent works.
- Treat account size as an explanatory variable, not an automatic advantage.

Use labels:

- `high_mimicability`: fewer works or smaller account plus strong traffic and clear repeatable structure.
- `medium_mimicability`: some repeated structure, but traffic depends partly on account maturity.
- `low_mimicability`: large mature account, scattered topics, or hard-to-copy production access.
- `needs_account_probe`: search result is strong but account profile has not been collected yet.
- `large_mature_account_penalty`: the work is useful as a structure reference, but the account's existing audience makes fast imitation less certain.

## Realistic Ending Strategy

If the last page is a real person photo, real-life scene, screenshot, document, chat record, or evidence-style image, do not treat it only as a risk. Treat it as a format mechanism:

- It increases authenticity.
- It can make users ask whether the story is real.
- It can convert a drawn story into a "this really happened" feeling.
- It often changes comment behavior from passive reading to blessing, debate, identity projection, or story sharing.

Replication rule:

- Do not copy real people, private screenshots, or unlicensed evidence images.
- Extract the function of the ending: proof, confirmation, after-story, real-life trace, or emotional grounding.
- Recreate that function with original assets, authorized materials, or image-2 realistic-scene generation.

Generated realistic-scene options:

- final couple selfie after a pure-love story
- night street candid photo after a reunion story
- phone screenshot recreated with fictional text
- receipt, ticket, letter, exam notice, hospital corridor, classroom, wedding scene, or workplace desk as proof-like objects
- blurred background real-scene style with fictional subjects

Record:

- `realistic_scene_role`: proof, after-story, contrast, identity evidence, relationship confirmation, or topic proof.
- `image2_real_scene_prompt_seed`: short prompt seed for generating a safe original realistic image.
- `real_scene_rights_policy`: original_generated, authorized, anonymized, or reject.

## Hotness First, Then Realness

The priority remains hotness:

1. Which category is getting traffic in the last 7 days?
2. Which works explain that traffic through hook, payoff, comments, or share behavior?
3. Which accounts show a repeatable or easy-to-imitate formula?
4. Which realistic elements can be generated safely to increase authenticity?

Do not start with "what content should I publish." Start with what the market is already rewarding, then design an original version that preserves the mechanism.
