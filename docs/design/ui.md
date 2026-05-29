# UI Design

## Navigation

DoodleStory starts as an operational creative tool, not a marketing site. The first screen should be the task workspace.

Primary navigation:

- Tasks
- Styles
- Image Models
- Settings

Secondary global controls:

- Display mode: `System`, `Light`, `Dark`
- Provider health/status area when real providers exist

## Information Architecture

### Tasks

Tasks are the main user workflow.

Screens:

- Task list
- Create task
- Task detail
- Image preview dialog
- Batch download confirmation/progress dialog

### Styles

Styles are reusable generation presets.

Screens:

- Style list
- Create style
- Style detail
- Edit style
- Style test panel
- Delete style confirmation

### Image Models

Image models are controlled configuration records used by styles.

Screens:

- Model list
- Create model
- Edit model
- Model detail
- Disable model confirmation

Model records should be manageable before real provider integration exists, but they must not return mock generation results.

## Task List

Purpose: find previous generation tasks, inspect state, and start a new task.

Layout:

- Page title: `Tasks`
- Primary action: `Create task`
- Search input: task title or story excerpt
- Filters: status, style, created date
- Sort: newest first by default
- Table columns:
  - Task title or story excerpt
  - Style
  - Status
  - Progress
  - Image count
  - Created time
  - Updated time

States:

- Loading: table skeleton with stable row height.
- Empty: explain that no tasks exist and offer `Create task`.
- No results: explain that filters matched nothing and offer `Clear filters`.
- Error: show retry and preserve current filters.

Behavior:

- Server-backed pagination with bounded page size.
- Clicking the task title opens task detail.
- Returning from detail preserves filters, pagination, and scroll position.
- Row actions are always reachable by keyboard and touch.

## Create Task

Container: full page or wide drawer. Use full page if the text input and style chooser need more room.

Fields:

- Original text: required multiline textarea.
- Image count mode: segmented control with `Auto` and `Fixed`.
- Fixed image count: numeric input shown only when `Fixed` is selected.
- Style: searchable selector with style cards showing thumbnail, name, model, and short description.

Rules:

- Do not alter the original text in the form.
- Required validation runs before submit and again on submit.
- `Create task` is disabled until original text and style are valid.
- If `Fixed` is selected, count must be a positive integer within the configured product limit.
- On failure, keep all input and focus the first actionable error.
- On success, navigate to the new task detail page.

Primary action: `Create task`

Secondary action: `Cancel`

## Task Detail

Purpose: watch generation, inspect intermediate outputs, review images, and download results.

Header:

- Task title or generated display name from story excerpt.
- Status badge.
- Style name and linked model.
- Created and updated time.
- Primary action by state:
  - `Start generation` when created but not queued.
  - `Cancel generation` when queued, running, or retrying.
  - `Download images` when at least one generated image exists.
  - `Retry failed step` only when a retryable failed state exists.

Main regions:

- Original text: exact submitted text, read-only.
- Generation progress: current step, progress count, started time, latest user-safe error.
- Panels: ordered list with panel number, original panel text, generated prompt, status, and image result.
- Images: grid of generated images with panel number, status, and preview action.
- Activity trail: step-level events from workflow state.

States:

- Queued: show waiting state and allow cancellation.
- Segmenting: show LLM segmentation step.
- Prompting: show prompt generation step.
- Generating images: show per-panel progress.
- Succeeded: show all images and download action.
- Partial succeeded: show successful images, failed panels, and retry action where valid.
- Failed: show user-safe error and retry eligibility.
- Cancel requested: show that cancellation is pending.
- Cancelled: show preserved completed outputs and no automatic retry.

Behavior:

- Auto-refresh while task is active, with visible refresh state.
- Do not hide failed panels.
- Do not overwrite the original story text with panel text or generated prompts.
- Generated prompts are visible for debugging and future edit/retry decisions, but editing prompts is not part of the first design.

## Image Preview Dialog

Triggered by selecting an image.

Required behavior:

- Dialog traps focus and restores focus to the triggering image when closed.
- Large image preview with panel number and prompt summary.
- Actions: `Download image`, `Open original`, `Close`.
- Keyboard: `Escape` closes; arrow keys move to previous/next image when multiple images exist.
- The preview chrome must not distort or recolor generated images.

## Batch Download

Preferred behavior:

- One `Download images` action creates a compressed archive containing all available generated images.
- Archive naming: `doodlestory-task-{task_id}.zip`.
- File naming inside archive: `panel-{panel_order}-{image_id}.{ext}`.

Interaction:

- If archive preparation is immediate, start the download directly.
- If archive preparation is asynchronous, create a download workflow with visible progress.
- If no images exist, disable `Download images` with an explanation.
- If some panels failed, the action label remains `Download images`, and the confirmation states how many images will be included.

## Style List

Purpose: manage reusable visual styles.

Layout:

- Page title: `Styles`
- Primary action: `Create style`
- Search: name and description
- Filters: model, status
- Sort: updated newest by default
- Cards or table:
  - Reference thumbnail
  - Name
  - Bound model
  - Status
  - Last tested time
  - Updated time

Cards are acceptable here because styles have visual reference images.

States:

- Loading, empty, no results, and error states are required.
- Server-backed pagination is required when styles can grow beyond a small fixed set.

## Create And Edit Style

Fields:

- Name: required.
- Description: optional.
- Status: draft or active.
- Bound image model: required.
- Style prompt: required multiline textarea.
- Reference images: optional multiple upload.

Rules:

- Style prompt is saved as authored.
- Bound model is explicit and visible near the style prompt.
- Removing a reference image requires confirmation if the image is already used by a saved style.
- Deleting a style requires confirmation and must be blocked if active tasks still reference it, unless a later product decision defines archival behavior.

Primary actions:

- `Create style`
- `Save style`

Secondary actions:

- `Cancel`
- `Test style`

## Style Detail And Test Panel

Style detail shows:

- Name, status, bound model, description.
- Reference image gallery.
- Style prompt.
- Recent style tests.
- Linked tasks using the style.

Style test panel:

- Test text: required textarea.
- Read-only composed prompt preview:
  - Test text
  - Style prompt
  - Bound model
- Primary action: `Generate test image`
- Result area: latest test image, status, error, and timestamps.

Rules:

- Testing uses the style's bound model only.
- Testing must not silently switch models.
- Failure shows the provider or validation error in user-safe language and stores internal details separately.

## Image Model Management

Model fields:

- Display name.
- Provider key.
- Model key.
- Status: active or disabled.
- Default parameters as structured configuration.
- Notes.

Rules:

- Disabled models cannot be selected for new styles.
- Existing styles bound to a disabled model show a warning.
- Deleting a model is blocked when styles reference it. Prefer disabling over deletion.

## Accessibility And Theme

- All forms use labels, help text, and visible focus states.
- Dialogs follow accessible focus management.
- Icon-only actions need accessible names and tooltips.
- Status is communicated with text plus color or icon, never color alone.
- Support `System`, `Light`, and `Dark` display modes when frontend implementation starts.
- Generated images are never theme-inverted.
