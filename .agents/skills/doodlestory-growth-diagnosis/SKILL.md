---
name: "doodlestory-growth-diagnosis"
description: "Use the dbs-diagnosis business checkup frame to diagnose DoodleStory growth, content-iteration experiments, pricing, and Xiaohongshu/Douyin validation work."
---

# DoodleStory Growth Diagnosis

## Purpose

Use this skill when discussing DoodleStory as a business, not only as an image generation app. The current product direction is an AI-assisted Douyin image-text content iteration system: generate content, publish, collect data, review results, and decide the next topic direction.

This skill is project-local on purpose. It should read repository context first, so strategy work can continue across sessions without relying on chat memory.

## Read First

1. `docs/strategy/doodle-growth-diagnosis.md`
2. `docs/product/content-iteration-system.md`
3. `docs/experiments/content-iteration-cycle-template.md`
4. `docs/growth/xiaohongshu/content-strategy.md`
5. `docs/spec.md`
6. `docs/progress.md`

## Diagnosis Frame

Use the dbs-diagnosis checkup frame, but anchor every judgment in current DoodleStory evidence.

1. Printing-machine check: what are the inputs and outputs, and can another user get similar outputs from the same inputs?
2. Ethics check: are we selling efficiency and experiments, or implying guaranteed traffic and revenue?
3. Pricing check: are we pricing compute, a workspace, or an experiment cycle?
4. Demand check: does the user need images, or a lower-cost way to test content directions?
5. Traffic-to-monetization check: where are acquisition, education, payment, delivery, and result attribution?
6. Scalability check: which judgment fields have been externalized from the operator's head?
7. Growth-level check: which level is proven now, and what is the next level task?

## Current Working Thesis

DoodleStory should not be positioned as a generic AI image-text generator. The current business thesis is:

> Use AI to reduce the cost of Douyin image-text content experiments, use publication data to decide the next topic, and gradually turn repeated review fields into a productized content-iteration system.

## Operating Rules

- Do not recommend more feature development unless it supports a paid experiment, data return, or next-topic decision.
- Do not claim guaranteed traffic, viral results, or monetization.
- Do not treat free users as validation for willingness to pay.
- Prefer a 14-day or 30-day experiment package over pure self-serve SaaS in the early stage.
- Keep human review in the topic-decision loop until repeated experiment data proves the rule stable.
- Record every important strategic decision in repository docs, not only in chat.

## Output Formats

For a diagnosis, output:

1. Current level: one sentence.
2. Main bottleneck: one sentence.
3. Evidence: short bullets from docs or current user-provided data.
4. Recommendation: the next paid or data-generating action.
5. Repository update target: which doc should be updated if the conclusion changes.

For a cycle review, output:

1. What was tested.
2. What happened.
3. What can be explained.
4. What cannot be explained yet.
5. Next topics to publish.
6. Why these topics were chosen.
7. Stop conditions.

## Boundaries

This skill does not replace product implementation contracts. If the next step requires code changes, write or update a sprint contract before implementation.

This skill does not introduce fallback strategies, mocks, or silent error handling. If a required data source is missing, state the blocker and ask whether to continue with a narrower analysis.
