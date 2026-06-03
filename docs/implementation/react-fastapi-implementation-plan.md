# React + FastAPI 实施计划

## 结论

当前代码已经从错误的 Next.js 全栈架构改成 `frontend/` React + `backend/` FastAPI，但它仍然只是第一层骨架，距离 `docs/design/ui.md`、`docs/design/api.md`、`docs/design/database.md` 的目标还有明显差距。

尤其是风格模块、任务队列、LLM 切分、panel prompt 生成、图片生成、下载、分页接口、数据库迁移和 Runway / Creative AI Studio 风格 UI 都尚未真正实现。

## 当前偏差

| 领域 | 设计预期 | 当前状态 | 结论 |
| --- | --- | --- | --- |
| 前端架构 | React 前端，任务/风格/设置三大工作台 | 已是 React + Vite，但页面是单文件粗糙实现 | 架构对了，产品完成度不足 |
| 后端架构 | Python FastAPI，REST `/api/v1` | 已是 FastAPI | 架构对了，接口深度不足 |
| 认证 | 邮箱密码注册登录，普通用户只看自己任务，Admin 可看全部 | 基础 Cookie session 已有 | 可用，但缺找回密码、会话表、CSRF 策略 |
| API 响应 | 统一错误结构、分页、摘要/详情分离 | 当前是简化 `{data}`，无分页 | 不符合设计 |
| 数据库 | 完整任务工作流事实来源 | 缺 `generation_steps`、`task_downloads`、很多状态时间和错误字段 | 不符合设计 |
| 迁移 | 可审计 migration | 当前 `Base.metadata.create_all` | 不符合长期维护 |
| 风格 | CRUD、参考图、测试风格、生图模型名、历史快照 | 有基础 CRUD 和上传入口，但 UI/API 都很薄 | 不符合核心需求 |
| 风格配置 | 普通用户不暴露 provider/API key，只绑定 `image_model_name` | 字段由风格维护，密钥由 env 维护 | 符合当前收口方向 |
| 任务创建 | 保存原始文本、选数量、选风格、入队 | 当前直接返回 503 | 未实现 |
| LLM | SiliconFlow 调两次：切分、panel prompt | 未实现 | 未实现 |
| 生图 | XG `/v1/images/edits`，多参考图 `image[]`，9:16 | 未实现 | 未实现 |
| 文件存储 | 本地默认，可配置；必要时对象存储 | 只有本地 | MVP 可用，但需抽象存储接口 |
| UI 风格 | Runway / Creative AI Studio，影像中心，深色/中性专业工具 | 当前偏普通后台表单 | 不符合视觉目标 |

## 外部接口决策

### LLM：SiliconFlow

使用 OpenAI SDK 兼容方式调用 SiliconFlow：

- base url：`https://api.siliconflow.cn/v1`
- API key：`SILICONFLOW_API_KEY`
- 默认模型：`SILICONFLOW_TEXT_MODEL`
- 调用形态：`client.chat.completions.create(...)`
- 切分和 prompt 生成都要求 JSON 输出。

SiliconFlow 文档显示其文本生成支持 OpenAI SDK 调用方式，示例 base url 为 `https://api.siliconflow.cn/v1`，并支持 `response_format={"type":"json_object"}` 约束 JSON 输出。

### 生图：XG GPT Image

使用你提供的接口：

- base url：`https://api.xgapi.top`
- endpoint：`POST /v1/images/edits`
- 完整地址：`https://api.xgapi.top/v1/images/edits`
- header：`Authorization: Bearer <XG_API_KEY>`
- content type：`multipart/form-data`
- 模型：`gpt-image-2`
- 参考图字段：重复字段 `image[]`
- prompt 字段：`prompt`
- 比例：`aspect_ratio=9:16`
- 返回：`response_format=url`

图片生成服务封装必须支持：

- 单个 panel 调一次图片接口。
- 每个 panel 只保留一张生成图。
- 将风格参考图作为多图参考传入 `image[]`。
- 如果接口返回 URL，后端必须下载图片并写入 `file_assets`，不能只保存远程 URL。
- provider 请求失败写入 `generated_images.error_code/error_message` 和 `generation_tasks.error_message`，不能静默忽略。

### 对象存储：七牛是否需要

本地开发仍可使用本地磁盘；需要跨机器访问、长期保存或 CDN 加速时，配置 `STORAGE_BACKEND=qiniu` 启用七牛对象存储。

需要接七牛的场景：

