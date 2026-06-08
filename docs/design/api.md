# 后端 API 设计

## 范围

本设计使用 REST 资源和 JSON 负载，不绑定具体 Web 框架。

所有动态列表接口必须强制默认 `limit` 和最大 `limit`。列表响应只返回摘要字段；详情接口返回完整对象和有界子集合。

## 通用规则

基础路径：

```text
/api/v1
```

分页查询参数：

- `limit`：默认 `20`，最大 `100`。
- `cursor`：不透明游标。
- `sort`：接口允许的排序字段。
- `direction`：`asc` 或 `desc`。

列表响应结构：

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

错误响应结构：

```json
{
  "error": {
    "code": "validation_failed",
    "message": "部分字段需要修正。",
    "fields": {
      "original_text": "原始文本不能为空。"
    },
    "request_id": "req_..."
  }
}
```

错误处理：

- `message` 返回用户可读信息。
- 内部 provider 细节存入数据库字段或日志，不直接暴露在公开 API 中。
- provider 调用失败不能静默忽略。
- provider 不可用时不能返回 Mock 生成结果。

## 认证和用户

### 注册

```http
POST /api/v1/auth/register
```

请求：

```json
{
  "email": "user@example.com",
  "password": "strong-password",
  "display_name": "创作者"
}
```

行为：

- 创建普通用户，角色为 `user`。
- 如果所选认证模块支持邮箱验证，则发送验证邮件。
- 不在注册接口里创建任何示例任务或 Mock 数据。

### 登录

```http
POST /api/v1/auth/login
```

请求：

```json
{
  "email": "user@example.com",
  "password": "strong-password"
}
```

响应包含当前用户摘要和会话建立结果。具体 session/cookie/token 形态由后续技术栈决定。

### 退出登录

```http
POST /api/v1/auth/logout
```

### 当前用户

```http
GET /api/v1/auth/me
```

响应：

```json
{
  "id": "user_...",
  "email": "user@example.com",
  "display_name": "创作者",
  "role": "user"
}
```

## 积分

### 查看当前用户积分

```http
GET /api/v1/credits/me
```

响应只用于当前积分账户概览，不默认加载流水明细：

```json
{
  "data": {
    "account": {
      "user_id": "user_...",
      "balance": 30,
      "reserved_balance": 0
    },
    "recent_transactions": []
  }
}
```

规则：

- 新注册用户默认获得 `30` 积分。
- Sprint 44 上线迁移时，当前已经注册的用户统一初始化为 `1000` 积分。
- 所有模型同价，成功产出一张图片扣 `1` 积分。
- 风格测试、人物参考图、正式 panel 图、任务重试和单 panel 修改都按成功图片数扣费。
- 积分不足时不调用图片 Provider，并返回明确错误。

### 兑换激活码

```http
POST /api/v1/credits/redeem
```

请求：

```json
{
  "code": "DS-XXXX-XXXX-XXXX-XXXX"
}
```

行为：

- 激活码存在、未过期、未禁用且未兑换时，为当前用户增加对应积分。
- 兑换成功写入 `activation_code_redeem` 积分流水。
- 已兑换、过期、禁用或不存在的激活码必须明确失败。

### 分页查看当前用户积分流水

```http
GET /api/v1/credits/transactions?filter=spent&limit=10&cursor=...
```

规则：

- 用户在设置页点击 `查看明细` 后才调用该接口；进入设置页默认不加载流水。
- `filter` 可选 `all`、`spent`、`reset`，默认 `all`。
- `spent` 只返回成功出图扣费流水，即 `image_generation_charge`。
- `reset` 返回管理员调整流水，即 `admin_adjustment`，用于快速查看重置或人工调整积分记录。
- 使用标准分页响应，`page.next_cursor` 存在时可以请求下一页。

### 查看当前用户积分消耗趋势

```http
GET /api/v1/credits/usage?days=7
```

规则：

- `days` 只支持 `1`、`7` 和 `30`。
- `days=1` 返回最近 24 个小时桶；`days=7` 和 `days=30` 返回自然日桶。
- 只统计 `image_generation_charge` 成功扣费流水，不统计占用、释放、激活码兑换或管理员调整。

响应：

```json
{
  "data": [
    {
      "label": "06-08",
      "spent_credits": 12,
      "started_at": "2026-06-08T00:00:00"
    }
  ]
}
```

## 管理员积分与用户管理

### 用户列表

```http
GET /api/v1/admin/users?query=&limit=20&cursor=...
```

仅 Admin 可访问。列表返回用户摘要、积分余额、任务数量、成功图片数量和消耗积分。

### 用户详情

```http
GET /api/v1/admin/users/{user_id}
```

