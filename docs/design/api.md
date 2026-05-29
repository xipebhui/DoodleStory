# Backend API Design

## Scope

This API design uses REST resources and JSON payloads. It does not select a concrete web framework.

All dynamic list endpoints must enforce a default `limit` and a maximum `limit`. List responses return summary fields only. Detail endpoints return full object data and bounded child collections.

## Common Rules

Base path:

```text
/api/v1
```

Pagination query parameters:

- `limit`: default `20`, maximum `100`.
- `cursor`: opaque cursor for cursor-paginated lists.
- `sort`: allowed endpoint-specific sort key.
- `direction`: `asc` or `desc`.

List response shape:

```json
{
  "items": [],
  "page": {
    "limit": 20,
    "next_cursor": null,
    "has_more": false
  }
}
```

Error response shape:

```json
{
  "error": {
    "code": "validation_failed",
    "message": "Some fields need attention.",
    "fields": {
      "original_text": "Original text is required."
    },
    "request_id": "req_..."
  }
}
```

Error handling:

- Return user-safe messages in `message`.
- Store internal provider details in database fields or logs, not in public API payloads.
- Do not silently ignore failed provider calls.
- Do not return mock generation results when providers are unavailable.

## Image Models

### List Models

```http
GET /api/v1/image-models?status=active&limit=20&cursor=...
```

Summary item:

```json
{
  "id": "model_...",
  "display_name": "Example Image Model",
  "provider_key": "provider",
  "model_key": "model-name",
  "status": "active",
  "updated_at": "2026-05-29T15:00:00Z"
}
```

### Create Model

```http
POST /api/v1/image-models
```

Request:

```json
{
  "display_name": "Example Image Model",
  "provider_key": "provider",
  "model_key": "model-name",
  "default_parameters": {
    "size": "1024x1024"
  },
  "notes": "Used for story illustration styles."
}
```

Response: `201 Created` with model detail.

### Get Model

```http
GET /api/v1/image-models/{model_id}
```

### Update Model

```http
PATCH /api/v1/image-models/{model_id}
```

### Disable Model

```http
POST /api/v1/image-models/{model_id}/disable
```

Disabling preserves existing references. New styles cannot bind to disabled models.

## Styles

### List Styles

```http
GET /api/v1/styles?query=&status=active&image_model_id=&limit=20&cursor=...
```

Summary item:

```json
{
  "id": "style_...",
  "name": "Watercolor Storybook",
  "description": "Soft illustrated watercolor scenes.",
  "status": "active",
  "image_model": {
    "id": "model_...",
    "display_name": "Example Image Model"
  },
  "thumbnail_asset": {
    "id": "asset_...",
    "url": "/api/v1/assets/asset_.../content"
  },
  "last_tested_at": "2026-05-29T15:00:00Z",
  "updated_at": "2026-05-29T15:00:00Z"
}
```

### Create Style

```http
POST /api/v1/styles
```

Request:

```json
{
  "name": "Watercolor Storybook",
  "description": "Soft illustrated watercolor scenes.",
  "status": "draft",
  "image_model_id": "model_...",
  "style_prompt": "Use soft watercolor textures, gentle outlines, and warm storybook lighting.",
  "reference_asset_ids": ["asset_..."]
}
```

Validation:

- `name`, `image_model_id`, and `style_prompt` are required.
- `image_model_id` must reference an active image model.

### Get Style

```http
GET /api/v1/styles/{style_id}
```

Detail includes full `style_prompt`, reference images, bound model detail, recent tests, and usage summary.

### Update Style

```http
PATCH /api/v1/styles/{style_id}
```

Changing `image_model_id` affects future style tests and future tasks. Existing tasks keep the model snapshot recorded at task creation.

### Delete Style

```http
DELETE /api/v1/styles/{style_id}
```

Deletion is blocked when tasks reference the style. A later archival flow may replace hard deletion if needed.

### Upload Style Reference Image

```http
POST /api/v1/styles/{style_id}/reference-images
Content-Type: multipart/form-data
```

Response includes the created asset and style reference record.

### Remove Style Reference Image

```http
DELETE /api/v1/styles/{style_id}/reference-images/{reference_id}
```

## Style Tests

### Create Style Test

```http
POST /api/v1/styles/{style_id}/tests
```

Request:

```json
{
  "test_text": "A little fox stands under a glowing streetlamp."
}
```

Behavior:

- Load the style and its bound image model.
- Compose the test prompt from `test_text` and `style_prompt`.
- Create a `style_tests` row with `queued` status.
- Enqueue the style test ID in the in-process queue.
- Return the test record.

Response: `202 Accepted`

