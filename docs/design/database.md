# 数据库设计

## 范围

本设计假设使用关系型 OLTP 数据库，命名风格兼容 PostgreSQL，但不绑定具体 ORM 或 migration 工具。当前规模按小项目/MVP 处理。

数据库是生成工作流状态的事实来源。进程内队列只负责调度任务 ID，不能作为进度或结果的唯一记录。

## 实体关系概要

```text
users 1--N generation_tasks
users 1--1 user_credit_accounts
users 1--N credit_transactions
users 1--N credit_activation_code_redemptions
styles 1--N style_reference_images N--1 file_assets
styles 1--N style_tests
styles 1--N generation_tasks
generation_tasks 1--N task_panels
task_panels 1--N generated_images
generation_tasks 1--N generation_steps
generation_tasks 1--N task_characters 1--N task_character_appearances
task_panels 1--N task_panel_character_appearances N--1 task_character_appearances
file_assets 1--N generated_images
file_assets 1--N task_character_appearances
file_assets 1--N task_downloads
credit_activation_codes 1--0..1 credit_activation_code_redemptions
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

### Session 存储

第一版不在业务 schema 中固定设计 `sessions` 表。登录会话由后续选定的认证模块负责，例如 Supabase Auth、Better Auth 或其他与技术栈匹配的方案。

原因：

- session 的表结构和 token 机制高度依赖认证模块。
- 提前设计自定义 session 表会限制后续认证选型。
- 当前业务数据库只需要保存用户资料和角色。

### `user_credit_accounts`

保存用户当前积分账户。数据库是积分余额的事实来源，前端不能自行维护余额。

字段：

- `id` 主键
- `user_id` 外键到 `users.id`，not null，唯一
- `balance` integer not null，当前可用积分
- `reserved_balance` integer not null，生图请求已占用但尚未最终扣费或释放的积分
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

约束：

- `balance >= 0`
- `reserved_balance >= 0`
- 每个用户最多一个积分账户。

说明：

- Sprint 44 上线时，已有用户统一初始化为 `1000` 积分。
- 新注册用户默认获得 `30` 积分。

### `credit_transactions`

保存所有积分变动流水，用于审计和用户使用明细。

字段：

- `id` 主键
- `user_id` 外键到 `users.id`，not null
- `transaction_type` text not null，取值 `initial_grant`、`admin_adjustment`、`activation_code_redeem`、`image_generation_reserve`、`image_generation_charge`、`image_generation_release`
- `amount` integer not null
- `balance_before` / `balance_after` integer not null
- `reserved_balance_before` / `reserved_balance_after` integer not null
- `admin_user_id` 外键到 `users.id`，null，用于管理员调整
- `task_id`、`panel_id`、`generated_image_id`、`style_test_id`、`character_appearance_id`、`activation_code_id` 可选外键，用于追踪扣费来源
- `note` text null
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

索引：

- `idx_credit_transactions_user_id`：用户流水列表。
- `idx_credit_transactions_transaction_type`：按类型统计消耗。
- 各关联外键索引用于从任务、生图版本、风格测试、人物参考或激活码追溯流水。

### `credit_activation_codes`

保存管理员生成的单次兑换激活码。数据库只保存激活码哈希和前缀，明文只在生成接口响应中返回一次。

字段：

- `id` 主键
- `code_hash` text not null，唯一
- `code_prefix` text not null
- `credit_amount` integer not null
- `note` text null
- `expires_at` timestamptz null
- `disabled_at` timestamptz null
- `created_by_admin_id` 外键到 `users.id`，null
- `redeemed_by_user_id` 外键到 `users.id`，null
- `redeemed_at` timestamptz null
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

约束：

- `credit_amount > 0`
- `code_hash` 唯一。

### `credit_activation_code_redemptions`

保存激活码兑换记录。

字段：

- `id` 主键
- `activation_code_id` 外键到 `credit_activation_codes.id`，not null，唯一
- `user_id` 外键到 `users.id`，not null
- `transaction_id` 外键到 `credit_transactions.id`，not null，唯一
- `redeemed_at` timestamptz not null
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

### `styles`

保存可复用视觉风格。风格只绑定生图模型名；provider、API key 和模型默认参数属于后台私密配置，不进入普通风格编辑流程。

字段：

- `id` 主键
- `name` text not null
- `description` text null
- `status` text not null，取值 `draft`、`active`、`disabled`
- `image_model_name` text not null
- `style_prompt` text not null
- `last_tested_at` timestamptz null
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

约束：

- `name` 唯一。
- `style_prompt` 不能为空字符串。

索引：

- `idx_styles_status_updated_at`：`status`, `updated_at desc`，用于风格列表。
- `idx_styles_image_model_name`：`image_model_name`，用于按生图模型名排查风格。

说明：

- `image_model_name` 是调用统一生图平台时传入的模型名，例如 `gpt-image-2`。
- 统一生图 Gateway API key、base url、LLM API key 和 LLM 模型保存在环境变量中，不进入数据库和普通用户 API。
- 普通用户可以看到模型名以理解风格差异，但不接触密钥或 provider 配置。

### `file_assets`

保存上传文件和生成文件的元数据。第一版文件内容存本地磁盘。

存储规则：

- 存储根目录通过环境变量 `DOODLESTORY_STORAGE_ROOT` 配置。
- 未配置时默认使用项目目录下的 `./storage`。
- `storage_key` 是相对存储根目录的内部文件定位符，例如 `generated-images/task_123/panel-1.png`。
- `storage_key` 不是密钥，也不是公开 URL。
- API 读取文件时由后端根据 `storage_key` 定位本地文件，不能把服务器绝对路径暴露给用户。

字段：

- `id` 主键
- `purpose` text not null，取值 `style_reference`、`character_reference`、`generated_image`、`download_archive`
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
- `image_model_name_snapshot` text not null
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
- `story_input_mode` text not null，取值 `original`、`adapted`
- `adapted_story_title` text null
- `adapted_story_hook` text null
- `adapted_story_text` text null
- `image_count_mode` text not null，取值 `auto`、`fixed`
- `requested_image_count` integer null
- `use_character_references` boolean not null，默认 `false`
- `style_id` 外键到 `styles.id`，not null
- `style_name_snapshot` text not null
- `style_prompt_snapshot` text not null
- `image_model_name_snapshot` text not null
- `status` text not null，取值 `queued`、`running`、`succeeded`、`partial_succeeded`、`failed`、`cancel_requested`、`cancelled`、`retrying`
- `current_step` text null，取值 `adapt_story`、`segment_story`、`extract_characters`、`generate_character_references`、`generate_panel_prompts`、`generate_images`、`package_download`
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
- `original_text` 始终保存用户输入；`adapted_story_text` 只在故事方案模式下由 LLM 生成。

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
- `step_name` text not null，取值 `adapt_story`、`segment_story`、`extract_characters`、`generate_character_references`、`generate_panel_prompts`、`generate_images`、`package_download`
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
- `panel_type` text not null，取值 `cover`、`scene`
- `original_text_segment` text not null
- `narration_text` text null
- `dialogue_text` text null
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
- 故事方案模式下，第一个 panel 必须由应用层保证为 `cover`，后续为 `scene`。

索引：

- `idx_task_panels_task_order`：`task_id`, `panel_order`，用于任务详情。

### `task_characters`

保存任务级主要人物。仅当任务开启 `use_character_references` 时创建。

字段：

- `id` 主键
- `task_id` 外键到 `generation_tasks.id`，not null
- `character_key` text not null，LLM 返回的稳定人物 key，例如 `character_1`
- `name` text not null，用户可见的人物称呼
- `description` text null，内部人物身份说明
- `importance` text not null，第一版固定为 `primary`
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

约束：

- `task_id` + `character_key` 唯一。

索引：

- `idx_task_characters_task_id`：`task_id`，用于任务详情加载人物参考。

### `task_character_appearances`

保存同一人物的年龄阶段或外形阶段，以及该阶段对应的人物参考图。

字段：

- `id` 主键
- `task_character_id` 外键到 `task_characters.id`，not null
- `appearance_key` text not null，必须以所属 `character_key` 开头
- `age_stage` text null，例如 `童年`、`成年`、`受伤后`
- `visual_prompt` text not null，人物外形设定
- `reference_prompt` text null，生成人物参考图时使用的最终 prompt
- `reference_image_id` 外键到 `file_assets.id`，null
- `status` text not null，取值 `queued`、`running`、`succeeded`、`failed`、`cancel_requested`、`cancelled`、`retrying`
- `provider_request_id` text null
- `error_code` text null
- `error_message` text null
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

约束：

- `task_character_id` + `appearance_key` 唯一。
- 当 `status = 'succeeded'` 时，应用层要求 `reference_image_id` 非空。

索引：

- `idx_task_character_appearances_task_character_id`：`task_character_id`，用于加载人物阶段。
- `idx_task_character_appearances_status`：`status`，用于排查人物参考图生成状态。

### `task_panel_character_appearances`

保存 panel 与人物外形阶段的引用关系，并确定传给生图模型时的人物参考图顺序。

字段：

- `id` 主键
- `panel_id` 外键到 `task_panels.id`，not null
- `task_character_appearance_id` 外键到 `task_character_appearances.id`，not null
- `reference_order` integer not null，从 `1` 开始，对应最终 prompt 中的 `参考图1`、`参考图2`
- `usage_note` text null，描述该人物在当前 panel 里的位置或作用
- `created_at` timestamptz not null

约束：

- `panel_id` + `task_character_appearance_id` 唯一。
- `panel_id` + `reference_order` 唯一。
- `reference_order` 必须大于 `0`。

索引：

- `idx_task_panel_character_appearances_panel_id`：`panel_id`，用于构建 panel 生图请求。
- `idx_task_panel_character_appearances_task_character_appearance_id`：`task_character_appearance_id`，用于追踪人物阶段引用。

### `generated_images`

保存 panel 的图片生成结果。该表同时承担 panel 图片版本记录，每个 panel 可以有多条生成版本，当前展示和下载使用 `is_current = true` 的成功版本。

字段：

- `id` 主键
- `task_id` 外键到 `generation_tasks.id`，not null
- `panel_id` 外键到 `task_panels.id`，not null
- `status` text not null，取值 `queued`、`running`、`succeeded`、`failed`、`cancelled`
- `generation_number` integer not null
- `is_current` boolean not null，默认 `false`
- `source_type` text not null，取值 `initial`、`user_edit`、`retry`
- `workflow_step` text null，取值 `rewrite_prompt`、`generate_image`
- `user_instruction` text null，用户对单 panel 的修改方向
- `previous_prompt` text null，修改前的 panel image prompt 快照
- `image_prompt` text null，LLM 生成或修改后的画面提示词
- `prompt_change_summary` text null，LLM 对本次修改的摘要
- `llm_model_snapshot` text null
- `final_prompt` text null
- `image_model_name_snapshot` text not null
- `asset_id` 外键到 `file_assets.id`，null
- `provider_request_id` text null
- `started_at` timestamptz null
- `finished_at` timestamptz null
- `error_code` text null
- `error_message` text null
- `internal_error_ref` text null
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

约束：

- `panel_id` + `generation_number` 唯一。
- `generation_number` 必须大于 `0`。
- 当 `status = 'succeeded'` 时，`asset_id` 不能为空。
- 当前阶段由应用层保证每个 panel 只有一个当前成功版本。

索引：

- `idx_generated_images_task_created_at`：`task_id`, `created_at`。
- `idx_generated_images_panel_id`：`panel_id`。
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

1. 插入 `generation_tasks`，保存 `owner_user_id`、精确 `original_text`、风格快照和生图模型名快照。
2. 插入初始 `generation_steps`，或在步骤开始时创建。
3. 进程内队列只放入任务 ID。

Worker 执行：

1. 从 `generation_tasks` 读取当前任务状态。
2. 如果任务已终态或已取消，不产生副作用。
3. 在步骤边界更新 `current_step`、`progress_current`、`progress_total`。
4. 如果是故事方案模式，先写入 `adapted_story_title`、`adapted_story_hook` 和 `adapted_story_text`。
5. 将切分或规划结果写入 `task_panels`；故事方案模式第一个 panel 是封面，并保存旁白/对白。
6. 如果任务开启人物参考，写入 `task_characters` 和 `task_character_appearances`，再生成每个人物阶段的参考图并写入 `file_assets`。
7. 将 prompt 结果写入 `task_panels.generated_prompt`；开启人物参考时，同时写入 `task_panel_character_appearances`，记录 panel 使用哪些人物参考图及顺序。
8. 将图片生成元数据写入 `generated_images`。
9. 将文件元数据写入 `file_assets`。
10. 最终将任务标记为 `succeeded`、`partial_succeeded`、`failed` 或 `cancelled`。

启动恢复：

- 重新入队状态为 `queued`、`retrying` 或过久停留在 `running` 的任务。
- 风格测试当前为同步请求，不进入进程内任务队列。
- 使用步骤状态和幂等键避免重复已完成副作用。

取消：

- 设置任务的 `cancel_requested_at`。
- Worker 在切分、prompt 生成和每张图片生成之间检查取消状态。
- 已完成图片继续保留在任务下。

## 数据完整性说明

- `generation_tasks.original_text` 必须原样保存。
- 故事方案模式下，LLM 改写结果必须独立保存在 `adapted_story_*` 字段，不能覆盖 `original_text`。
- `task_panels.narration_text` 和 `task_panels.dialogue_text` 用于最终生图 prompt 区分旁白字幕和人物对白。
- 任务和风格测试保存风格 prompt 与 `image_model_name` 快照，保证风格后续编辑不影响历史审计。
- 支持用户提交单 panel 画面修改方向；系统调用 LLM 生成新的 `image_prompt`，再为该 panel 生成新的图片版本。
- 任务级重试和单 panel 修改都会保留历史图片版本，当前展示和下载只使用当前成功版本。
- 开启人物参考时，人物阶段参考图独立保存在 `task_character_appearances.reference_image_id`，panel 生图只引用当前 panel 绑定的人物阶段。
- 人物参考图顺序由 `task_panel_character_appearances.reference_order` 决定；panel 生图请求只传当前 panel 绑定的人物参考图，不传风格样张参考图。
- 如果开启人物参考但没有识别到主要人物，任务失败并记录明确错误，不静默降级。
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

- 认证模块具体选择。
- 是否需要在后续版本增加后台配置页来查看当前 env 中的 provider、API key 状态和模型参数。