返回用户积分摘要和最近积分流水。

### 管理员积分消耗大盘

```http
GET /api/v1/admin/credits/usage?days=7&user_id=...
```

仅 Admin 可访问。

规则：

- `days` 只支持 `1`、`7` 和 `30`；`days=1` 返回最近 24 个小时桶，`days=7` 和 `days=30` 返回自然日桶。
- 不传 `user_id` 时统计全站成功出图扣费流水。
- 传 `user_id` 时只统计该用户成功出图扣费流水。
- 只统计 `image_generation_charge`，不统计占用、释放、激活码兑换或管理员调整。

响应：

```json
{
  "data": {
    "summary": {
      "total_spent_credits": 120,
      "transaction_count": 120,
      "active_user_count": 8
    },
    "points": [
      {
        "label": "06-08",
        "spent_credits": 22,
        "started_at": "2026-06-08T00:00:00"
      }
    ]
  }
}
```

### 管理员积分消耗明细

```http
GET /api/v1/admin/credits/transactions?user_id=...&limit=10&cursor=...
```

仅 Admin 可访问。按时间倒序分页返回成功出图扣费流水，并附带用户邮箱和昵称。

### 调整用户积分

```http
POST /api/v1/admin/users/{user_id}/credits/adjust
```

请求：

```json
{
  "amount": 100,
  "note": "活动赠送"
}
```

规则：

- `amount` 可以为正数或负数，但不能为 `0`。
- 必须填写 `note`。
- 调整后不能让用户可用积分变成负数。
- 调整写入 `admin_adjustment` 积分流水，并记录管理员操作者。

### 生成激活码

```http
POST /api/v1/admin/activation-codes
```

请求：

```json
{
  "credit_amount": 100,
  "count": 10,
  "expires_at": "2026-06-30T23:59:59Z",
  "note": "内测活动"
}
```

响应返回本次生成的明文激活码；明文只在本次响应中展示，数据库长期只保存哈希和前缀。

### 激活码列表

```http
GET /api/v1/admin/activation-codes?limit=20&cursor=...
```

仅 Admin 可访问。列表返回激活码前缀、积分面额、过期时间、禁用状态和兑换状态。

### 找回密码

```http
POST /api/v1/auth/password-reset/request
POST /api/v1/auth/password-reset/confirm
```

第一版使用所选认证模块提供的邮箱找回密码能力，不手写密码重置 token 机制。

## 权限规则

- 未登录用户不能访问任务、风格、风格测试、资产内容和下载接口。
- 普通用户只能查询、查看、取消、重试和下载自己创建的任务。
- Admin 可以查询和查看所有用户的任务。
- 第一版不做组织、团队、项目空间或租户隔离。
- 风格管理暂定为登录用户可见；如果后续需要限制风格维护权限，应新增明确的 admin-only 规则。
- 服务端必须在每个任务详情、panel、图片和下载接口校验任务归属，不能只依赖前端隐藏。

## 风格

### 查询风格列表

```http
GET /api/v1/styles?query=&status=active&limit=20&cursor=...
```

摘要项：

```json
{
  "id": "style_...",
  "name": "水彩故事书",
  "description": "柔和水彩插画场景。",
  "status": "active",
  "thumbnail_asset": {
    "id": "asset_...",
    "url": "/api/v1/assets/asset_.../content"
  },
  "last_tested_at": "2026-05-29T15:00:00Z",
  "updated_at": "2026-05-29T15:00:00Z"
}
```

### 创建风格

```http
POST /api/v1/styles
```

请求：

```json
{
  "name": "水彩故事书",
  "description": "柔和水彩插画场景。",
  "status": "draft",
  "style_prompt": "使用柔和水彩质感、温和描边和温暖故事书光线。",
  "reference_asset_ids": ["asset_..."]
}
```

校验：

- `name`、`style_prompt` 必填。
- provider、API key 和默认参数不出现在普通风格接口中。
- 风格必须提交 `image_model_name`，作为统一生图平台的 `model` 参数。

### 获取风格详情

```http
GET /api/v1/styles/{style_id}
```

详情包含完整 `style_prompt`、参考图片、最近测试记录、生图模型名和使用摘要。普通用户详情不返回 provider、API key 或模型默认参数。

### 更新风格

```http
PATCH /api/v1/styles/{style_id}
```

普通风格更新接口只修改名称、描述、状态、风格提示词、参考图片和生图模型名，不修改 provider、API key 或模型默认参数。

规则：

- `image_model_name` 是风格内部配置，保存模型名，不保存密钥。
- 统一生图 Gateway API key、base url、SiliconFlow API key 和 LLM 模型保存在环境变量中。
- 修改 `image_model_name` 只影响未来风格测试和未来任务。已有任务保留创建时的 `image_model_name` 快照。