- 生成图片需要跨机器访问。
- 后端容器/服务重启后本地磁盘不可靠。
- 图片结果需要长期保存、CDN 加速、私有下载 URL。
- XG 返回远程图片 URL，后端下载后希望持久化到对象存储，而不是只存本地。

建议实现方式：

- 抽象 `StorageBackend`，提供 `local` 和 `qiniu` 两种实现。
- 默认 `STORAGE_BACKEND=local`。
- 当 env 配置 `STORAGE_BACKEND=qiniu` 时启用七牛；配置缺失或上传失败必须明确报错，不能静默切回本地。
- 数据库 `file_assets.storage_backend` 保存 `local` 或 `qiniu`。
- `storage_key` 永远是内部 key，不暴露服务器绝对路径。
- 缩略图访问通过 `/api/v1/assets/{asset_id}/content?variant=thumbnail`；本地资产按需生成 WebP 缩略图，七牛资产使用 `imageView2` URL 参数生成缩略图。
- 七牛配置字段兼容 `QINIU_*` 和现有 `QNY_*` 命名：`QNY_ACCESS_KEY`、`QNY_SECRET_KEY`、`QNY_BUCKET`、`QNY_DOMAIN`。

七牛 Python SDK 文档支持 `pip install qiniu`，通过 `Auth(access_key, secret_key)` 初始化，使用 `upload_token` 和 `put_file_v2` 上传文件；私有空间下载可以通过 `private_download_url` 生成带过期时间的下载 URL。

## 环境变量规划

```env
APP_ENV=development
DATABASE_URL=sqlite:///./doodlestory.db
SESSION_SECRET=replace-with-long-secret
ADMIN_EMAILS=admin@example.com
FRONTEND_ORIGIN=http://127.0.0.1:3000

STORAGE_BACKEND=local
DOODLESTORY_STORAGE_ROOT=./storage

SILICONFLOW_API_KEY=
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
SILICONFLOW_MODEL=deepseek-ai/DeepSeek-V3.2

XG_API_KEY=
XG_API_BASE_URL=https://api.xgapi.top

QINIU_ACCESS_KEY=
QINIU_SECRET_KEY=
QINIU_BUCKET=
QINIU_BUCKET_DOMAIN=
QINIU_PRIVATE_BUCKET=true
```

规则：

- `style.image_model_name` 保存统一生图平台的模型名，例如 `gpt-image-2`。
- 普通用户 API 不返回 provider key、API key 或默认参数。
- 风格创建页允许维护模型名，但不允许输入 provider 或密钥。
- LLM 平台、LLM 模型、XG base url 和 XG API key 全部由 env 维护。

## 风格模块目标设计

风格是本产品的核心资产，不能只是一个文本 prompt 表单。

### 风格数据

`styles` 表应包含：

- `id`
- `name`
- `description`
- `status`
- `style_prompt`
- `image_model_name`
- `cover_asset_id`
- `last_tested_at`
- `created_at`
- `updated_at`

`style_reference_images`：

- `style_id`
- `asset_id`
- `display_order`
- `created_at`

`style_tests`：

- `style_id`
- `test_text`
- `style_prompt_snapshot`
- `image_model_name_snapshot`
- `composed_prompt`
- `status`
- `output_asset_id`
- `provider_request_id`
- `error_code`
- `error_message`
- `started_at`
- `finished_at`

### 风格 API

必须实现：

- `GET /api/v1/styles?query=&status=&limit=&cursor=`
- `POST /api/v1/styles`
- `GET /api/v1/styles/{style_id}`
- `PATCH /api/v1/styles/{style_id}`
- `DELETE /api/v1/styles/{style_id}`
- `POST /api/v1/styles/{style_id}/reference-images`
- `DELETE /api/v1/styles/{style_id}/reference-images/{reference_id}`
- `POST /api/v1/styles/{style_id}/tests`
- `GET /api/v1/style-tests/{style_test_id}`

删除规则：

- 如果风格被任务引用，禁止硬删除。
- 可后续增加归档，但不能静默删除历史任务依赖。

### 风格 UI

风格列表采用 Runway / Creative AI Studio 风格：

- 深色或中性灰黑背景。
- 风格卡片以参考图/封面图为视觉中心。
- 显示名称、状态、最近测试、参考图数量、使用任务数。
- 支持搜索、状态筛选、排序。
- 空状态不做营销文案，直接提供创建入口。

风格详情：

- 顶部大封面/参考图墙。
- 右侧或下方展示风格 prompt。
- 显示生图模型名，但普通用户看不到密钥和模型私密参数。
- 风格测试面板可输入测试文本并生成 9:16 测试图。

创建/编辑：

