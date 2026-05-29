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
  "image_model_config": {
    "provider_key": "provider",
    "model_key": "model-name"
  },
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
  "image_provider_key": "provider",
  "image_model_key": "model-name",
  "image_model_parameters": {
    "size": "1024x1024"
  },
  "style_prompt": "使用柔和水彩质感、温和描边和温暖故事书光线。",
  "reference_asset_ids": ["asset_..."]
}
```

校验：

- `name`、`image_provider_key`、`image_model_key`、`style_prompt` 必填。
- 模型配置是风格的一部分，不通过独立图片模型模块选择。

### 获取风格详情

```http
GET /api/v1/styles/{style_id}
```

详情包含完整 `style_prompt`、参考图片、图片模型配置、最近测试记录和使用摘要。

### 更新风格

```http
PATCH /api/v1/styles/{style_id}
```

修改图片模型配置只影响未来风格测试和未来任务。已有任务保留创建时的模型配置快照。

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

- 加载风格和风格内部的图片模型配置。
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
  "image_model_snapshot": {
    "provider_key": "provider",
    "model_key": "model-name"
  },
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
  "image_count_mode": "auto",
  "requested_image_count": null,
  "style_id": "style_..."
}
```

固定数量请求：

```json
{
  "original_text": "用户输入的原始故事文本，必须原样保存。",
  "image_count_mode": "fixed",
  "requested_image_count": 6,
  "style_id": "style_..."
}
```

行为：

- 按收到的内容原样保存 `original_text`。
- 将当前登录用户保存为任务 owner。
- 将选中风格的提示词和图片模型配置快照保存到任务。
- 创建状态为 `queued` 的任务。
- 将任务 ID 放入进程内队列。
- 返回 `202 Accepted` 和任务详情。

校验：

- `original_text` 必填。
- `style_id` 必须指向启用风格。
- 必须是登录用户。
- 固定数量模式必须提供有效正整数 `requested_image_count`。
- 自动模式要求 `requested_image_count` 为 `null`。

### 获取任务详情

```http
GET /api/v1/tasks/{task_id}
```

详情包含：

- 精确原始文本
- 任务 owner，Admin 可见
- 风格快照
- 任务状态和进度
- 有序 panels
- 生成 prompts
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

只允许失败或部分成功且存在可重试失败步骤的任务。重试必须复用已持久化的 panels 和已完成输出，避免重复副作用。

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

## 资产

资产表示上传参考图、生成图片和生成压缩包。

### 上传资产

```http
POST /api/v1/assets
Content-Type: multipart/form-data
```

第一版允许直接上传的用途：

- `style_reference`

生成图片和下载压缩包由工作流创建，不通过直接上传创建。

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

- `segment_story`
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
- 临时 provider 失败可以在次数上限内重试。
- 用户取消的任务永不自动重试。
