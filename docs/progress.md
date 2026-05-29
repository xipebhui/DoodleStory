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

## 验证记录

- harness 适配后，`./scripts/check.sh` 通过。
- 产品设计文档完成后，`./scripts/check.sh` 通过。
- 产品设计文档中文化后，`./scripts/check.sh` 通过。
- 用户和模型模块设计调整后，`./scripts/check.sh` 通过。
- 后台生成配置和本地文件存储设计调整后，`./scripts/check.sh` 通过。

## 已知缺口

- 尚未创建前端、后端、具体 migration 文件或 provider 集成。
- LLM 文本切分 prompt 和 panel prompt 生成 prompt 仍需设计和测试。
- 图片模型 provider、存储策略和生成图片下载格式尚未最终选择。
- 认证模块尚未选择，需随技术栈一起确定。
- 后台生成配置的具体加载方式尚未实现，需随 provider 集成一起确定。
- 现有规范仍是文档约束，直到具体技术栈落地后再接入自动化检查。

## 建议下一步

1. 选择第一版实现技术栈，并创建应用骨架实现 sprint。
2. 选择第一版 LLM provider 和图片生成 provider。
3. 明确并测试文本切分和 panel prompt 生成的系统提示词。
4. 选择数据库工具后，将 `docs/design/database.md` 转换成 migration。
