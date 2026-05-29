# 数据库设计

## 范围

本设计假设使用关系型 OLTP 数据库，命名风格兼容 PostgreSQL，但不绑定具体 ORM 或 migration 工具。当前规模按小项目/MVP 处理。

数据库是生成工作流状态的事实来源。进程内队列只负责调度任务 ID，不能作为进度或结果的唯一记录。

## 实体关系概要

```text
users 1--N generation_tasks
styles 1--N style_reference_images N--1 file_assets
styles 1--N style_tests
styles 1--N generation_tasks
generation_tasks 1--N task_panels
task_panels 1--N generated_images
generation_tasks 1--N generation_steps
file_assets 1--N generated_images
file_assets 1--N task_downloads
```

## 数据表

### `users`

保存应用用户资料和最小权限角色。认证凭证、密码哈希、邮箱验证和重置 token 优先交给所选认证模块管理；本表保存业务侧用户信息。

字段：

- `id` 主键
- `email` text not null
- `display_name` text null
- `role` text not null，取值 `user`、`admin`
- `auth_provider_subject` text null，保存外部/认证模块用户标识
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

约束：

- `email` 唯一。
- `role` 默认为 `user`。

索引：

- `idx_users_role_created_at`：`role`, `created_at desc`，用于 Admin 用户查询。

### `sessions`

如果所选认证模块不自带 session 表，再创建该表；如果使用 Supabase Auth、Better Auth 等自带存储，可不创建本表，以 provider 的 session 存储为准。

字段：

- `id` 主键
- `user_id` 外键到 `users.id`，not null
- `session_token_hash` text not null
- `expires_at` timestamptz not null
- `created_at` timestamptz not null
- `revoked_at` timestamptz null

约束：

- `session_token_hash` 唯一。

索引：

- `idx_sessions_user_expires_at`：`user_id`, `expires_at desc`。
- `idx_sessions_expires_at`：`expires_at`，用于清理过期 session。

### `styles`

保存可复用视觉风格及其内置图片模型配置。图片模型不作为独立业务模块存在。

字段：

- `id` 主键
- `name` text not null
- `description` text null
- `status` text not null，取值 `draft`、`active`、`disabled`
- `image_provider_key` text not null
- `image_model_key` text not null
- `image_model_parameters` jsonb not null，默认 `{}`
- `style_prompt` text not null
- `last_tested_at` timestamptz null
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

约束：

- `name` 唯一。
- `style_prompt` 不能为空字符串。
- `image_provider_key` 不能为空字符串。
- `image_model_key` 不能为空字符串。

索引：

- `idx_styles_status_updated_at`：`status`, `updated_at desc`，用于风格列表。
- `idx_styles_image_model_config`：`image_provider_key`, `image_model_key`，用于按模型配置排查风格。

### `file_assets`

保存上传文件和生成文件的元数据。文件内容后续可存本地磁盘、对象存储或其他存储系统。

字段：

- `id` 主键
- `purpose` text not null，取值 `style_reference`、`generated_image`、`download_archive`
- `storage_key` text not null
- `original_filename` text null
- `content_type` text not null
- `byte_size` bigint not null
- `checksum_sha256` text null
- `width` integer null
- `height` integer null
- `created_at` timestamptz not null

约束：

- `storage_key` 唯一。
- `byte_size` 必须大于 `0`。

索引：

- `idx_file_assets_purpose_created_at`：`purpose`, `created_at desc`，用于资产管理和清理视图。

### `style_reference_images`

连接风格和参考图片资产。

字段：

- `id` 主键
- `style_id` 外键到 `styles.id`，not null
- `asset_id` 外键到 `file_assets.id`，not null
- `display_order` integer not null，默认 `0`
- `created_at` timestamptz not null

约束：

- `style_id` + `asset_id` 唯一。

索引：

- `idx_style_reference_images_style_order`：`style_id`, `display_order`, `created_at`，用于风格详情参考图排序。

### `style_tests`

保存风格测试的工作流状态和输出。

字段：

- `id` 主键
- `style_id` 外键到 `styles.id`，not null
- `test_text` text not null
- `style_prompt_snapshot` text not null
- `image_model_snapshot` jsonb not null
- `composed_prompt` text not null
- `status` text not null，取值 `queued`、`running`、`succeeded`、`failed`、`cancel_requested`、`cancelled`、`retrying`
- `attempts` integer not null，默认 `0`
- `max_attempts` integer not null，默认 `3`
- `next_run_at` timestamptz null
- `cancel_requested_at` timestamptz null
- `started_at` timestamptz null
- `finished_at` timestamptz null
- `output_asset_id` 外键到 `file_assets.id`，null
- `provider_request_id` text null
- `error_code` text null
- `error_message` text null
- `internal_error_ref` text null
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

