# Sprint 01 合同：产品 UI、API 与数据库设计

## 目标

设计 DoodleStory 第一版产品形态，覆盖 UI 工作流、后端 REST API 契约和关系型数据库 schema，让后续实现可以从清晰、符合 harness 规范的方案开始。

## 范围内

- 定义风格、风格测试、任务、生成进度、图片预览和批量下载的主要 UI 页面与交互状态。
- 定义后端 API 资源、请求/响应结构、分页规则和工作流接口。
- 定义用户、认证、后台生成配置引用、资产、任务、panel、生成 prompt、生成图片和工作流状态的初始关系型数据库 schema。
- 定义普通用户和 Admin 的任务可见性规则。
- 定义本地磁盘文件存储规则，支持通过 env 配置存储根目录。
- 保持轻量工作流设计：进程内队列 + 数据库持久化任务状态。
- 更新项目规格、进度和 QA 记录。

## 范围外

- 实现前端或后端代码。
- 选择具体框架、ORM 或云服务商。
- 接入真实 LLM 或图片生成模型 provider。
- 增加计费、团队、组织或租户系统。
- 引入 Redis、RabbitMQ、Kafka、Temporal、Inngest 或其他外部工作流引擎。

## 交付物

- `docs/design/README.md`
- `docs/design/ui.md`
- `docs/design/api.md`
- `docs/design/database.md`
- `docs/qa/sprint-01-product-design-report.md`
- 更新 `docs/spec.md` 和 `docs/progress.md`

## 完成标准

- 后续实现可以从明确的产品页面、API 契约和 schema 说明开始。
- 设计明确要求原样保存用户原始文本。
- 设计包含注册登录和 `user/admin` 两级角色。
- 普通用户只能看到自己的任务，Admin 可以看到所有任务。
- provider、model、API key 和默认参数不暴露给普通用户。
- 第一版不支持单图片重试，每个 panel 只生成一张图片。
- 任务流程在数据库中保存进度、步骤状态、错误和生成资产引用。
- 动态列表使用服务端有界分页。
- 已运行 `./scripts/check.sh` 验证。

## 验证

```bash
./scripts/check.sh
```

人工/QA 检查：

- 确认 UI 设计包含列表、创建、详情、编辑、加载、空状态、错误、删除确认和图片预览状态。
- 确认 API 列表接口强制 `limit`，且不返回完整详情负载。
- 确认数据库设计包含约束、索引和持久化工作流状态。
- 确认图片模型不作为独立模块存在。
- 确认任务查询和详情设计包含 owner/admin 可见性约束。
- 确认文件存储使用本地磁盘，并通过 `DOODLESTORY_STORAGE_ROOT` 配置。
- 确认没有引入默认兜底、Mock 或静默忽略错误策略。

## 风险 / 备注

- 具体 provider 的字段需要在选择第一版 LLM 和图片生成 provider 后调整。
- 认证模块需要随最终技术栈选择；当前只定义邮箱/密码注册登录和角色需求。

## 交接

- 下一步建议：选择具体技术栈，并创建应用骨架实现 sprint。
