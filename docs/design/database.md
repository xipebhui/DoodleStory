# Database Design

## Scope

This design assumes a relational OLTP database, PostgreSQL-compatible naming, and a small-project/MVP scale. It documents tables, relationships, constraints, and indexes. It does not require a specific ORM or migration tool.

The database is the source of truth for generation workflow state. The in-process queue only schedules task IDs.

## Entity Relationship Summary

```text
image_models 1--N styles
styles 1--N style_reference_images N--1 file_assets
styles 1--N style_tests
styles 1--N generation_tasks
generation_tasks 1--N task_panels
task_panels 1--N generated_images
generation_tasks 1--N generation_steps
file_assets 1--N generated_images
file_assets 1--N task_downloads
```

## Tables

### `image_models`

Stores image model configuration that styles bind to.

Columns:

- `id` primary key
- `display_name` text not null
- `provider_key` text not null
- `model_key` text not null
- `status` text not null check in `active`, `disabled`
- `default_parameters` jsonb not null default `{}`
- `notes` text null
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

Constraints:

- Unique `provider_key`, `model_key`.

Indexes:

- `idx_image_models_status_updated_at` on `status`, `updated_at desc` for model lists.

### `styles`

Stores reusable visual styles and the bound image model.

Columns:

- `id` primary key
- `name` text not null
- `description` text null
- `status` text not null check in `draft`, `active`, `disabled`
- `image_model_id` foreign key to `image_models.id` not null
- `style_prompt` text not null
- `last_tested_at` timestamptz null
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

Constraints:

- Unique `name`.
- `style_prompt` must not be empty.

Indexes:

- `idx_styles_status_updated_at` on `status`, `updated_at desc` for style list.
- `idx_styles_image_model_id` on `image_model_id` for model usage checks.

### `file_assets`

Stores metadata for uploaded and generated files. File bytes may live on local disk, object storage, or another selected storage system later.

Columns:

- `id` primary key
- `purpose` text not null check in `style_reference`, `generated_image`, `download_archive`
- `storage_key` text not null
- `original_filename` text null
- `content_type` text not null
- `byte_size` bigint not null
- `checksum_sha256` text null
- `width` integer null
- `height` integer null
- `created_at` timestamptz not null

Constraints:

- Unique `storage_key`.
- `byte_size` must be greater than `0`.

Indexes:

- `idx_file_assets_purpose_created_at` on `purpose`, `created_at desc` for asset administration and cleanup views.

### `style_reference_images`

Links styles to uploaded reference images.

Columns:

- `id` primary key
- `style_id` foreign key to `styles.id` not null
- `asset_id` foreign key to `file_assets.id` not null
- `display_order` integer not null default `0`
- `created_at` timestamptz not null

Constraints:

- Unique `style_id`, `asset_id`.

Indexes:

- `idx_style_reference_images_style_order` on `style_id`, `display_order`, `created_at`.

### `style_tests`

Stores style test generation workflow state and output.

Columns:

- `id` primary key
- `style_id` foreign key to `styles.id` not null
- `test_text` text not null
- `style_prompt_snapshot` text not null
- `image_model_snapshot` jsonb not null
- `composed_prompt` text not null
- `status` text not null check in `queued`, `running`, `succeeded`, `failed`, `cancel_requested`, `cancelled`, `retrying`
- `attempts` integer not null default `0`
- `max_attempts` integer not null default `3`
- `next_run_at` timestamptz null
- `cancel_requested_at` timestamptz null
- `started_at` timestamptz null
- `finished_at` timestamptz null
- `output_asset_id` foreign key to `file_assets.id` null
- `provider_request_id` text null
- `error_code` text null
- `error_message` text null
- `internal_error_ref` text null
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

Constraints:

- `test_text` must not be empty.
- `composed_prompt` must not be empty.

Indexes:

- `idx_style_tests_style_created_at` on `style_id`, `created_at desc` for recent tests.
- `idx_style_tests_status_next_run_at` on `status`, `next_run_at` for worker recovery.

### `generation_tasks`

Stores user-facing text-to-image tasks.

Columns:

- `id` primary key
- `display_title` text not null
- `original_text` text not null
- `image_count_mode` text not null check in `auto`, `fixed`
- `requested_image_count` integer null
- `style_id` foreign key to `styles.id` not null
- `style_name_snapshot` text not null
- `style_prompt_snapshot` text not null
- `image_model_snapshot` jsonb not null
- `status` text not null check in `queued`, `running`, `succeeded`, `partial_succeeded`, `failed`, `cancel_requested`, `cancelled`, `retrying`
- `current_step` text null check in `segment_story`, `generate_panel_prompts`, `generate_images`, `package_download`
- `progress_current` integer not null default `0`
- `progress_total` integer not null default `0`
- `attempts` integer not null default `0`
- `max_attempts` integer not null default `3`
- `next_run_at` timestamptz null
- `cancel_requested_at` timestamptz null
- `started_at` timestamptz null
- `finished_at` timestamptz null
- `error_code` text null
- `error_message` text null
- `internal_error_ref` text null
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

Constraints:

- `original_text` must not be empty.
- If `image_count_mode = 'auto'`, `requested_image_count` must be null.
- If `image_count_mode = 'fixed'`, `requested_image_count` must be greater than `0`.
- `style_prompt_snapshot` must not be empty.

Indexes:

- `idx_generation_tasks_status_next_run_at` on `status`, `next_run_at` for worker polling and recovery.
- `idx_generation_tasks_status_updated_at` on `status`, `updated_at desc` for task list filtering.
- `idx_generation_tasks_style_created_at` on `style_id`, `created_at desc` for style usage and task list filters.
- `idx_generation_tasks_created_at` on `created_at desc` for newest-first task list.

