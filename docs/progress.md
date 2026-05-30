# 进度记录

## 当前基线

- 分支：`main`
- Harness 状态：`active`
- 产品：`DoodleStory`，文本转图片故事生成项目
- 最近验证状态：产品设计文档已中文化，并通过 `./scripts/check.sh`

## 当前 Sprint 合同

- `docs/contracts/sprint-01-product-design.md`

## 最近完成的工作

- 初始化 Git 仓库，并将 `main` 推送到 `git@github.com:xipebhui/DoodleStory.git`。
- 从 `git@github.com:xipebhui/codex-project-template.git` 引入 Codex 项目 harness。
- 将 README、产品规格、进度记录和当前 sprint 合同适配到 DoodleStory。
- 保留模板中的前端、UI 交互、数据库设计、后端工作流、Python、Java 和通用模块规范。
- 移除模板仓库自身的历史 sprint 与 QA 报告，让 DoodleStory 从自己的合同开始。
- 记录 DoodleStory 的核心业务流程：
  - 风格 CRUD 和风格测试
  - 风格内配置图片模型
  - 用户注册登录
  - 普通用户只能看到自己的任务，Admin 可以看到全部任务
  - 任务创建时原样保存用户文本
  - 故事切分为 panels
  - 带风格约束的 panel prompt 生成
  - 图片生成、放大预览和批量下载
- 设计第一版产品 UI、后端 API 和数据库 schema：
  - `docs/design/ui.md`
  - `docs/design/api.md`
  - `docs/design/database.md`
- 添加产品设计 sprint 的 QA 记录。
- 将 active 产品文档改为中文表达。
- 根据新要求移除独立图片模型模块，并补充注册登录、用户角色和任务可见性规则。
- 根据最新讨论收敛后台生成配置：provider、model、API key 和默认参数不暴露给普通用户；风格只通过后台 `generation_profile_key` 引用服务端配置。
- 明确第一版不支持 prompt 编辑和单图片重试，每个 panel 只生成一张图。
- 明确文件存储使用本地磁盘，`DOODLESTORY_STORAGE_ROOT` 可配置，默认 `./storage`。
- 纠正错误的 Next.js 全栈实现，改为 React + Vite 前端和 Python 3.11 + FastAPI 后端的双服务结构。
- 记录当前 React/FastAPI 实现与产品设计之间的差距，并新增实施计划：`docs/implementation/react-fastapi-implementation-plan.md`。

## 验证记录

- harness 适配后，`./scripts/check.sh` 通过。
- 产品设计文档完成后，`./scripts/check.sh` 通过。
- 产品设计文档中文化后，`./scripts/check.sh` 通过。
- 用户和模型模块设计调整后，`./scripts/check.sh` 通过。
- 后台生成配置和本地文件存储设计调整后，`./scripts/check.sh` 通过。

## 已知缺口

- 当前 React/FastAPI 代码仍是骨架，尚未达到产品设计完整要求。
- 尚未接入 Alembic migration，当前后端仍依赖 SQLAlchemy `create_all`。
- 尚未实现统一分页响应、标准错误结构和完整任务工作流接口。
- 尚未实现完整风格模块，尤其是参考图删除、风格测试、被任务引用时禁止删除和普通用户不编辑后台生成配置。
- LLM 文本切分 prompt 和 panel prompt 生成 prompt 仍需设计和测试。
- LLM provider 已倾向 SiliconFlow，但尚未实现客户端和 prompts。
- 图片生成 provider 已明确使用 XG `/v1/images/edits`，但尚未实现客户端。
- 对象存储第一版继续本地磁盘，七牛作为可选 `StorageBackend` 尚未实现。
- 后台生成配置的 env 加载方式尚未实现。
- UI 尚未达到 Runway / Creative AI Studio 风格。

## 建议下一步

1. 执行 `docs/implementation/react-fastapi-implementation-plan.md` 中的 PR 01：清理工程基线。
2. 执行 PR 02：接入 Alembic 并固化完整数据库 schema。
3. 优先完成 PR 04：风格模块完整实现。
4. 再实现 SiliconFlow LLM、XG 生图和任务队列。