约束：

- `test_text` 不能为空字符串。
- `composed_prompt` 不能为空字符串。

索引：

- `idx_style_tests_style_created_at`：`style_id`, `created_at desc`，用于最近测试记录。
- `idx_style_tests_status_next_run_at`：`status`, `next_run_at`，用于 worker 恢复。

### `generation_tasks`

保存用户发起的文本转图片任务。

字段：

- `id` 主键
- `owner_user_id` 外键到 `users.id`，not null
- `display_title` text not null
- `original_text` text not null
- `image_count_mode` text not null，取值 `auto`、`fixed`
- `requested_image_count` integer null
- `style_id` 外键到 `styles.id`，not null
- `style_name_snapshot` text not null
- `style_prompt_snapshot` text not null
- `image_model_snapshot` jsonb not null
- `status` text not null，取值 `queued`、`running`、`succeeded`、`partial_succeeded`、`failed`、`cancel_requested`、`cancelled`、`retrying`
- `current_step` text null，取值 `segment_story`、`generate_panel_prompts`、`generate_images`、`package_download`
- `progress_current` integer not null，默认 `0`
- `progress_total` integer not null，默认 `0`
- `attempts` integer not null，默认 `0`
- `max_attempts` integer not null，默认 `3`
- `next_run_at` timestamptz null
- `cancel_requested_at` timestamptz null
- `started_at` timestamptz null
- `finished_at` timestamptz null
- `error_code` text null
- `error_message` text null
- `internal_error_ref` text null
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

约束：

- `original_text` 不能为空字符串。
- 当 `image_count_mode = 'auto'` 时，`requested_image_count` 必须为 null。
- 当 `image_count_mode = 'fixed'` 时，`requested_image_count` 必须大于 `0`。
- `style_prompt_snapshot` 不能为空字符串。

索引：

- `idx_generation_tasks_status_next_run_at`：`status`, `next_run_at`，用于 worker 轮询和恢复。
- `idx_generation_tasks_status_updated_at`：`status`, `updated_at desc`，用于任务列表筛选。
- `idx_generation_tasks_style_created_at`：`style_id`, `created_at desc`，用于风格使用情况和任务筛选。
- `idx_generation_tasks_owner_created_at`：`owner_user_id`, `created_at desc`，用于普通用户只查询自己的任务。
- `idx_generation_tasks_created_at`：`created_at desc`，用于任务列表默认排序。

### `generation_steps`

保存任务步骤级状态，用于可视化进度、重试和活动记录。

字段：

- `id` 主键
- `task_id` 外键到 `generation_tasks.id`，not null
- `step_name` text not null，取值 `segment_story`、`generate_panel_prompts`、`generate_images`、`package_download`
- `status` text not null，取值 `queued`、`running`、`succeeded`、`failed`、`cancelled`、`retrying`
- `attempts` integer not null，默认 `0`
- `idempotency_key` text not null
- `started_at` timestamptz null
- `finished_at` timestamptz null
- `output_ref` text null
- `error_code` text null
- `error_message` text null
- `internal_error_ref` text null
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

约束：

- `idempotency_key` 唯一。

索引：

- `idx_generation_steps_task_created_at`：`task_id`, `created_at`，用于任务详情活动记录。
- `idx_generation_steps_status_updated_at`：`status`, `updated_at`，用于检测卡住的步骤。

### `task_panels`

保存语义切分后的故事片段和生成图 prompt。

字段：

- `id` 主键
- `task_id` 外键到 `generation_tasks.id`，not null
- `panel_order` integer not null
- `original_text_segment` text not null
- `prompt_status` text not null，取值 `pending`、`generated`、`failed`
- `generated_prompt` text null
- `prompt_model_snapshot` jsonb null
- `error_code` text null
- `error_message` text null
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

约束：

- `task_id` + `panel_order` 唯一。
- `panel_order` 必须大于 `0`。
- `original_text_segment` 不能为空字符串。
- 当 `prompt_status = 'generated'` 时，`generated_prompt` 不能为空。

索引：

- `idx_task_panels_task_order`：`task_id`, `panel_order`，用于任务详情。

### `generated_images`

保存 panel 的图片生成结果。

