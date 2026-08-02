# Sprint 152：项目出站 API 调用清单

## 背景

项目中同时存在 SiliconFlow、OpenAI-compatible Agent、图片 Provider、语音 Provider、内容导入服务、YouTube 发布服务、对象存储和观测告警链路。仅记录 SiliconFlow 与 Native Agent 地址不足以判断一次业务操作实际会触发哪些外部调用。

## 目标

基于当前仓库运行时代码，新增一份不包含密钥的 Markdown 清单，完整记录外部 HTTP、SDK、兄弟服务和本地进程调用，并明确 SiliconFlow、Native Agent、APEXERAPI 配置与实际请求目标之间的关系。

## 范围

- 模型：SiliconFlow、普通 OpenAI-compatible 文本/视觉、Native Agent Responses、旧 AgentModelRouter。
- 媒体：统一生图网关、XG、Grok CLI、SiliconFlow 语音、火山语音、Whisper、FFmpeg、Remotion、comic-video-studio。
- 内容与发布：多平台导入、抖音下载、YouTube 频道研究、YouTube 发布服务。
- 基础设施：七牛、阿里云 OSS、MLflow、飞书失败告警、前端到本项目 FastAPI 的内部 API 边界。
- 说明当前可确认的公开地址、Endpoint、HTTP 方法/路径、配置名、代码入口和不直连配置。
- 记录兼容性探测、Agent SDK 探测、Runtime smoke 和 MLflow smoke 等诊断脚本的主动调用，但与正常业务链路分开标注。

## 非目标

- 不修改业务调用逻辑、Provider 选择、重试策略或认证方式。
- 不把 API Key、Secret、Token、完整 webhook URL 或其他敏感配置写入文档。
- 不把兄弟导入服务内部使用的 YouTube Data API 误写成 DoodleStory 的直接调用。

## 验收标准

1. `docs/integrations/llm-agent-endpoints.md` 标题和内容升级为全量出站调用清单。
2. 文档覆盖源码中已确认的 HTTP、SDK、兄弟服务和本地进程调用入口，并标出直接/间接/内部边界。
3. 文档明确 Native Agent 主地址为 `TEXT_FALLBACK_BASE_URL` 规范化后的 `/responses`，SiliconFlow 为独立的 `/chat/completions` 与语音接口。
4. 文档明确 `APEXERAPI_BASE` 当前没有被 DoodleStory 直接请求。
5. `docs/progress.md` 记录本次变更、验证结果和未执行的完整检查项。
6. `git diff --check` 通过，且文档不包含密钥值。