- 名称、描述、状态、风格 prompt。
- 多参考图上传、排序、删除。
- 不展示 API key 和 provider key。
- `image_model_name` 是风格字段，用于调用统一生图平台。

## 任务工作流目标设计

### 创建任务

1. 前端提交：
   - `original_text`
   - `image_count_mode`
   - `requested_image_count`
   - `style_id`
2. 后端原样保存 `original_text`。
3. 后端读取 style，并保存：
   - `style_name_snapshot`
   - `style_prompt_snapshot`
   - `image_model_name_snapshot`
4. 创建任务状态 `queued`。
5. 创建或准备 `generation_steps`。
6. 将任务 ID 投入进程内队列。
7. 返回 `202 Accepted`。

### Worker 执行

1. `segment_story`
   - 调 SiliconFlow。
   - 固定数量时按用户指定数量切分。
   - 自动数量时按语义切分，约 10 个中文字符一段作为启发。
   - 写入 `task_panels`。
2. `generate_panel_prompts`
   - 调 SiliconFlow。
   - 输入：原始故事、风格 prompt、panel 文本。
   - 输出每个 panel 的静态画面 prompt。
   - 不改写原始故事。
   - 写入 `task_panels.generated_prompt`。
3. `generate_images`
   - 对每个 panel 调 XG `/v1/images/edits`。
   - prompt = 风格强约束 + panel prompt。
   - 传入风格参考图 `image[]`。
   - 固定 `aspect_ratio=9:16`。
   - 下载返回 URL 到本地或七牛。
   - 写入 `generated_images` 和 `file_assets`。
4. 完成任务：
   - 全部成功：`succeeded`
   - 部分成功：`partial_succeeded`
   - 全部失败：`failed`

### LLM Prompt 产物

需要新增两份版本化 prompt 文档：

- `backend/app/prompts/segment_story_v1.md`
- `backend/app/prompts/generate_panel_prompt_v1.md`

LLM 输出必须 JSON 化，不能靠字符串切割。

## 数据库实施步骤

1. 引入 Alembic，停止依赖 `Base.metadata.create_all`。
2. 建立初始 migration。
3. 补齐表：
   - `sessions`
   - `generation_steps`
   - `task_downloads`
4. 补齐字段：
   - 任务 current_step、attempts、started_at、finished_at、cancel_requested_at、internal_error_ref。
   - panel prompt_model_snapshot、error_code、error_message。
   - generated_images provider_request_id、started_at、finished_at、error 字段。
   - file_assets storage_backend、public_url、width、height。
5. 增加约束：
   - fixed 数量必须有 `requested_image_count`。
   - auto 数量必须没有 `requested_image_count`。
   - panel_order 从 1 开始。
   - 每个 panel 只能一张 generated image。

## API 实施步骤

1. 统一响应格式：
   - 列表：`{ items, page }`
   - 错误：`{ error: { code, message, fields, request_id } }`
2. 所有列表接口支持 `limit <= 100` 和 cursor。
3. 任务接口补齐：
   - create
   - detail
   - cancel
   - retry task
   - panels
   - generated image metadata/download
   - batch downloads
4. 风格接口补齐：
   - reference image delete
   - style test create/detail
   - style delete 引用保护
5. 资产接口补齐：
   - metadata
   - content
   - 权限检查

## 前端实施步骤

### UI 风格基线

统一为 Runway / Creative AI Studio：

- 深色中性背景：`#0b0d10`、`#111318`、`#1a1d24`。
- 内容卡片克制，不做浅色后台表格感。
- 图片预览、任务缩略图、参考图墙是视觉中心。
- 字体用系统无衬线，数字和状态小号克制。
- 9:16 图片容器固定比例。

### 页面拆分

当前 `frontend/src/main.tsx` 必须拆分为：

```text
frontend/src/
  app/
    App.tsx
    routes.tsx
  pages/
    LoginPage.tsx
    RegisterPage.tsx
    TasksPage.tsx
    TaskCreatePage.tsx
    TaskDetailPage.tsx
    StylesPage.tsx
    StyleCreatePage.tsx
    StyleDetailPage.tsx
    StyleEditPage.tsx
    SettingsPage.tsx
  components/
    layout/
    ui/
    task/
    style/
    image/
  api/
    client.ts
    auth.ts
    styles.ts
    tasks.ts
    assets.ts
```

### 任务页面

- 任务列表：搜索、状态筛选、风格筛选、分页。
- 任务新建：原始文本、数量模式、固定数量、风格选择器。
- 任务详情：原文、进度、steps、panels、图片网格、下载。
- 图片预览弹窗：放大、上一张/下一张、下载。

