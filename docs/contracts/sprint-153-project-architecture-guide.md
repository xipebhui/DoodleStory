# Sprint 153：项目架构导览与 Agent 扩展蓝图

## 状态

Complete

## Goal

基于当前仓库的实现、既有 Sprint 合同和集成文档，交付一份可在本地浏览器直接打开的中文 HTML
项目导览。它应让新的协作者能够理解 DoodleStory 的现有运行边界，并据此设计新的 YouTube
赛道研究、视频制作或其他 Agent 流程。

## In Scope

- 在 `docs/architecture/` 创建一个无外部依赖的 HTML 导览入口，以及配套的本地 SVG 架构图和时序图。
- 说明前端、FastAPI、数据库、Native Agent、进程内 Worker、Skill / Tool、媒体管线、存储、
  YouTube 研究和发布服务之间的真实关系。
- 展示一次 Native Agent Run 的创建、持久化、排队、模型 / Tool 执行、审批、恢复和 SSE 投影链路。
- 展示 YouTube 赛道研究到视频发布的当前边界，明确研究服务、发布平台和本地媒体工具的职责。
- 给出新增 Agent 流程应复用的持久化、Tool、Skill、人工确认、前端事件流和验证步骤，并区分
  当前可复用能力、需配置能力和未实现能力。
- 提供关键源码、既有合同、API 清单和视频发布平台文档的本地跳转入口。

## Out of Scope

- 不新增、修改或执行任何新的 Agent / Skill / Tool 业务流程。
- 不调整 Provider、模型、密钥、队列、数据库 schema 或线上部署配置。
- 不把当前仅有配置或规划的能力写成可用功能，也不替代完整的产品、运维或 API 文档。
- 不部署 HTML 到外网或修改 DoodleStory 的产品前端。

## Deliverables

- `docs/architecture/project-guide.html`：本地离线项目导览入口。
- `docs/architecture/diagrams/`：系统架构、Native Agent Run、YouTube 研究到发布三张独立 SVG 图。
- 本 Sprint 合同和 `docs/progress.md` 的完成记录。

## Done Means

- 从 `project-guide.html` 打开时，图表、目录锚点和本地文档链接均可解析，不依赖网络加载。
- 架构与时序说明可以追溯到当前源码和已完成合同；明确标注单实例、进程内队列及外部依赖边界。
- 新协作者能据此判断一个新赛道 Agent 的最小实现切面与不可跳过的审批 / 验证环节。

## Verification

```powershell
git diff --check
# 校验 HTML 本地资源和目录锚点；解析 SVG XML；生成三张 @2x PNG。
```

Manual checks:

- 在本地浏览器打开 HTML，确认图表不依赖在线资源、信息层级可阅读。
- 逐项核对 Agent、YouTube 和 Provider 结论与相应源码 / 集成清单。

## Risks / Notes

- 项目中并存传统任务链路、早期 Agent Runtime 与当前 Native / Durable Runtime；导览以当前
  Native / Durable 链路为主，并把旧链路作为仍存在的兼容边界而不是推荐扩展入口。
- 当前 Worker 是单实例进程内队列。它能恢复合法 Run，但不是多实例分布式调度方案；新的高并发
  或跨机器流程不能假设此边界已经解决。
- 图表 SVG 均已通过 XML 解析并由 HTML 直接引用。图表 Skill 提供的 PNG 转换脚本依赖 `sharp`，
  当前机器未安装该依赖；为避免修改全局 Skill 目录或项目依赖，本 Sprint 不生成 PNG 副本。SVG
  是无损、离线可直接打开的正式文档资产。

## Handoff

- 下一步：先选定一个具体 YouTube 赛道，按导览中的“新流程最小切面”建立独立 Sprint；确认
  研究输入、所需 Tool、人工 Gate、产物定义和发布资格后再开始业务实现。