### `generation_steps`

Stores step-level workflow state for visibility, retries, and activity trail.

Columns:

- `id` primary key
- `task_id` foreign key to `generation_tasks.id` not null
- `step_name` text not null check in `segment_story`, `generate_panel_prompts`, `generate_images`, `package_download`
- `status` text not null check in `queued`, `running`, `succeeded`, `failed`, `cancelled`, `retrying`
- `attempts` integer not null default `0`
- `idempotency_key` text not null
- `started_at` timestamptz null
- `finished_at` timestamptz null
- `output_ref` text null
- `error_code` text null
- `error_message` text null
- `internal_error_ref` text null
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

Constraints:

- Unique `idempotency_key`.

Indexes:

- `idx_generation_steps_task_created_at` on `task_id`, `created_at`.
- `idx_generation_steps_status_updated_at` on `status`, `updated_at` for stuck step detection.

### `task_panels`

Stores semantic story segments and generated image prompts.

Columns:

- `id` primary key
- `task_id` foreign key to `generation_tasks.id` not null
- `panel_order` integer not null
- `original_text_segment` text not null
- `prompt_status` text not null check in `pending`, `generated`, `failed`
- `generated_prompt` text null
- `prompt_model_snapshot` jsonb null
- `error_code` text null
- `error_message` text null
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

Constraints:

- Unique `task_id`, `panel_order`.
- `panel_order` must be greater than `0`.
- `original_text_segment` must not be empty.
- When `prompt_status = 'generated'`, `generated_prompt` must not be null.

Indexes:

- `idx_task_panels_task_order` on `task_id`, `panel_order` for task detail.

### `generated_images`

Stores image-generation results for panels.

Columns:

- `id` primary key
- `task_id` foreign key to `generation_tasks.id` not null
- `panel_id` foreign key to `task_panels.id` not null
- `image_order` integer not null default `1`
- `status` text not null check in `queued`, `running`, `succeeded`, `failed`, `cancelled`, `retrying`
- `final_prompt` text not null
- `image_model_snapshot` jsonb not null
- `asset_id` foreign key to `file_assets.id` null
- `provider_request_id` text null
- `attempts` integer not null default `0`
- `max_attempts` integer not null default `3`
- `started_at` timestamptz null
- `finished_at` timestamptz null
- `error_code` text null
- `error_message` text null
- `internal_error_ref` text null
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

Constraints:

- Unique `panel_id`, `image_order`.
- When `status = 'succeeded'`, `asset_id` must not be null.

Indexes:

- `idx_generated_images_task_created_at` on `task_id`, `created_at`.
- `idx_generated_images_panel_order` on `panel_id`, `image_order`.
- `idx_generated_images_status_updated_at` on `status`, `updated_at` for recovery and stuck image detection.

### `task_downloads`

Stores generated archive metadata for batch downloads.

Columns:

- `id` primary key
- `task_id` foreign key to `generation_tasks.id` not null
- `status` text not null check in `queued`, `running`, `ready`, `failed`
- `image_count` integer not null default `0`
- `asset_id` foreign key to `file_assets.id` null
- `filename` text not null
- `error_code` text null
- `error_message` text null
- `internal_error_ref` text null
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

Constraints:

- When `status = 'ready'`, `asset_id` must not be null.

Indexes:

- `idx_task_downloads_task_created_at` on `task_id`, `created_at desc` for task detail download history.

## Workflow State Rules

Task creation:

1. Insert `generation_tasks` with exact `original_text`, style snapshot, and model snapshot.
2. Insert initial `generation_steps` rows or create them as each step starts.
3. Enqueue only the task ID in memory.

Worker execution:

1. Load current task from `generation_tasks`.
2. Exit without side effects if task is terminal or cancelled.
3. Update `current_step`, `progress_current`, and `progress_total` at step boundaries.
4. Store segmentation output in `task_panels`.
5. Store prompt output in `task_panels.generated_prompt`.
6. Store generated image metadata in `generated_images`.
7. Store file metadata in `file_assets`.
8. Mark task `succeeded`, `partial_succeeded`, `failed`, or `cancelled`.

Startup recovery:

- Re-enqueue tasks with `queued`, `retrying`, or stale `running` status.
- Re-enqueue style tests with `queued`, `retrying`, or stale `running` status.
- Use step status and idempotency keys to avoid repeating completed side effects.

Cancellation:

- Set `cancel_requested_at` on task.
- Workers check cancellation between segmentation, prompt generation, and each image generation.
- Completed images remain linked to the task.

## Data Integrity Notes

- Preserve `generation_tasks.original_text` exactly.
- Use snapshots for style prompt and image model on tasks/tests so historical runs stay auditable after style edits.
- Store user-safe errors in `error_message`; store internal details in `internal_error_ref`.
- Large provider responses and raw logs should not be stored in primary workflow rows.
- Deleting a style or image model should be blocked while referenced by tasks or styles.

## Initial Query Patterns

- Task list: filter by status/style and order by `created_at desc`.
- Task detail: load one task, ordered panels, generated images, and recent steps.
- Style list: filter by status/model and order by `updated_at desc`.
- Style detail: load one style, reference images, recent tests, and usage summary.
- Worker polling: find queued/retrying tasks by `status`, `next_run_at`.
- Recovery: find stale running tasks by `status`, `updated_at`.

## Open Schema Questions

- Whether authentication will introduce `users` and ownership columns.
- Whether generated prompts should become editable versions before image generation.
- Whether multiple images per panel are a first-class feature or only a future extension.
- Which storage backend will provide `storage_key` semantics.