### 风格页面

- 风格列表：参考图卡片、搜索、状态筛选。
- 风格创建：多图上传 + prompt。
- 风格详情：参考图墙、prompt、测试面板、最近测试结果。
- 风格编辑：保存 prompt 与参考图。

## 分 PR 实施计划

### PR 01：纠正工程基线

状态：已完成。

- 删除残留 Next 痕迹。
- 更新 README 和 `docs/progress.md`，明确 React/FastAPI。
- 清理 `__pycache__`、本地 DB、构建产物。
- 确认 `./scripts/check.sh` 只检查 `backend/app` 和 `frontend`。

验收：

- `./scripts/check.sh` 通过。
- `git status` 无构建产物。

### PR 02：数据库和迁移

状态：已完成。

- 接入 Alembic。
- 完整迁移当前设计表。
- 补齐任务、steps、downloads、assets 字段。

验收：

- 新库能通过 migration 创建完整 schema。
- `sqlite3` 可看到所有目标表。

### PR 03：统一 API 与认证边界

状态：已完成。

- 统一响应和错误结构。
- 列表分页。
- 任务 owner 权限。
- Admin 查询全部任务。

验收：

- 未登录访问返回 401。
- 普通用户不能读取他人任务。
- Admin 能读取全部任务。

### PR 04：风格模块完整实现

状态：已完成基础闭环；风格测试真实生图依赖 PR 05-07。

- 风格列表/详情/创建/编辑/删除。
- 多参考图上传、展示、删除。
- 已被任务引用的风格禁止删除。
- `image_model_name` 可在风格表单维护，provider 与密钥不可编辑。

验收：

- 风格完整 CRUD 可用。
- 参考图可上传和展示。
- 普通 UI 不暴露 provider/API key。

### PR 05：固定平台配置加载

状态：已完成。

- 从 env 读取 `SILICONFLOW_API_KEY`、`SILICONFLOW_MODEL`、`XG_API_KEY` 和 `XG_API_BASE_URL`。
- 移除旧的多 profile registry。
- 生图时使用风格上的 `image_model_name` 作为 XG `model` 参数。

验收：

- 缺配置时返回明确错误。
- 配置字段不会出现在普通 API 响应。

### PR 06：SiliconFlow LLM 客户端

状态：已完成客户端与 Prompt 基础实现；任务 worker 集成在 PR 08。

- 封装 OpenAI SDK 兼容客户端。
- 实现故事切分。
- 实现 panel prompt 生成。
- 保存 LLM 请求错误。

验收：

- 固定图片数能生成对应数量 panels。
- 自动模式能按语义生成 panels。
- 输出 JSON 解析失败会标记任务失败。

### PR 07：XG 图片生成客户端

状态：已完成客户端与风格测试接入；任务图片生成集成在 PR 08。

- 实现 `/v1/images/edits` multipart 调用。
- 多参考图字段 `image[]`。
- `aspect_ratio=9:16`。
- 下载返回 URL 到 `file_assets`。

验收：

- 风格测试能生成一张 9:16 图。
- 任务每个 panel 生成一张图。

### PR 08：进程内队列与任务执行

状态：已完成基础执行链路；后续仍需加强任务详情 UI、下载和更完整的恢复策略。

- 应用启动恢复 queued/running 卡住任务。
- 顺序执行 steps。
- 支持取消任务。
- 不支持单图重试。

验收：

- 创建任务后自动执行。
- 刷新任务详情能看到进度变化。

### PR 09：下载和预览

状态：已完成。

- 单图下载。
- 批量 zip。
- 图片预览弹窗。

验收：

- 已完成任务可以下载 zip。
- zip 文件名和内部文件名符合设计。

### PR 10：Runway 风格 UI 重做

状态：已完成基础视觉重做；后续可继续做更细的组件拆分和动效。

- 深色专业创作工具视觉。
- 任务列表改为影像项目列表。
- 风格列表改为参考图中心卡片。
- 所有图片容器 9:16。

验收：

- Playwright 桌面/移动截图无明显错位。
- 任务和风格页面视觉接近 Creative AI Studio，而不是普通后台。

## 下一步建议

下一轮不要直接继续堆功能，应先执行 PR 01 + PR 02：

1. 把工程基线清理干净。
2. 用 Alembic 固化数据库。
3. 再开始风格模块完整实现。

风格是任务生成质量的入口，建议 PR 04 优先于完整任务 worker，先把风格 CRUD、参考图、测试风格的闭环做扎实。