### 删除风格

```http
DELETE /api/v1/styles/{style_id}
```

当已有任务引用该风格时阻止删除。后续如需要可改为归档流程。

### 上传风格参考图

```http
POST /api/v1/styles/{style_id}/reference-images
Content-Type: multipart/form-data
```

响应包含创建的资产和风格参考图记录。

### 移除风格参考图

```http
DELETE /api/v1/styles/{style_id}/reference-images/{reference_id}
```

## 风格测试

### 创建风格测试

```http
POST /api/v1/styles/{style_id}/tests
```

请求：

```json
{
  "test_text": "一只小狐狸站在发光的路灯下。"
}
```

行为：

- 加载风格和后台绑定的生成配置。
- 将 `test_text` 与 `style_prompt` 组合为测试 prompt。
- 创建 `style_tests` 记录，状态为 `queued`。
- 将风格测试 ID 放入进程内队列。
- 返回测试记录。

响应：`202 Accepted`

```json
{
  "id": "styletest_...",
  "style_id": "style_...",
  "status": "queued",
  "test_text": "一只小狐狸站在发光的路灯下。",
  "created_at": "2026-05-29T15:00:00Z"
}
```

### 获取风格测试

```http
GET /api/v1/style-tests/{style_test_id}
```

## 任务

### 查询任务列表

```http
GET /api/v1/tasks?query=&status=&style_id=&user_id=&limit=20&cursor=...
```

普通用户传入 `user_id` 时返回权限错误，避免静默忽略查询条件。普通用户任务列表只返回自己的任务；Admin 可以使用 `user_id` 筛选任意用户任务。

摘要项：

```json
{
  "id": "task_...",
  "display_title": "兔子找到了一盏灯...",
  "owner": {
    "id": "user_...",
    "display_name": "创作者"
  },
  "status": "running",
  "current_step": "generate_images",
  "progress_current": 2,
  "progress_total": 6,
  "style": {
    "id": "style_...",
    "name": "水彩故事书"
  },
  "requested_image_count": null,
  "image_count_mode": "auto",
  "use_character_references": true,
  "generated_image_count": 2,
  "created_at": "2026-05-29T15:00:00Z",
  "updated_at": "2026-05-29T15:00:00Z"
}
```

### 创建任务

```http
POST /api/v1/tasks
```

自动数量请求：

```json
{
  "original_text": "用户输入的原始故事文本，必须原样保存。",
  "story_input_mode": "original",
  "image_count_mode": "auto",
  "requested_image_count": null,
  "style_id": "style_...",
  "use_character_references": false
}
```

固定数量请求：

```json
{
  "original_text": "用户输入的原始故事文本，必须原样保存。",
  "story_input_mode": "adapted",
  "image_count_mode": "fixed",
  "requested_image_count": 6,
  "style_id": "style_...",
  "use_character_references": true
}
```

行为：

- 按收到的内容原样保存 `original_text`。
- 当 `story_input_mode = adapted` 时，先调用 LLM 生成 `adapted_story_title`、`adapted_story_hook` 和 `adapted_story_text`，再基于增强故事规划封面和分镜。
- 将当前登录用户保存为任务 owner。
- 将选中风格的提示词和生图模型名快照保存到任务。
- 当 `story_input_mode = adapted` 时，任务步骤增加 `adapt_story`。
- 当 `use_character_references = true` 时，任务步骤增加 `extract_characters` 和 `generate_character_references`。
- 创建状态为 `queued` 的任务。
- 将任务 ID 放入进程内队列。
- 返回 `202 Accepted` 和任务详情。

校验：

- `original_text` 必填。
- `style_id` 必须指向启用风格。
- 必须是登录用户。
- 固定数量模式必须提供有效正整数 `requested_image_count`。
- 自动模式要求 `requested_image_count` 为 `null`。
- `story_input_mode` 默认为 `original`。`adapted` 模式固定图片数量包含封面。
- `use_character_references` 默认为 `false`。开启后如果 LLM 未识别到主要人物，任务失败并返回用户可读错误，不静默降级为普通生图。

### 获取任务详情

```http
GET /api/v1/tasks/{task_id}
```

详情包含：

- 精确原始文本
- 故事方案模式下的增强标题、钩子和完整增强故事
- 任务 owner，Admin 可见
- 风格快照
- 任务状态和进度
- 有序 panels
- panels 中包含 `panel_type`、`narration_text` 和 `dialogue_text`
- 生成 prompts
- 人物参考摘要：仅在任务开启人物参考时返回成功的人物参考图、人物姓名和年龄/外形阶段
- 生成图片
- 步骤活动记录
- 用户可读错误状态

