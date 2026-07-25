# DoodleStory 产品设计

本目录保存 DoodleStory 第一版可实施的产品设计。

## 文档

- [UI 设计](ui.md)：产品导航、页面结构、交互状态和生成流程体验。
- [后端 API 设计](api.md)：REST 资源、请求与响应结构、分页、错误和工作流动作。
- [数据库设计](database.md)：初始关系型 schema、约束、索引和工作流状态模型。
- [内容提取设计](content-extraction.md)：抖音链接同步下载、图文漫画整组顺序理解、视频音频转写和内容提取 tab 的页面设计。
- [内容提取列表化 UI 设计](content-extraction-list-redesign.md)：内容提取任务列表、创建弹窗和详情弹窗的历史设计；其中故事总结入口已被当前整组图文内容提取方案取代。
  - 效果图：`content-extraction-list-redesign-list.png`、`content-extraction-list-redesign-create.png`、`content-extraction-list-redesign-detail.png`。
- [Agent 漫画创作工作台前端设计 Brief](agent-creative-workspace-frontend-brief.md)：用于独立设计和对比 Agent 对话、结构化分镜画布与对象检查器的高保真交互原型。
- [Agent 会话前端 Demo](agent-conversation-demo/README.md)：独立、无后端的可点击原型，用于体验新建/恢复对话、对话内任务卡片、任务详情和 Panel 上下文引用。
- [Agent V1 Runtime 与模型路由](agent-runtime-architecture.md)：单 Agent、Skill/Tool Runtime、应用侧上下文、checkpoint、HITL、安全事件、MLflow 和火苗/LIO 路由边界。
- [Agent V1 Tool 契约](agent-tool-contracts.md)：模型端口、`load_skill`、生图工具、VL 检查工具、Artifact/Approval 与 `@资源` 注入规则。
- [Sprint 117 Skill 前端视觉与交互基准](sprint-117-skill-ui/README.md)：Skill 列表、编辑器、版本历史、对话 `@Skill` 和执行状态的高保真效果图与交互约束。
- [Agent 模型平台兼容性实测](../testing/agent-model-provider-compatibility-report.md)：火苗与 LIO 的 Chat、JSON、工具、多模态和 Responses 能力结论。
- [Agent V1 全局实施路线图](../implementation/agent-v1-implementation-roadmap.md)：Sprint 111–117 从独立 Agent Shell、MLflow、Skill/Tool Runtime、HITL/SSE、资源引用、Panel/VL 到可插拔 Skill 管理与通用 Loop 的顺序与退出门槛；Evaluation 已顺延到最终阶段。
- [Agent V1 新窗口实施交接](../implementation/agent-v1-new-window-handoff.md)：当前 Sprint 111 和后续每个 Sprint 的必读顺序、可直接使用的启动提示词和验证收尾流程。

## 设计原则

- 原样保存用户提交的故事文本。
- 通过参考图、风格提示词、测试记录和生图模型名，让风格调试可追踪。
- 支持邮箱注册登录；普通用户只能看到自己的任务，Admin 可以看到全部任务。
- 将 AI 生成的中间结果产品化：panel 和生成 prompt 是可查看的业务状态，不是隐藏内部细节。
- 将外部素材处理过程产品化：下载、媒体登记、文案提取和错误状态都应可见。
- 以数据库中的任务状态作为生成流程的唯一事实来源。
- 第一版保持轻量工作流；未经后续明确决策，不引入外部队列或重型工作流基础设施。
