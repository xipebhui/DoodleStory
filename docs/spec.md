# Product Spec

## Product Summary

`DoodleStory` is a text-to-image story generation product. A user provides original text, selects a generation style, and receives one or more generated images that correspond to semantically segmented panels from the story.

The product must preserve the user's original text. LLM calls may segment the text and create image-generation prompts, but they must not rewrite the user's source story.

## Users

- Creators who want to turn short story text into a sequence of images.
- Operators or maintainers who tune reusable image styles and bind them to image-generation models.

## Core Concepts

- Style: a reusable image style with reference images, metadata, a style prompt, and a bound image model.
- Style test: a generation test that combines custom test text with a style prompt and sends it to the style's bound model.
- Task: a user-facing text-to-image generation request.
- Panel: a semantic segment produced from the user's original story. A panel contains the original segment text and later receives an image-generation prompt.
- Generated image: an image output for one panel within a task.

## Core User Journeys

1. Manage styles.
   - Create, read, update, and delete styles.
   - Attach reference images and style metadata.
   - Configure the style prompt.
   - Bind the style to a specific image-generation model.

2. Test a style.
   - Select a style.
   - Enter test text.
   - Combine the test text with the style prompt.
   - Generate a test image with the style's bound model.
   - Use the result to refine the style prompt or model binding.

3. Create a generation task.
   - Enter original text.
   - Choose automatic image count or a fixed image count.
   - Select a style.
   - Submit the task.

4. Generate images for a task.
   - Call an LLM with a segmentation system prompt.
   - If the user selected a fixed image count, split the story into that number of semantic panels.
   - If no fixed count was selected, split by semantic boundaries, roughly around ten Chinese characters per panel as a starting heuristic.
   - Call an LLM again with the original story, selected style, and panel text to produce image prompts.
   - The generated image prompt should describe subject, action, scene state, and static visual content without contradicting the style prompt.
   - The prompt-generation system message must emphasize that the selected style must be followed.
   - Send each panel prompt to the image model bound to the selected style.

5. Review and download results.
   - View generated images in the task detail.
   - Click an image to enlarge it.
   - Download all generated images in one action, preferably as a folder-like batch when supported, otherwise as a compressed archive.

## Product Priorities

1. Preserve the user's original text exactly.
2. Make style tuning explicit and repeatable through style metadata, prompts, test generation, and model bindings.
3. Keep the task workflow inspectable: original text, panels, generated prompts, model, and images should be traceable.
4. Make failed LLM or image-generation steps visible rather than silently ignored.
5. Keep the Codex harness as the durable project memory for future implementation work.

## Technical Shape

- Frontend: concrete framework not selected yet. Product UI design is documented in `docs/design/ui.md`.
- Backend: concrete framework not selected yet. Initial REST API design is documented in `docs/design/api.md`.
- Storage: relational OLTP database design is documented in `docs/design/database.md`.
- External integrations: LLM provider and image-generation model provider are not selected yet.
- Background workflow: image generation is asynchronous and starts as a small workflow: in-process queue plus database-backed task state.
- Standards: markdown guidance under `docs/standards/` for Python, Java, database design, backend workflows, frontend work, UI interaction, and reusable modules.

## Constraints

- Do not introduce fallback behavior, compatibility layers, mocks, placeholder responses, or silent error handling unless the user explicitly requests it.
- Do not rewrite, summarize, or sanitize the user's submitted source text as part of task creation.
- Do not let panel prompt generation conflict with the selected style prompt.
- Do not bind a style test or task to a model other than the model configured on the selected style, unless the user explicitly changes that style binding.
- Technology choices are still open. Future implementation should select a concrete stack through a sprint contract before writing application code.

## Non-Goals

- Building a generic prompt marketplace.
- Building a general-purpose image model abstraction before concrete providers are selected.
- Adding production-scale workflow infrastructure before the project's actual scale requires it and the user approves it.

## Acceptance Direction

The primary acceptance flow is: define a sprint, implement within that sprint, run verification, record QA, and leave clear progress for the next Codex run.

## Open Questions

- Which frontend and backend stack should DoodleStory use?
- Which LLM provider and image-generation provider should be integrated first?
- What metadata is required for a style beyond name, description, reference images, prompt, status, and model binding?
- Should generated panel prompts be editable before image generation, or only visible for debugging?
- What image formats and naming conventions should batch download use?