### 取消任务

```http
POST /api/v1/tasks/{task_id}/cancel
```

行为：

- 设置 `cancel_requested_at`。
- 当前状态允许取消时切换为 `cancel_requested`。
- worker 在步骤边界检查取消状态。

### 重试任务

```http
POST /api/v1/tasks/{task_id}/retry
```

任务级重试用于处理失败任务，会复用已持久化的 panels 和已完成输出，避免重复副作用。用户显式点击重试不限制次数，`attempts` 仅用于排查和标记重试来源。

### 修改单个 Panel 画面

```http
POST /api/v1/tasks/{task_id}/panels/{panel_id}/edits
```

请求：

```json
{
  "user_instruction": "人物表情更紧张，背景改成雨夜街头"
}
```

行为：

- 创建一条新的 `generated_images` 版本，`source_type = user_edit`。
- 先进入 `rewrite_prompt`，调用 LLM 基于当前 `image_prompt` 和用户修改方向生成新提示词。
- 再进入 `generate_image`，使用新提示词重新生成该 panel 图片。
- 成功后将新版本标记为当前版本，旧版本保留。
- 失败时保留错误信息，不影响旧的当前成功图。

### 删除任务

```http
DELETE /api/v1/tasks/{task_id}
```

UI 必须要求确认。第一版仅在不需要 provider 侧清理时允许硬删除；如果后续需要清理外部资产，应先重新设计归档或显式清理流程。

## Panels

Panels 由任务工作流创建，第一版不允许用户直接创建。

### 查询任务 Panels

```http
GET /api/v1/tasks/{task_id}/panels
```

该列表受任务 panel 数量天然限制，并按 `panel_order` 排序。

### 获取 Panel

```http
GET /api/v1/panels/{panel_id}
```

## 生成图片

### 获取图片元数据

```http
GET /api/v1/generated-images/{image_id}
```

### 下载单张图片

```http
GET /api/v1/generated-images/{image_id}/download
```

### 创建批量下载

```http
POST /api/v1/tasks/{task_id}/downloads
```

行为：

- 若压缩包可即时创建，返回下载 URL。
- 若需要后台打包，返回 `202 Accepted` 和下载任务状态。
- 第一版在任务图片数量较小时优先直接创建压缩包。

响应：

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

### 任务人物参考摘要

任务详情中的 `character_references` 字段只返回可给用户查看的最小信息：

```json
[
  {
    "id": "appearance_...",
    "name": "小鹿同学",
    "age_stage": "成年",
    "asset": {
      "id": "asset_...",
      "content_type": "image/png",
      "byte_size": 123456
    }
  }
]
```

不返回内部人物分析、`visual_prompt`、`reference_prompt`、panel 引用 notes 或完整 provider 响应。

## 资产

资产表示上传参考图、生成图片和生成压缩包。

第一版文件存储使用本地磁盘：

- 存储根目录通过 `DOODLESTORY_STORAGE_ROOT` 配置。
- 未配置时默认使用项目目录下的 `./storage`。
- API 不直接暴露本地磁盘路径。
- 数据库中的 `storage_key` 是相对存储根目录的内部文件定位符，不是密钥，也不是公开 URL。

### 上传资产

```http
POST /api/v1/assets
Content-Type: multipart/form-data
```

第一版允许直接上传的用途：

- `style_reference`

人物参考图、生成图片和下载压缩包由工作流创建，不通过直接上传创建。

### 获取资产元数据

```http
GET /api/v1/assets/{asset_id}
```

### 获取资产内容

```http
GET /api/v1/assets/{asset_id}/content
```

## 工作流状态

任务状态：

- `queued`
- `running`
- `succeeded`
- `partial_succeeded`
- `failed`
- `cancel_requested`
- `cancelled`
- `retrying`

任务步骤：

- `adapt_story`
- `segment_story`
- `extract_characters`
- `generate_character_references`
- `generate_panel_prompts`
- `generate_images`
- `package_download`

风格测试状态：

- `queued`
- `running`
- `succeeded`
- `failed`
- `cancel_requested`
- `cancelled`
- `retrying`

Provider 错误规则：

- 永久性校验错误不重试。
- 生图请求或结果图下载出现 timeout 时自动重试 3 次，任一重试成功即停止。
- 其它临时 provider 失败可以由用户显式再次重试；Provider 单次请求内部仍使用配置的有限重试次数。
- 用户取消的任务永不自动重试。
- 单 panel 修改会新增图片版本；当前版本由 `is_current` 标记。