字段：

- `id` 主键
- `task_id` 外键到 `generation_tasks.id`，not null
- `panel_id` 外键到 `task_panels.id`，not null
- `image_order` integer not null，默认 `1`
- `status` text not null，取值 `queued`、`running`、`succeeded`、`failed`、`cancelled`、`retrying`
- `final_prompt` text not null
- `image_model_snapshot` jsonb not null
- `asset_id` 外键到 `file_assets.id`，null
- `provider_request_id` text null
- `attempts` integer not null，默认 `0`
- `max_attempts` integer not null，默认 `3`
- `started_at` timestamptz null
- `finished_at` timestamptz null
- `error_code` text null
- `error_message` text null
- `internal_error_ref` text null
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

约束：

- `panel_id` + `image_order` 唯一。
- 当 `status = 'succeeded'` 时，`asset_id` 不能为空。

索引：

- `idx_generated_images_task_created_at`：`task_id`, `created_at`。
- `idx_generated_images_panel_order`：`panel_id`, `image_order`。
- `idx_generated_images_status_updated_at`：`status`, `updated_at`，用于恢复和卡住图片检测。

### `task_downloads`

保存批量下载压缩包元数据。

字段：

- `id` 主键
- `task_id` 外键到 `generation_tasks.id`，not null
- `status` text not null，取值 `queued`、`running`、`ready`、`failed`
- `image_count` integer not null，默认 `0`
- `asset_id` 外键到 `file_assets.id`，null
- `filename` text not null
- `error_code` text null
- `error_message` text null
- `internal_error_ref` text null
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

约束：

- 当 `status = 'ready'` 时，`asset_id` 不能为空。

索引：

- `idx_task_downloads_task_created_at`：`task_id`, `created_at desc`，用于任务详情下载记录。

## 工作流状态规则

任务创建：

1. 插入 `generation_tasks`，保存 `owner_user_id`、精确 `original_text`、风格快照和模型配置快照。
2. 插入初始 `generation_steps`，或在步骤开始时创建。
3. 进程内队列只放入任务 ID。

Worker 执行：

1. 从 `generation_tasks` 读取当前任务状态。
2. 如果任务已终态或已取消，不产生副作用。
3. 在步骤边界更新 `current_step`、`progress_current`、`progress_total`。
4. 将切分结果写入 `task_panels`。
5. 将 prompt 结果写入 `task_panels.generated_prompt`。
6. 将图片生成元数据写入 `generated_images`。
7. 将文件元数据写入 `file_assets`。
8. 最终将任务标记为 `succeeded`、`partial_succeeded`、`failed` 或 `cancelled`。

启动恢复：

- 重新入队状态为 `queued`、`retrying` 或过久停留在 `running` 的任务。
- 重新入队状态为 `queued`、`retrying` 或过久停留在 `running` 的风格测试。
- 使用步骤状态和幂等键避免重复已完成副作用。

取消：

- 设置任务的 `cancel_requested_at`。
- Worker 在切分、prompt 生成和每张图片生成之间检查取消状态。
- 已完成图片继续保留在任务下。

## 数据完整性说明

- `generation_tasks.original_text` 必须原样保存。
- 任务和风格测试保存风格 prompt 与图片模型配置快照，保证风格后续编辑不影响历史审计。
- `error_message` 保存用户可读错误；`internal_error_ref` 保存内部细节引用。
- 大型 provider 响应和原始日志不放入主工作流表。
- 被任务引用的风格不应被硬删除。
- 普通用户读取任务时必须按 `owner_user_id` 过滤；Admin 可以跨用户查询。

## 初始查询路径

- 任务列表：普通用户按 `owner_user_id`、状态、风格筛选，并按 `created_at desc` 排序；Admin 可以不加 owner 限制。
- 任务详情：加载单个任务、有序 panels、生成图片和最近步骤。
- 风格列表：按状态筛选，并按 `updated_at desc` 排序。
- 风格详情：加载单个风格、参考图、最近测试和使用摘要。
- Worker 轮询：按 `status`、`next_run_at` 查找排队/重试任务。
- 恢复：按 `status`、`updated_at` 查找卡住的运行中任务。

## 未决 Schema 问题

- 所选认证模块是否自带 session 表；若自带，则不创建本设计中的 `sessions` 表。
- 生成 prompt 是否需要在生图前支持编辑和版本。
- 每个 panel 多图是否是一版能力，还是未来扩展。
- 具体存储后端如何定义 `storage_key`。
