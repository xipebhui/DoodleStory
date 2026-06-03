# 进度记录

## 当前基线

- 分支：`main`
- Harness 状态：`active`
- 产品：`DoodleStory`，文本转图片故事生成项目
- 最近验证状态：产品设计文档已中文化，并通过 `./scripts/check.sh`

## 当前 Sprint 合同

- `docs/contracts/sprint-04-story-adaptation.md`

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
- 根据最新讨论收敛生成配置：LLM 固定一个平台和模型，生图固定一个平台和 API key；风格只绑定 `image_model_name`，不再存在旧的多 profile 配置层。
- 早期曾明确第一版不支持 prompt 编辑和单图片重试；后续已通过单 panel 画面修改将图片生成结果升级为 panel 多版本。
- 明确文件存储使用本地磁盘，`DOODLESTORY_STORAGE_ROOT` 可配置，默认 `./storage`。
- 纠正错误的 Next.js 全栈实现，改为 React + Vite 前端和 Python 3.11 + FastAPI 后端的双服务结构。
- 记录当前 React/FastAPI 实现与产品设计之间的差距，并新增实施计划：`docs/implementation/react-fastapi-implementation-plan.md`。
- 完成 React/FastAPI 工程基线的第一轮清理，接入 Alembic，并补齐初始数据库表：`sessions`、`generation_steps`、`task_downloads` 等工作流表已进入迁移。
- 完成统一 API 契约：列表分页、标准错误结构、认证响应包裹、普通用户任务可见性边界已落地。
- 完成风格模块基础闭环：风格 CRUD、参考图上传/删除、已引用风格删除保护、风格绑定生图模型名、风格页 9:16 参考图展示已落地。
- 已移除旧的多 profile 设计，后端直接从 env 读取 SiliconFlow 与 XG 配置。
- 完成 SiliconFlow LLM 客户端基础实现：新增故事切分与 panel prompt 生成的版本化 Prompt，并封装 OpenAI SDK 兼容 JSON 调用与响应结构校验。
- 完成 XG 图片生成客户端基础实现：支持 `/v1/images/edits` multipart、多参考图 `image[]`、9:16 参数、URL 结果下载到本地文件存储，并接入风格测试入口。
- 完成任务队列基础链路：任务创建会原样保存用户文本并入进程内队列，worker 顺序执行故事切分、panel prompt 和图片生成 steps，失败会写回任务与 step 错误。
- 完成下载和预览基础闭环：成功图片可批量打包为 zip，下载包写入 `task_downloads` 与 `file_assets`，前端任务详情支持 9:16 图片墙、放大预览和下载。
- 完成 Runway / Creative AI Studio 风格基础重做：任务页和风格页统一为深色影像工作台，强化 9:16 图片容器、状态标识、右侧详情面板和专业工具感。
- 将 Google/Gemini 图片模型和 `nano-banana`/`nana-banana` 类 Chat 生图模型切换到 ApexerAPI：从 `APEXERAPI_BASE` 和 `APEXERAPI_API_KEY` 读取配置，XG `/v1/images/edits` 路径继续保留给 image edit 类模型。
- 为 ApexerAPI Chat 生图请求增加独立代理配置 `APEXERAPI_PROXY_URL`，避免远程服务器直连 ApexerAPI 被重置时影响生成。
- 为图片 Provider 增加可开关的原始 IO 诊断日志：`IMAGE_PROVIDER_DEBUG_LOG_RAW_IO` 控制是否打印请求/响应正文，`IMAGE_PROVIDER_DEBUG_LOG_RAW_MAX_CHARS` 控制最大日志长度，便于排查第三方返回结构与 prompt 携带问题。
- 兼容 ApexerAPI Chat 生图成功响应中的 `choices[0].message.content[].image_url.url` 图片字段，可直接解析返回的 data URL 图片。
- 调整图片 Provider 原始 IO 日志脱敏：request 和 response 中的 `data:image/...;base64,...` 都只保留 data URL 头和 base64 长度，不再把完整图片 base64 写入日志。
- 开始支持单 panel 画面修改：`generated_images` 升级为 panel 图片版本表，新增用户修改方向、前后 prompt、当前版本、版本号和修改流程步骤；前端任务详情可提交单 panel 修改并查看版本过程。
- 修复单 panel 修改后的前端轮询问题：任务本身状态不变化时，详情页现在会根据 `generated_images` 的状态变化持续刷新，避免停留在“LLM 改写提示词/生成中”。
- 调整任务详情交互：任务列表不再常驻右侧详情栏，点击任务行后打开独立详情抽屉；详情内容在抽屉内部滚动，避免图片数量多时拉长整个任务页。
- Sprint 03 人物参考图进入实现：任务创建增加“使用参考人物”开关；数据库新增任务人物、人物外形阶段、panel 人物引用关系；worker 增加人物提取、人物参考图生成和带人物引用的 panel prompt 生成流程；任务详情只展示人物参考图、姓名和阶段。
- Sprint 04 故事方案模式已调整为直接 storyboard planning：任务创建保留“完整故事/故事方案”输入模式；故事方案模式不再先扩写完整故事再 chunk，而是一次 LLM 直接输出标题、钩子、规划概要、封面/剧情 panel、画面 prompt、图片内文字和文字布局；完整故事模式继续走切分后图文设计。
- 生图最终 prompt、风格测试 prompt 和人物参考图 prompt 已改为 Markdown 模板渲染，Python 代码只负责传入结构化变量和确定性参考图顺序。
- panel 和 generated image 增加图片内文字 JSON 与文字布局字段，用于保存当前设计与每次生成版本的快照；任务详情补充展示图片文字和文字布局，方便排查 prompt 质量。
- 收紧故事方案 storyboard prompt：当用户用“图1、图2...”明确列出画面时，默认输出 1 张封面 + 原始编号剧情图；没有明确台词时不再代写对白。人物提取 prompt 进一步要求稳定、确定的人物视觉锚点，避免参考人物缺乏辨识度。
- 修正人物参考拆分规则：人物只在不同年龄阶段拆不同 appearance，情绪、动作、失败、焦虑、幻想、石化等都作为同一人物的状态处理；最终生图 prompt 去掉 DoodleStory/Markdown 文档标题，改成更接近画师创作指令，并允许为“问话、回答、说话”等动作补充简短人物对白。
- 为人物提取增加代码层归一化：LLM 即使按愤怒、焦虑、幻想等状态拆出多个 appearance，后端也会按童年/少年/青年/成年/中年/老年等年龄阶段合并，人物参考图只保留稳定身份外观。
- 调整故事方案和生图 prompt 风格：故事方案 prompt 从工程化字段规则改为“故事导演分镜”口吻，允许每格按剧情自然选择旁白、对白、强调或留白；最终生图、风格测试和人物参考图 prompt 去掉 Markdown 任务书结构，改为自然画师指令，并让图片文字只绘制引号内内容。
- 放宽故事方案和分镜 prompt 的创作边界：允许 LLM 围绕用户粗略想法主动补足冲突、反差、情绪推进、短对白和旁白钩子，避免因过度限制导致故事性不足；新增内容只要求服务主线和人物关系，不把故事带偏。
- 精简最终生图 prompt：参考图说明缩短为“人物参考（参考图N）/风格参考（参考图N）”；最终 prompt 不再使用 emphasis；对白会从“人物：台词”转换为“人物说：台词”，并提示气泡中只绘制台词本身；旁白定位调整为补充前因后果和剧情信息，而不是复述画面状态。