```json
{
  "id": "styletest_...",
  "style_id": "style_...",
  "status": "queued",
  "test_text": "A little fox stands under a glowing streetlamp.",
  "image_model_snapshot": {
    "id": "model_...",
    "provider_key": "provider",
    "model_key": "model-name"
  },
  "created_at": "2026-05-29T15:00:00Z"
}
```

### Get Style Test

```http
GET /api/v1/style-tests/{style_test_id}
```

## Tasks

### List Tasks

```http
GET /api/v1/tasks?query=&status=&style_id=&limit=20&cursor=...
```

Summary item:

```json
{
  "id": "task_...",
  "display_title": "The rabbit found a lantern...",
  "status": "running",
  "current_step": "generate_images",
  "progress_current": 2,
  "progress_total": 6,
  "style": {
    "id": "style_...",
    "name": "Watercolor Storybook"
  },
  "requested_image_count": null,
  "image_count_mode": "auto",
  "generated_image_count": 2,
  "created_at": "2026-05-29T15:00:00Z",
  "updated_at": "2026-05-29T15:00:00Z"
}
```

### Create Task

```http
POST /api/v1/tasks
```

Request:

```json
{
  "original_text": "用户输入的原始故事文本，必须原样保存。",
  "image_count_mode": "auto",
  "requested_image_count": null,
  "style_id": "style_..."
}
```

Fixed count request:

```json
{
  "original_text": "用户输入的原始故事文本，必须原样保存。",
  "image_count_mode": "fixed",
  "requested_image_count": 6,
  "style_id": "style_..."
}
```

Behavior:

- Save `original_text` exactly as received.
- Snapshot the selected style prompt and bound image model onto the task.
- Create task with `queued` status.
- Enqueue task ID in the in-process queue.
- Return `202 Accepted` with task detail.

Validation:

- `original_text` is required.
- `style_id` must reference an active style.
- Fixed mode requires a valid positive `requested_image_count`.
- Auto mode requires `requested_image_count` to be null.

### Get Task

```http
GET /api/v1/tasks/{task_id}
```

Detail includes:

- exact original text
- style snapshot
- task status and progress
- ordered panels
- generated prompts
- generated images
- step activity
- user-safe error state

### Cancel Task

```http
POST /api/v1/tasks/{task_id}/cancel
```

Behavior:

- Set `cancel_requested_at`.
- Transition to `cancel_requested` when current state allows cancellation.
- Worker checks cancellation at step boundaries.

### Retry Task

```http
POST /api/v1/tasks/{task_id}/retry
```

Only valid for failed or partial states with retryable failed steps. Retries must reuse persisted panels and completed outputs when safe.

### Delete Task

```http
DELETE /api/v1/tasks/{task_id}
```

Deletion requires confirmation in the UI. The first design may hard-delete only when no provider-side cleanup is required. If provider cleanup becomes necessary, replace this with archival or explicit cleanup design before implementation.

## Panels

Panels are created by the task workflow and are not created directly by users in the first design.

### List Task Panels

```http
GET /api/v1/tasks/{task_id}/panels
```

The list is bounded by the task's panel count and ordered by `panel_order`.

### Get Panel

```http
GET /api/v1/panels/{panel_id}
```

## Generated Images

### Get Image Metadata

```http
GET /api/v1/generated-images/{image_id}
```

### Download Single Image

```http
GET /api/v1/generated-images/{image_id}/download
```

### Create Batch Download

```http
POST /api/v1/tasks/{task_id}/downloads
```

Behavior:

- If archive creation is immediate, return a download URL.
- If archive creation needs a background task, return `202 Accepted` with download job status.
- The first implementation should prefer direct archive creation for small task image counts.

Response:

```json
{
  "id": "download_...",
  "task_id": "task_...",
  "status": "ready",
  "image_count": 6,
  "filename": "doodlestory-task-task_....zip",
  "download_url": "/api/v1/downloads/download_.../content"
}
```

## Assets

Assets represent uploaded reference images, generated images, and generated archives.

### Upload Asset

```http
POST /api/v1/assets
Content-Type: multipart/form-data
```

Allowed initial purposes:

- `style_reference`

Generated image and archive assets are created by workflows, not direct upload.

### Get Asset Metadata

```http
GET /api/v1/assets/{asset_id}
```

### Get Asset Content

```http
GET /api/v1/assets/{asset_id}/content
```

## Workflow Statuses

Task statuses:

- `queued`
- `running`
- `succeeded`
- `partial_succeeded`
- `failed`
- `cancel_requested`
- `cancelled`
- `retrying`

Task steps:

- `segment_story`
- `generate_panel_prompts`
- `generate_images`
- `package_download`

Style test statuses:

- `queued`
- `running`
- `succeeded`
- `failed`
- `cancel_requested`
- `cancelled`
- `retrying`

Provider errors:

- Permanent validation errors are not retried.
- Transient provider failures may retry with bounded attempts.
- User cancellation is never retried automatically.