## 验证记录

- harness 适配后，`./scripts/check.sh` 通过。
- 产品设计文档完成后，`./scripts/check.sh` 通过。
- 产品设计文档中文化后，`./scripts/check.sh` 通过。
- 用户和模型模块设计调整后，`./scripts/check.sh` 通过。
- 风格模型名和本地文件存储设计调整后，`./scripts/check.sh` 通过。
- 故事方案 storyboard planning 与 Markdown prompt 模板调整后，`./scripts/check.sh` 通过。
- 故事方案显式图号与人物锚点 prompt 修正后，`./scripts/check.sh` 通过；用“老板和男孩办公室对话”固定 10 张场景手动验证第一步返回 10 个 panels，且第 1 个为封面。

## 已知缺口

- 当前 React/FastAPI 代码仍是骨架，尚未达到产品设计完整要求。
- 任务创建、任务详情、取消、下载、完整 worker 流程尚未实现。
- 风格测试真实生图尚未实现，当前仍会明确返回 Provider 未接入错误，避免产生 Mock 结果。
- LLM 客户端和 prompts 已实现，但尚未接入任务 worker 流程。
- 任务 worker 已接入 LLM 和 XG 客户端，基础任务详情、批量下载和预览已完成；更精细的运行中恢复策略、单图下载入口和更系统的组件拆分仍可继续完善。
- 对象存储第一版继续本地磁盘，七牛作为可选 `StorageBackend` 尚未实现。
- 旧的多 profile registry 已移除；SiliconFlow、XG 图片编辑接口与 ApexerAPI Chat 生图接口按固定平台配置接入。
- UI 已开始切换到 Runway / Creative AI Studio 风格，但任务页、详情页和整体组件拆分仍需继续深化。

## 建议下一步

1. 继续做组件拆分，把当前 `frontend/src/main.tsx` 拆成页面、组件和 API 模块。
2. 补充更细的自动化测试和任务 worker 运行恢复策略。
3. 用真实 SiliconFlow 与 XG 配置跑一条完整端到端任务，校验真实生成质量。
