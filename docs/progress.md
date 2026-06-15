# 进度记录

## 当前基线

- 分支：`main`
- Harness 状态：`active`
- 产品：`DoodleStory`，文本转图片故事生成项目
- 最近验证状态：QY 图片接口尺寸参数修复后，`./scripts/check.sh` 通过。

## 当前 Sprint 合同

- `docs/contracts/sprint-48-user-character-management.md`

## 最近完成的工作

- 新增 DoodleStory 增长诊断与内容迭代上下文包：项目内增加 `.agents/skills/doodlestory-growth-diagnosis/SKILL.md`，用于在 DoodleStory 仓库内按 dbs-diagnosis 体检框架继续诊断产品增长、定价、内容实验和小红书获客；新增 `docs/strategy/doodle-growth-diagnosis.md`、`docs/product/content-iteration-system.md`、`docs/experiments/content-iteration-cycle-template.md` 和 `docs/growth/xiaohongshu/content-strategy.md`，把“图文账号内容迭代实验系统”的定位、实验闭环、售卖边界、复盘模板和获客内容策略沉淀到仓库，不再依赖聊天上下文。
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
- 开始 Sprint 05 性能优化：任务列表接口改为轻量摘要，不再返回完整 panels、steps、generated_images、人物参考和下载记录；前端列表页不再自动拉取第一条任务详情，列表预览图改用缩略图变体。
- 接入可配置存储后端：`STORAGE_BACKEND=local` 保持本地存储；`STORAGE_BACKEND=qiniu` 时新资产写入七牛对象存储，并向前端返回固定公开 CDN 原图 URL 或 `imageView2` 缩略图 URL；本地历史资产按需生成 WebP 缩略图。
- 调整故事方案和生图 prompt 风格：故事方案 prompt 从工程化字段规则改为“故事导演分镜”口吻，允许每格按剧情自然选择旁白、对白、强调或留白；最终生图、风格测试和人物参考图 prompt 去掉 Markdown 任务书结构，改为自然画师指令，并让图片文字只绘制引号内内容。
- 放宽故事方案和分镜 prompt 的创作边界：允许 LLM 围绕用户粗略想法主动补足冲突、反差、情绪推进、短对白和旁白钩子，避免因过度限制导致故事性不足；新增内容只要求服务主线和人物关系，不把故事带偏。
- 精简最终生图 prompt：参考图说明缩短为“人物参考（参考图N）/风格参考（参考图N）”；最终 prompt 不再使用 emphasis；对白会从“人物：台词”转换为“人物说：台词”，并提示气泡中只绘制台词本身；旁白定位调整为补充前因后果和剧情信息，而不是复述画面状态。
- 调整风格提示词作用层级：任务生成链路中的 style prompt 进入 LLM system prompt，用于影响 storyboard、panel prompt、人物提取和单图修改的风格化设计；最终 panel 生图 prompt 不再直接拼接原始 style prompt，而是输出已经风格化后的自然分段提示词。
- SiliconFlow 文本 LLM 调用开始显式传入 temperature，默认 `SILICONFLOW_TEMPERATURE=0.8`，用于增强故事方案和分镜生成的创作弹性。
- 进一步简化最终生图 prompt：移除独立排版段和独立人物对白段，最终 prompt 只保留参考、画面比例、画面和图片文字；人物动作、状态和对白统一融合进画面段，图片文字只承载封面标题、旁白、字幕或画外信息。
- 收紧完整故事模式的对白策略：完整故事的 panel prompt 不再允许在原文没有明显说话行为时新增人物对白，避免把旁白、情绪判断或金句改写成角色台词；故事方案模式仍保留围绕方案增强短对白的能力。
- 最终生图 prompt 的文字规则改为条件化：有对白时才写对白气泡规则；没有对白时明确禁止新增对白气泡或人物台词，避免图片模型自行补台词。
- 新增本地开发一键重启脚本 `scripts/restart-dev.sh`，可同时重启 FastAPI 后端和 Vite 前端，并输出 PID 与 `/tmp` 下的日志路径。
- 修复最终生图 prompt 对白规则冲突：条件化文字规则现在同时检查 `visual_prompt` 中的显式对白，不再只依赖 `image_text.dialogue`；无标题、旁白或字幕时的提示文案也改为更准确的“无标题、旁白或字幕”。
- 拆分完整故事和故事方案的文字生成责任：完整故事模式改为后端确定性断句，所有 panel 拼接后必须逐字等于原文；LLM 只生成画面 `visual_prompt`，图片内文字固定使用 panel 原文且不添加“旁白/字幕/标题”等标签。故事方案模式继续由 LLM 规划封面、剧情图、对白和旁白。
- 增强 prompt 链路诊断日志：新增统一 `prompt_trace` 单行 JSON 日志，记录 LLM 请求/响应、原始 JSON、结构校验、panel prompt 采纳、最终生图 prompt、人物参考图 prompt 和单 panel 修改链路；所有关键日志带 task_id、step、panel_id 或 generated_image_id，便于后续按任务复盘生成问题。
- 修复远程前端 API 地址推断：生产环境默认使用同源 `/api/v1` 走 nginx 代理，不再自动拼接公网主机的 `:8000` 端口；本地 loopback 开发仍默认请求 `http://127.0.0.1:8000`。
- 开始并完成 Sprint 36 七牛原图 URL 缓存污染修复：远程任务 `260d1c030dfb437480d9a51b28b8b6d8` 的生成图本地镜像和 xgapi 直连结果均为完整 `896x1200`，但对象存储公网 URL 返回 `320x568 image/webp`；进一步确认 `?imageInfo`、`?imageMogr2/format/jpg` 等 query 也命中同一份 WebP，判断为 CDN 忽略 query string 后由 `imageView2` 缩略图请求污染同 key 缓存。现已取消七牛资产 `thumbnail_url` 和 `thumbnail` 变体的同 key query 缩略图，统一返回无 query 原图 URL；历史已污染缓存可能仍需刷新 CDN、等待过期或生成新 key。
- 开始并完成 Sprint 37 内容提取公网 URL 视觉理解：下载素材登记资产仍使用原始文件 bytes，不做压缩、缩放或格式转换；图片和 metadata 资产保存/对象存储上传改为并行执行，完成后按原 display_order 写入数据库；图文 VL 请求改为按顺序传资产公网原图 URL，不再把图片转成 base64 data URL，没有公网 HTTP(S) URL 时明确失败。
- 开始并完成 Sprint 38 内容提取卡死状态恢复：内容提取仍使用同进程后台任务；后端启动时会扫描上一进程遗留的 `processing` 内容提取记录，将其标记为 `failed` 并写入“后端重启或进程中断”的明确原因，避免服务重启后列表长期卡在处理中。
- 开始并完成 Sprint 39 旧图片生成状态不污染任务详情：定位远程任务 `43a48af4739f4e0791965ba06070d12f` 已有 11 张当前成功图，但上一轮中断的 11 条非当前 `running` 图片版本仍残留；前端详情优先选择任意 running 导致已完成任务显示生成中。现已改为任务重试时作废旧运行中图片版本，前端只在任务运行中或用户单 panel 修改时展示 active 图片。
- 开始并完成 Sprint 40 Policy Blocked 生图切换百度模型：先用远程任务 `3564da7ea27e496bb30fdb608441e51c` 的 panel 9 同一 `final_prompt` 验证 `baidu/ERNIE-Image-Turbo` 无参考图真实生成成功；随后在正式 panel 生图和单 panel 修改生图中增加仅针对 Google policy blocked 类错误的模型切换，切换后不提交参考图，并把成功图片版本的模型快照写为实际使用的百度模型。
- 开始并完成 Sprint 41 Policy Blocked 后改写生图提示词：根据新需求替换 Sprint 40 的切模型策略；policy blocked 后不再切换 `baidu/ERNIE-Image-Turbo`，而是新增 LLM 改写 final prompt 步骤，在保留画面效果、图片内文字、原模型和原参考图的前提下，把容易触发策略的动作意图表达改为中性视觉状态，再用原模型重试一次。
- 开始 Sprint 06 抖音下载 Cookie 与导入适配：阅读 `jiji262/douyin-downloader` V2.0 的 Cookie 获取方式，确认官方推荐用浏览器登录保存 Cookie；当时新增 DoodleStory 后端临时直连 adapter 和命令行验证入口，用于先获取 Cookie 再输入抖音链接做真实下载验证。该临时路径后续已被独立 HTTP 下载服务取代。
- 新增内容提取需求设计：后续 `内容提取` tab 由后端解析抖音分享文本中的真实 URL，同步调用同机抖音下载服务下载图文或视频；下载后用户再同步触发文案提取，视频先分离音频并用 SiliconFlow 音频多模态转写，图文按图片顺序逐张用 SiliconFlow 视觉理解提取文字。该功能第一版不设计异步状态机、worker、轮询或取消流程，页面以最终文案为主，媒体预览为辅。
- 开始 Sprint 07 同步内容提取：新增合同 `docs/contracts/sprint-07-content-extraction.md`，范围锁定为后端同步下载服务代理、最小内容提取记录、SiliconFlow 图文/音频文案提取和前端 `内容提取` tab。
- 完成 Sprint 07 同步内容提取第一版：新增 `content_extractions` 和 `content_extraction_media` 表、内容提取 API、同机抖音下载服务代理、SiliconFlow 图文/音频多模态提取服务、内容提取资产权限和前端 `内容提取` tab；页面支持粘贴分享文本、同步解析下载、同步提取文案、复制结果、媒体预览和最近记录。
- 增强 `内容提取` 媒体预览交互：下载后的图片缩略图支持点击放大、键盘关闭、左右切换、下载单图和打开原图；视频仍保留内嵌播放器。
- 完成内容提取下一版 UI 设计：将页面重构为列表入口，创建任务和查看详情都使用弹窗；新增图文故事总结展示，包含故事内容、故事爆点和目标观众；明确列表页只加载摘要，不加载所有图片。
- 输出内容提取列表化 UI 三张效果图：列表页、创建任务弹窗和查看详情弹窗，作为 Sprint 08 后续实现的视觉参照。
- 完成 Sprint 08 内容提取列表化实现：新增一键同步处理接口，创建任务时完成抖音链接解析、下载、图文 OCR 或视频音频转写，并对图文作品生成故事内容、故事爆点和目标观众；前端 `内容提取` tab 已改为列表入口，创建任务和查看详情都使用弹窗，详情才加载完整媒体，列表只加载摘要。
- 调整内容提取创建交互：提交后先保存真实记录并在列表显示 `处理中`，后端在同进程后台继续下载、提取和总结；处理完成后列表刷新状态，不再自动弹出详情弹窗，用户从列表行手动查看详情。
- 清理主仓库内早期抖音直连下载临时代码：删除旧后端 adapter、Cookie 获取脚本和命令行下载验证脚本；移除旧环境变量说明与本地配置项。当前 DoodleStory 只通过 `backend/app/services/douyin_import_service.py` 调用独立 HTTP 下载服务，地址由 `DOUYIN_IMPORT_SERVICE_BASE_URL` 指定。
- 开始并完成 Sprint 09 内容提取下载先展示与本地 OCR：新增合同 `docs/contracts/sprint-09-content-extraction-fast-media-ocr.md`；后台任务改为下载媒体登记后立即提交、OCR 后再次提交、故事总结完成后标记成功；图文 OCR 改用 `rapidocr-onnxruntime` 本地 Python SDK，只有故事总结继续调用 SiliconFlow 视觉模型；前端创建提示同步说明“下载完成先显示媒体，本地 OCR 提取文字，AI 总结故事”。
- 开始并完成 Sprint 10 工作台二级路径路由：新增合同 `docs/contracts/sprint-10-stable-workspace-routes.md`；前端主工作台从内存态 tab 切换改为 URL 驱动，任务、内容提取、风格和设置页面分别使用 `/tasks`、`/content-extractions`、`/styles` 和 `/settings`，侧边栏改为真实导航链接，刷新和浏览器前进后退会保留当前页面。
- 开始并完成 Sprint 11 内容提取使用下载原始媒体：新增合同 `docs/contracts/sprint-11-content-extraction-source-media.md`；远程故障排查确认任务 `5b7cb28b10224ab8843c23b4441e24d8` 在旧代码中因 `cdn.vdgen.shop` 读取超时失败，失败发生在下载成功后的 OCR/处理阶段，旧事务回滚导致媒体记录不可见；内容提取 OCR、图文故事总结和视频转写改为直接使用下载服务返回的 `source_path` 本地原始媒体，不再为了处理流程从对象存储公开 CDN 回拉刚下载的媒体。
- 开始并完成 Sprint 12 风格创建参考图上传：新增合同 `docs/contracts/sprint-12-style-create-reference-upload.md`；风格创建抽屉现在直接展示参考图区域，新建时可先选择多张参考图并显示文件名，创建风格成功后自动按顺序上传到新风格；编辑风格保留原有即时上传和删除参考图能力。
- 细化 Sprint 12 创建态上传交互：新建风格时不再在参考图标题右侧显示上传按钮，参考图区大空白框本身就是文件选择入口，选中文件后仍在同一区域显示数量和文件名。
- 开始并完成 Sprint 13 SiliconFlow 生图模型路由：新增合同 `docs/contracts/sprint-13-siliconflow-image-generation-routing.md`；`Qwen/Qwen-Image-Edit-2509`、`Qwen/Qwen-Image-Edit`、`baidu/ERNIE-Image-Turbo` 和 `Qwen/Qwen-Image` 已精确路由到 SiliconFlow `/v1/images/generations`，并保持返回 URL 立即下载入库；其它模型继续走原有 ApexerAPI 或 XG 路径。
- 开始并完成 Sprint 14 任务详情稳定 URL 与本地打包下载：新增合同 `docs/contracts/sprint-14-task-detail-route-local-download.md`；任务详情 URL 使用 `/tasks/{task_id}`，任务图片下载按钮增加打包中状态，下载 zip 改为只读取服务器本地已有资产文件，zip 本身固定保存为本地资产；七牛新写入资产会同时保留服务器本地镜像，便于后续本地处理和打包。
- 开始并完成 Sprint 15 取消任务重试上限与 panel 生图并发：新增合同 `docs/contracts/sprint-15-unlimited-retry-image-concurrency.md`；任务级手动重试不再受 `attempts >= max_attempts` 阻止，`attempts` 继续保留用于排查；任务 `generate_images` 阶段改为按 `IMAGE_GENERATION_CONCURRENCY` 有限并发提交 panel 生图请求，默认并发 3。
- 开始并完成 Sprint 16 任务创建弹窗与风格宫格选择：新增合同 `docs/contracts/sprint-16-task-create-modal-style-grid.md`；任务创建从侧边抽屉改为居中弹窗，完整故事/故事方案改为带说明的点击选择，使用参考人物默认勾选并移动到风格前，图片数量也前置，风格选择改为紧凑宫格并支持展开二级弹窗选择更多风格。
- 开始并完成 Sprint 17 生图 timeout 自动重试：新增合同 `docs/contracts/sprint-17-image-timeout-retry.md`；新增 `IMAGE_PROVIDER_TIMEOUT_RETRY_ATTEMPTS=3` 配置，生图请求和结果图下载遇到 timeout 时最多自动重试 3 次，成功即停止；非 timeout 错误不使用 timeout 专用重试次数。
- 开始并完成 Sprint 18 任务 worker 并发：新增合同 `docs/contracts/sprint-18-task-worker-concurrency.md`；任务队列启动时按 `TASK_WORKER_CONCURRENCY` 创建进程内 worker 池，默认 3 个 worker 并发领取任务；同一进程内同一个任务 ID 重复入队时不会并发执行两次，单任务内 panel 生图并发仍由 `IMAGE_GENERATION_CONCURRENCY` 单独控制。
- 开始并完成 Sprint 19 七牛资产本地镜像优先读取：新增合同 `docs/contracts/sprint-19-qiniu-materialize-local-mirror.md`；远程任务 `bec1e4f7dda144278b4254bf4eba4d7d` 失败原因确认是正式生图前准备人物参考图时，`materialize_asset_to_local()` 未优先使用已存在的服务器本地镜像，转而从 `cdn.vdgen.shop` 回拉七牛资产并读超时；现已改为七牛资产优先读取本地镜像，再读取已有缓存，最后才保留历史 CDN 下载路径。
- 开始并完成 Sprint 20 模板编辑入口与图片模型输入：新增合同 `docs/contracts/sprint-20-template-edit-actions.md`；模板卡片标题区直接展示“编辑模板”按钮，模板表单中的图片模型继续保持用户手动填写的文本输入，并补充“不使用下拉选择”的说明。
- 开始并完成 Sprint 21 故事方案用户要求优先级：新增合同 `docs/contracts/sprint-21-story-brief-priority.md`；故事方案 storyboard prompt 明确 `brief_text` 是最高创作约束，用户要求与风格规则、默认分镜方法或剧情增强建议冲突时优先满足用户需求，并强化上下分区、左右分区、分屏、单页构图、字体大小、必须出现和不要出现等要求必须进入对应 panel 设计。
- 开始并完成 Sprint 22 QNY 公开访问域名配置：新增合同 `docs/contracts/sprint-22-qny-public-base-url.md`；对象存储新增 `QNY_PUBLIC_BASE_URL` 和 `QNY_USE_HTTPS` 配置，本地 `.env` 切换到 `QNY_BUCKET=video-space001`、`QNY_PUBLIC_BASE_URL=http://tg721n1on.hn-bkt.clouddn.com`、`QNY_USE_HTTPS=false`，同时保留 `QINIU_BUCKET_DOMAIN` 和历史 `QNY_DOMAIN` 兼容。
- 开始并完成 Sprint 23 内容提取漫画逐页识别：新增合同 `docs/contracts/sprint-23-content-extraction-comic-vision-llm.md`；图文内容提取从本地 OCR 改为 SiliconFlow 视觉模型逐页提取漫画页内容，提示词要求逐字保留旁白、对话和内心 OS，并输出画面描述与分格信息；全部逐页结果合并后再调用 SiliconFlow 文本 LLM 做最终整理，最终写入详情弹窗的 `内容提取` 主结果区。
- 开始并完成 Sprint 24 调试过程日志：新增合同 `docs/contracts/sprint-24-debug-process-logs.md`；内容提取链路增加 `content_extraction_debug` 日志，覆盖任务创建、抖音下载、媒体登记、图文提取、视频转写和后台失败；内容提取 AI 交互增加 `content_extraction_ai_debug` 日志，记录模型 prompt、图片/音频输入摘要、AI 返回内容和最终提取结果，并固定写入 `backend/logs/local-backend.log`；故事画图链路增加 `story_drawing_debug` 日志，覆盖任务开始、分镜、人物识别、人物参考、panel prompt、final prompt、Provider 请求、单图结果和任务完成。
- 开始并完成 Sprint 25 内容提取整组图文顺序理解：新增合同 `docs/contracts/sprint-25-content-extraction-ordered-gallery.md`；纠正 Sprint 23 的逐张视觉调用方案，图文内容提取改为把同一作品全部图片按 `display_order` 顺序一次性提交给 SiliconFlow 视觉模型，要求模型结合前后页上下文并按页输出旁白、对话、内心 OS、画面描述和分格信息；该步骤替代旧的图文故事总结步骤，后台处理不再生成 `故事内容`、`故事爆点`、`目标观众`，前端详情只展示 `内容提取` 主结果。
- 开始 Sprint 26 内容提取结果提交为分镜生图任务：新增合同 `docs/contracts/sprint-26-content-extraction-to-task.md`；内容提取详情增加 `提交任务`，跳转任务创建并预填内容提取结果；任务创建增加第三种 `提取分镜` 模式，后端只把内容提取结果结构化为 panels，不走故事方案的二次创作。
- 开始 Sprint 27 统一生图 Gateway 接入：新增合同 `docs/contracts/sprint-27-unified-image-gateway.md`；根据 `docs/api_v3.md` 把已同意的 10 个当前可用生图模型统一接入 OpenAI Images 兼容 `/v1/images/generations`，新增 `IMAGE_GATEWAY_BASE_URL` 和 `IMAGE_GATEWAY_API_KEY` 配置，响应同时兼容 `data[0].url` 和 `data[0].b64_json`，未列入清单的模型改为明确配置错误，不再默认走旧 XG、ApexerAPI Chat 或 SiliconFlow 直连接口。
- 开始 Sprint 28 提示词风格控制与参考图展示化：新增合同 `docs/contracts/sprint-28-prompt-style-control.md`；风格参考图继续保留为风格样张、封面和管理资产，但不再作为风格测试、人物参考图生成、任务 panel 生图或单 panel 修改的 provider 输入；实际风格控制由风格模板提示词承担，开启人物参考时 provider 请求只携带人物参考图。

## 验证记录

- harness 适配后，`./scripts/check.sh` 通过。
- 产品设计文档完成后，`./scripts/check.sh` 通过。
- 产品设计文档中文化后，`./scripts/check.sh` 通过。
- 用户和模型模块设计调整后，`./scripts/check.sh` 通过。
- 风格模型名和本地文件存储设计调整后，`./scripts/check.sh` 通过。
- 故事方案 storyboard planning 与 Markdown prompt 模板调整后，`./scripts/check.sh` 通过。
- 故事方案显式图号与人物锚点 prompt 修正后，`./scripts/check.sh` 通过；用“老板和男孩办公室对话”固定 10 张场景手动验证第一步返回 10 个 panels，且第 1 个为封面。
- 任务列表与对象存储性能改造后，`python3 -m compileall backend/app`、`npm run build` 和 `./scripts/check.sh` 通过。
- 七牛配置兼容 `QNY_*` 前缀后，用本地 `.env` 中的 QNY 配置完成真实烟测：临时启用 `STORAGE_BACKEND=qiniu` 上传测试 PNG 成功，固定原图 CDN URL 返回 `200 image/png`，固定 `imageView2` 缩略图 URL 返回 `200 image/webp`，烟测对象已从七牛删除。
- 七牛资产访问改为前端直接使用 `file_assets.public_url` 派生出的固定公开 CDN URL，避免短期签名 URL 造成浏览器缓存命中差；后端 `/assets/{id}/content` 仅保留本地资产访问和七牛固定 URL 兼容跳转。
- 抖音图文链接 `https://v.douyin.com/Vcpjpg3pcMk/` 已用外部下载器做无 Cookie 烟测：短链可解析为 `https://www.douyin.com/note/7578551127650620323?previous_page=web_code_link`，类型识别为 `gallery`，但详情接口连续返回空 `200`，下载器判断为反爬信号，未产生媒体文件。后续需配置有效 Cookie 后复测。
- 按外部下载器官方流程打开浏览器登录抖音并保存 Cookie 后，通过早期临时命令行入口成功下载图文作品 `https://v.douyin.com/Vcpjpg3pcMk/`，产出 5 个媒体文件和 `download_manifest.jsonl`。该临时入口已在后续清理中移除，当前下载能力由独立 HTTP 服务提供。
- Sprint 07 同步内容提取后，`python3.11 -m compileall backend/app`、空 SQLite 数据库 Alembic `upgrade head`、`npm run build` 和 `./scripts/check.sh` 通过；用临时本地前后端服务在浏览器中注册测试账号并打开 `内容提取` tab，页面可正常加载并在 `127.0.0.1:8010` 不可达时显示明确错误。
- 内容提取图片放大预览增强后，`npm run build` 和 `./scripts/check.sh` 通过；临时启动本地前后端与同机抖音下载服务，用真实图文链接 `https://v.douyin.com/Vcpjpg3pcMk/` 下载 5 张图片，浏览器验证第 1 张缩略图可打开预览、可切换到第 2 张、Esc 可关闭。
- Sprint 08 内容提取列表化实现后，`./scripts/check.sh` 通过；临时启动本地前后端，使用真实图文分享文本中的 `https://v.douyin.com/Vcpjpg3pcMk/` 调用一键处理接口成功，结果为 `gallery`，登记 5 张图片和 1 个 metadata，生成原始文案与三段故事总结；浏览器验证列表页、创建弹窗和详情弹窗布局，详情内多图默认折叠且缩略图加载成功。
- 内容提取提交即入列表调整后，`./scripts/check.sh` 通过；本地页面提交真实图文分享文本后，创建弹窗立即关闭，列表顶部立刻出现 `处理中` 记录，且没有自动弹出详情弹窗。
- 抖音直连下载临时代码清理后，`python3.11 -m compileall backend/app` 和 `./scripts/check.sh` 通过；本地后端已通过 LaunchAgent 重启并监听 `127.0.0.1:8000`，`curl -sS http://127.0.0.1:8000/health` 返回 `{"status":"ok"}`；独立抖音下载服务 `127.0.0.1:8010` 健康检查也返回 `status=ok`。
- Sprint 09 本地 OCR 与分阶段提交实现后，`python3.11 -m compileall backend/app`、`npm run build` 和 `./scripts/check.sh` 通过；本地重启后端并用真实图文链接 `https://v.douyin.com/XQ5ncKT0UAo/` 验证分阶段可见性：任务仍为 `processing` 时媒体数量先从 0 变为 14，随后 `extracted_text` 先于故事总结写入，最终任务变为 `succeeded` 且故事总结正常生成。
- Sprint 10 工作台二级路径路由实现后，`npm run build` 和 `./scripts/check.sh` 通过；本地浏览器使用测试账号验证 `/content-extractions` 刷新后仍显示内容提取页面，点击进入 `/styles` 后刷新仍显示风格页面，浏览器后退回到内容提取、前进回到风格时页面标题和地址均保持同步。
- Sprint 11 内容提取使用下载原始媒体实现后，`./scripts/check.sh` 通过；远程诊断已确认 `doodlestory-backend.service` 正常运行、`douyin-import-service.service` 正常运行且目标下载请求返回 200，`127.0.0.1:7890` 代理进程存在但经代理访问 `cdn.vdgen.shop` 出现 TLS EOF，直连 CDN 可返回但较慢。修复方向是不让内容提取处理依赖 CDN 回读。
- Sprint 12 风格创建参考图上传实现后，`npm run build` 和 `./scripts/check.sh` 通过；本地浏览器打开 `/styles`，点击“新建风格”后确认创建抽屉中展示“参考图”区域、“选择图片”按钮和创建态参考图说明。
- Sprint 12 创建态上传投放区细化后，`npm run build` 和 `./scripts/check.sh` 通过；本地浏览器打开 `/styles`，点击“新建风格”后确认创建态参考图标题右侧不再显示小上传按钮，参考图区大空白框展示“点击这里上传参考图”并包含文件选择输入。
- Sprint 13 SiliconFlow 生图模型路由实现后，使用后端虚拟环境运行单元级 smoke：确认 `Qwen/Qwen-Image-Edit-2509` payload 不传 `image_size` 且使用 `image/image2/image3`，确认 `Qwen/Qwen-Image` 使用 `928x1664` 等官方推荐尺寸和 `cfg=4`，确认 SiliconFlow `images[0].url` 会进入下载路径；随后 `backend/.venv/bin/python -m compileall backend/app` 和 `./scripts/check.sh` 通过。
- Sprint 14 任务详情稳定 URL 与本地打包下载实现后，`npm run build`、`backend/.venv/bin/python -m compileall backend/app`、`git diff --check` 和 `./scripts/check.sh` 通过；本地重启前后端后使用 Playwright 验证：点击任务行后地址进入 `/tasks/36b58bfb4a1642698b34b288e160bb1c`，刷新仍保持同一任务详情，关闭详情回到 `/tasks`；点击下载生成 `doodlestory-36b58bfb4a1642698b34b288e160bb1c.zip`，最新 `task_downloads` 记录对应 `file_assets.storage_backend=local`，zip 内包含 4 张 panel 图片，浏览器下载请求走本地后端 `/api/v1/assets/{asset_id}/content`。
- Sprint 15 取消任务重试上限与 panel 生图并发实现后，`backend/.venv/bin/python -m compileall backend/app` 和 `./scripts/check.sh` 通过；静态检查确认后端已移除“任务已达到最大重试次数”错误分支；单元级 smoke 用 5 个模拟 panel 请求验证默认 `IMAGE_GENERATION_CONCURRENCY=3` 时最大同时执行请求数为 3，且不会触发真实图片 Provider。
- Sprint 16 任务创建弹窗与风格宫格选择实现后，`npm run build`、`./scripts/check.sh` 和 `git diff --check` 通过；浏览器验证创建任务弹窗、默认参考人物勾选、紧凑风格宫格与二级风格选择弹窗。
- Sprint 17 生图 timeout 自动重试实现后，`backend/.venv/bin/python -m compileall backend/app`、`./scripts/check.sh` 和 `git diff --check` 通过；单元级 smoke 模拟 SiliconFlow 连续 3 次 `ReadTimeout` 后第 4 次成功，确认 timeout 会使用首尝试 + 3 次重试；模拟非 timeout `ConnectionError` 时确认不会使用 timeout 专用 4 次尝试。
- Sprint 18 任务 worker 并发实现后，`backend/.venv/bin/python -m compileall backend/app`、`./scripts/check.sh` 和 `git diff --check` 通过；单元级 smoke 模拟 5 个任务入队，确认默认 `TASK_WORKER_CONCURRENCY=3` 时最大同时执行任务数为 3。
- Sprint 19 七牛资产本地镜像优先读取实现后，`backend/.venv/bin/python -m compileall backend/app`、`./scripts/check.sh` 和 `git diff --check` 通过；单元级 smoke 构造七牛资产和本地镜像，禁用 `requests.get` 后确认 `materialize_asset_to_local()` 直接返回本地镜像路径，不访问公开 CDN。
- Sprint 20 模板编辑入口与图片模型输入实现后，`npm run build --prefix frontend`、`./scripts/check.sh` 和 `git diff --check` 通过；构建产物确认 `/styles` 模板卡片标题行包含“编辑模板”，编辑弹窗里的图片模型字段是文本输入框并显示手动填写说明。
- Sprint 21 故事方案用户要求优先级实现后，`./scripts/check.sh` 和 `git diff --check` 通过；静态检查确认故事方案 prompt 已把用户输入提升为最高创作约束，并声明用户需求与风格或默认创作建议冲突时优先用户需求。
- Sprint 22 QNY 公开访问域名配置实现后，`./scripts/check.sh` 和 `git diff --check` 通过；本地使用新 `video-space001` Bucket 做真实七牛烟测，上传测试 PNG 成功，固定 HTTP 原图 URL 返回 `200 image/png`；固定 HTTP `imageView2` 和 `imageMogr2` 处理 URL 也返回 `200`，但新公开域名当前返回的仍是原始 `image/png`，未应用 WebP 或缩放处理，测试对象随后已从七牛删除。
- Sprint 23 内容提取漫画逐页识别实现后，`backend/.venv/bin/python -m compileall backend/app`、`npm run build --prefix frontend`、`git diff --check` 和 `./scripts/check.sh` 通过；本次未调用真实 SiliconFlow/抖音下载服务做端到端验证。
- Sprint 24 调试过程日志实现后，`backend/.venv/bin/python -m compileall backend/app`、`git diff --check` 和 `./scripts/check.sh` 通过；本地重启后端确认 `backend/logs/local-backend.log` 会写入启动日志。本次未调用真实内容提取或故事生图任务。
- Sprint 25 内容提取整组图文顺序理解实现后，`backend/.venv/bin/python -m compileall backend/app`、`npm run build --prefix frontend`、`git diff --check` 和 `./scripts/check.sh` 通过；本次完成本地服务重启前的静态与构建验证，尚未用真实抖音漫画链接调用 SiliconFlow 做端到端验证。
- Sprint 26 内容提取结果提交为分镜生图任务实现后，`backend/.venv/bin/python -m compileall backend/app`、`npm run build --prefix frontend`、`git diff --check` 和 `./scripts/check.sh` 通过；本地前后端已重启，后端 `/health` 返回 `{"status":"ok"}`，前端 `127.0.0.1:3000` 返回 `200 OK`；尝试用 Playwright 做浏览器自动化烟测时当前 Node REPL 环境缺少 `playwright` 包，因此未完成真实浏览器点击验证。
- Sprint 27 统一生图 Gateway 接入后，单元级 smoke 验证 `gpt-image-2` payload 会使用 `1024x1792` 和 `images` data URL，`data[0].b64_json` 与 data URL 形式的 `data[0].url` 均可解析为图片字节，未列入清单的 `nano-banana` 会明确返回“未接入统一 Gateway”；随后 `backend/.venv/bin/python -m compileall backend/app`、`git diff --check` 和 `./scripts/check.sh` 通过。本次未调用真实远端生图接口，避免在未显式配置运行时 API Key 时产生外部调用。
- Sprint 28 提示词风格控制实现后，`backend/.venv/bin/python -m compileall backend/app`、`npm run build --prefix frontend`、`git diff --check` 和 `./scripts/check.sh` 通过；单元级 smoke 确认 `gpt-image-2` 无参考图 payload 不包含 `images` 字段，空 panel 参考包返回空路径和空说明。本次未调用真实远端生图接口，避免消耗外部额度。
- 统一生图 Gateway 非 Gemini 模型真实远端验证后，使用 `docs/api_v3.md` 中的统一入口和测试 Key，按当前代码路径分别调用 `gpt-image-2`、`Tongyi-MAI/Z-Image`、`Qwen/Qwen-Image` 和 `baidu/ERNIE-Image-Turbo`，四个模型均成功返回 `image/png` 图片字节；实测耗时分别约 43.23 秒、15.87 秒、41.73 秒和 9.80 秒，响应均带 provider request id。本次未打印 API Key、完整图片 URL 或 base64 内容，也未把生成图片保存到仓库。
- 修复提取分镜/故事方案最终生图 prompt 遗漏对白内容的问题：`image_text.dialogue` 现在会进入“需要写入图片的文字”块，和旁白、内心 OS 分开标注，确保图片模型收到具体对白文本而不只是对白气泡规则；新增后端单测覆盖“旁白 + 多行对白”的 final prompt 组装，并接入 `./scripts/check.sh`。
- 收紧任务完成和下载状态：图片生成只有所有 panel 都生成当前成功图时才保持 `succeeded` 并允许打包下载；部分成功会停留在 `partial_succeeded`，进度不再显示满格，并记录“成功 X / 共 Y 张”的错误信息。下载接口现在重新校验每个 panel 的当前成功图，前端下载按钮也只在全部分镜图片生成后启用。
- 调整正式 panel 最终生图 prompt 的文字规则块：去掉代码固定拼接的“不要添加指定文字之外的任何文字、Logo 或水印”等硬禁止项，保留旁白、对白和内心 OS 的正向呈现说明，减少规则块压制画面风格和场景灵活性的情况。
- 完成 Sprint 29 Gateway 失败后的 XG 备用生图：新增合同 `docs/contracts/sprint-29-xg-image-fallback.md`；统一生图 Gateway 仍是主路径，Provider 响应错误在既有重试耗尽后会显式切到 XG 备用 provider；无参考图调用 XG `/v1/images/generations`，有参考图调用 XG `/v1/images/edits`，多参考图按重复 `image` form part 上传，备用模型由 `XG_FALLBACK_IMAGE_MODEL` 配置。
- Sprint 29 XG 备用生图实现后，`PYTHONPATH=backend backend/.venv/bin/python -m unittest discover -s backend/tests`、`backend/.venv/bin/python -m compileall backend/app`、`npm run build --prefix frontend`、`git diff --check` 和 `./scripts/check.sh` 通过；单元测试确认 Gateway Provider 响应错误会进入 XG fallback，Gateway 配置错误不会进入 XG fallback，无参考图 payload 使用 XG generations 的 JSON `response_format=url`，多参考图 edit 使用重复 `image` form part。
- 开始并完成 Sprint 30 生图只使用统一平台：新增合同 `docs/contracts/sprint-30-unified-image-platform-only.md`；根据 `docs/api_v4.md` 扩展统一平台模型白名单，新增 `gpt-image-2(线路XF)`、`gr-image-2`、`nano-banana`、`nano-banana-hd` 和 `nano-banana-pro`；移除 DoodleStory 后端 Gateway 失败后直连 XG 的兜底逻辑，Provider 响应错误在统一平台重试耗尽后直接失败并暴露原因。
- 开始并完成 Sprint 31 最终生图 Prompt 拼接风格提示词：新增合同 `docs/contracts/sprint-31-final-prompt-style-injection.md`；正式任务 panel 生图和单 panel 修改的 final prompt 现在都会把任务保存的 `style_prompt_snapshot` 作为独立风格提示词段拼接到参考图说明之后、画面比例之前，增强图片模型端的直接风格约束。
- 开始并完成 Sprint 32 风格删除与图片预览加载态：新增合同 `docs/contracts/sprint-32-style-delete-and-preview-loading.md`；风格删除改为无历史引用时物理删除、有历史任务或测试引用时软删除并从列表隐藏；图片懒加载组件在 URL 切换时重置为空白加载态，避免预览文字已切换但图片仍显示上一张。核对发现本地已使用国内对象存储 `video-space001`，远程仍是旧 bucket/domain，本次部署时同步切到国内对象存储。
- 开始并完成 Sprint 33 人物参考图拼接风格提示词：新增合同 `docs/contracts/sprint-33-character-reference-style-injection.md`；人物参考图 prompt 将任务保存的 `style_prompt_snapshot` 作为独立风格提示词段放在人物比例和外观设定之前，强化角色参考图自身的画风一致性；`PYTHONPATH=backend backend/.venv/bin/python -m unittest discover -s backend/tests`、`backend/.venv/bin/python -m compileall backend/app`、`git diff --check` 和 `./scripts/check.sh` 通过。
- 开始并完成 Sprint 34 QY 参考图公网 URL 字段格式：新增合同 `docs/contracts/sprint-34-qy-reference-url-fields.md`；统一生图 Gateway 的人物参考图请求改为直接提交资产公网 URL，并按 `image`、`image2`、`image3` 独立字段组织，不再把参考图转成 base64 data URL 或放入 `images` 数组；`PYTHONPATH=backend backend/.venv/bin/python -m unittest discover -s backend/tests`、`backend/.venv/bin/python -m compileall backend/app`、`npm run build --prefix frontend`、`git diff --check` 和 `./scripts/check.sh` 通过。
- 开始并完成 Sprint 35 显式生图 Provider 切换：新增合同 `docs/contracts/sprint-35-explicit-image-provider-switch.md`；通过 `IMAGE_PROVIDER=qy|xgapi` 显式选择生图 provider，QY 保持公网 URL + `image/image2/image3` 逻辑，xgapi 使用独立 adapter，无参考图走 generations JSON，有参考图走 edits JSON，参考图使用 `image` 公网 URL 数组；两边参考图都直接使用资产公网 URL，不下载本地文件也不转 base64；新增 `scripts/switch-image-provider.sh` 用于隔离切换配置；`PYTHONPATH=backend backend/.venv/bin/python -m unittest discover -s backend/tests`、`backend/.venv/bin/python -m compileall backend/app`、`npm run build --prefix frontend`、`git diff --check` 和 `./scripts/check.sh` 通过。
- 修复 xgapi 多参考图公网 URL 提交方式：本地真实请求验证 `multipart image`、`image[]`、`image[0]/image[1]`、`images[]`、`image/image2` 以及 form URL 均返回 500，`/v1/images/edits` JSON `image: [url1, url2]` 返回 200；后端已改为该格式，单元测试同步覆盖。
- 调整内容提取分镜解析策略：`parse_extracted_storyboard_v1.md` 不再诱导 LLM 在 `visual_prompt` 或 `text_layout` 中输出画面比例，分镜解析只负责画面与分格信息，最终画面比例继续由风格 `aspect_ratio` 统一控制。
- Sprint 38 内容提取卡死状态恢复实现后，`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend/tests/test_content_extraction_media_flow.py`、`backend/.venv/bin/python -m compileall backend/app`、`git diff --check` 和 `./scripts/check.sh` 通过。
- Sprint 39 旧图片生成状态修复实现后，`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend/tests/test_task_download_state.py`、`backend/.venv/bin/python -m compileall backend/app`、`npm run build --prefix frontend`、`git diff --check` 和 `./scripts/check.sh` 通过。
- Sprint 40 Policy Blocked 生图切换实现前，远程真实验证 `3564da7ea27e496bb30fdb608441e51c` panel 9 使用 `baidu/ERNIE-Image-Turbo`、`reference_count=0` 成功返回 `image/jpeg`，耗时约 31.7 秒，provider request id 为 `202606080746462097348648268d9d6XlLSJ0fe`；实现后 `PYTHONPATH=backend backend/.venv/bin/python -m unittest backend/tests/test_task_worker_prompt.py`、`backend/.venv/bin/python -m compileall backend/app`、`git diff --check` 和 `./scripts/check.sh` 通过。
- Sprint 41 Policy Blocked 提示词改写实现后，`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend/tests/test_task_worker_prompt.py`、`backend/.venv/bin/python -m compileall backend/app`、`git diff --check` 和 `./scripts/check.sh` 通过。
- Sprint 42 风格参考方式实现后，新增 `prompt` / `image` 两种风格参考模式；旧数据默认保持 `prompt`；任务创建和重试会保存风格参考方式与参考图快照；正式 panel 生图、单 panel 修改和风格测试会按同一套参考方式传入 Prompt 或风格参考图。`PYTHONPATH=backend backend/.venv/bin/python -m unittest discover -s backend/tests`、空 SQLite Alembic `upgrade head`、`npm run build --prefix frontend`、`git diff --check` 和 `./scripts/check.sh` 通过；本地重启前后端后，浏览器验证 `/styles` 页面可见“Prompt 参考”，新建风格抽屉中可见“Prompt 参考 / 参考图参考”和公网 URL 说明。浏览器截图尝试两次均因 in-app browser `Page.captureScreenshot` 超时未保存。
- 开始并完成 Sprint 43 DY 爆款复刻一键创建任务：新增合同 `docs/contracts/sprint-43-dy-replication-task-create.md`；创建任务弹窗新增 `DY爆款复刻`，提交抖音分享文本后调用内容提取复刻接口，后端先下载素材并提取逐页内容，成功后复用普通任务创建服务自动创建 `story_input_mode=extracted_storyboard` 的生成任务并线程安全入队；内容提取记录新增关联任务 ID、自动创建状态和错误信息；前端轮询关联任务，创建成功后跳转 `/tasks/{task_id}`。`PYTHONPATH=backend backend/.venv/bin/python -m unittest discover -s backend/tests`、空 SQLite Alembic `upgrade head`、`npm run build --prefix frontend`、`git diff --check` 和 `./scripts/check.sh` 通过。
- 开始并完成 Sprint 44 用户积分、激活码与管理员使用管理：新增合同 `docs/contracts/sprint-44-user-credits-admin-usage.md`；已有用户通过迁移初始化 `1000` 积分，新用户注册默认 `30` 积分；新增积分账户、积分流水、激活码和兑换记录；成功产出图片扣 `1` 积分，正式任务、任务重试、单 panel 修改、人物参考图和风格测试都接入统一扣费 hook；Provider 失败会释放积分占用，积分不足时不调用 Provider；新增 `/credits` 与 `/admin` 积分管理 API；前端左下角展示积分余额，设置页支持用户兑换激活码，Admin 可查看用户使用情况、调整积分和生成激活码。`backend/.venv/bin/python -m compileall backend/app`、`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend/tests/test_credits.py`、`npm run build --prefix frontend`、`git diff --check` 和 `./scripts/check.sh` 通过；全量检查覆盖 34 个后端测试、空 SQLite Alembic `upgrade head` 和前端生产构建。本次未调用真实图片 Provider，扣费 hook 使用单元测试和构建验证覆盖。
- 补充 Sprint 44 管理体验：管理员用户管理从设置页拆到单独 `/users` tab，用户列表改为每页 10 条分页表格并支持搜索；用户管理页保留积分调整抽屉和生成激活码能力；设置页新增当前用户最近 `1` 天、`7` 天、`30` 天积分消耗折线图，后端新增 `/api/v1/credits/usage` 只统计成功扣费流水。`backend/.venv/bin/python -m compileall backend/app`、`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend/tests/test_credits.py`、`npm run build --prefix frontend`、`git diff --check` 和 `./scripts/check.sh` 通过；本地服务已通过 `./scripts/restart-dev.sh` 重启，浏览器验证管理员登录后 `/settings` 可见趋势图、`/users` 可见分页用户表和生成激活码入口。本地新增开发管理员账号 `admin@example.com` 用于登录烟测。
- 补充 Sprint 44 积分流水体验：`/credits/me` 不再默认加载最近流水，新增 `/credits/transactions` 分页接口；设置页最近积分流水默认只展示 `查看明细` 入口，用户点击后才按每页 10 条加载，并可用 `全部流水`、`消耗积分`、`重置积分` 快捷筛选。`消耗积分` 对应成功扣费流水，`重置积分` 对应管理员调整流水。`backend/.venv/bin/python -m compileall backend/app`、`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend/tests/test_credits.py`、`npm run build --prefix frontend`、`git diff --check` 和 `./scripts/check.sh` 通过。
- 补充 Sprint 44 管理员积分消耗大盘：新增管理员可见 `/credit-usage` tab，展示全站或按用户筛选的成功出图扣费汇总、最近 `1` 天按小时聚合、最近 `7` 天/`30` 天按日期聚合的柱状图和成功扣费明细分页；后端新增 `/admin/credits/usage` 和 `/admin/credits/transactions`。`backend/.venv/bin/python -m compileall backend/app`、`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend/tests/test_credits.py`、`npm run build --prefix frontend`、`git diff --check` 和 `./scripts/check.sh` 通过。
- 完成 Sprint 45 统一分镜生图格式：新增合同 `docs/contracts/sprint-45-unified-storyboard-prompt-format.md`；故事方案 prompt 改为输出 `text_layout`，并将旁白、对白、内心 OS 分别放入结构化字段；完整故事 prompt 明确后端会把 panel 原文映射到 `第X页 / 【分格】单页 / 画面 / 旁白 / 对话 / 内心OS` 的页式分镜块；正式 panel 最终生图 prompt 已统一组装为页式分镜块，同时要求字段名只用于理解结构、不能画进图片。`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend/tests/test_task_worker_prompt.py`、`backend/.venv/bin/python -m compileall backend/app`、`git diff --check` 和 `./scripts/check.sh` 通过。
- 完成 Sprint 46 人物参考图三视图布局：新增合同 `docs/contracts/sprint-46-character-reference-three-view-layout.md`；人物参考图 prompt 改为固定角色设定图布局，上半部分为正面主图，下半部分并排展示同一人物的左侧视图和右侧视图，并要求三张视图保持同一年龄阶段、发型、服装、体态和标志物。`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend/tests/test_character_reference_prompt.py`、`backend/.venv/bin/python -m compileall backend/app`、`git diff --check` 和 `./scripts/check.sh` 通过。
- 开始并完成 Sprint 47 DY 来源元信息随任务下载：新增合同 `docs/contracts/sprint-47-dy-source-meta-download.md`；抖音下载 adapter 解析 `title`、`description`、`tags` 并保存到内容提取记录；通过 `DY爆款复刻` 自动创建出的生成任务在下载 zip 时额外写入 `meta.json`，只包含标题、描述和标签。`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend/tests/test_content_extraction_media_flow.py backend/tests/test_task_download_state.py`、`backend/.venv/bin/python -m compileall backend/app`、空 SQLite Alembic `upgrade head`、`npm run build --prefix frontend`、`git diff --check` 和 `./scripts/check.sh` 通过。
- 修复 QY 图片接口误传未验证尺寸：`gpt-image-2` 等 QY 图片请求不再把 `3:4` 映射为视频/Grok 章节里的 `864x1152` 传入 `size`，避免统一平台返回“gpt-image-2 不支持 864x1152”；当前仅对 `1:1`、`16:9`、`9:16` 这些已验证图片尺寸显式传 `size`，`3:4` 和 `4:3` 继续通过最终生图 prompt 表达画面比例。`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend/tests/test_image_generation_gateway_only.py`、`backend/.venv/bin/python -m compileall backend/app`、`git diff --check` 和 `./scripts/check.sh` 通过。
- 开始 Sprint 48 用户角色管理与快速角色参考：新增合同 `docs/contracts/sprint-48-user-character-management.md`；目标是新增用户隔离的角色管理 tab，并把创建任务里的人物参考改为规则快速提取角色名、用户显式绑定参考图后才进入固定角色参考链路。
- 完成 Sprint 48 用户角色管理与快速角色参考：新增 `user_characters` 表、角色 CRUD API 和角色参考图资产权限；新增创建任务规则角色名提取接口与显式角色绑定 payload；固定角色会快照为任务内人物参考，参考图不重新生成、不额外扣人物参考图积分，未绑定角色不进入人物参考链路；前端新增 `/characters` 角色管理 tab，并把创建任务弹窗改为角色名卡片、已有角色绑定、新建角色和显式融入故事操作。`PYTHONPATH=backend backend/.venv/bin/python -m unittest discover -s backend/tests`、空 SQLite Alembic `upgrade head`、`npm run build --prefix frontend`、`git diff --check` 和 `./scripts/check.sh` 通过；本地服务已通过 `./scripts/restart-dev.sh` 重启，浏览器验证 `/characters` 页面可访问且创建任务弹窗可见角色参考区域。
- 细化 Sprint 48 角色交互：角色管理列表改为一行一行的紧凑列表，角色图使用完整 contain 展示；创建/编辑角色上传图片后立刻显示本地预览；创建任务中的角色提取改为显式点击 `提取角色` 后调用后端接口，不再随输入自动刷新；提取出的角色名支持删除，点加号会打开带图片的用户角色库列表；手动添加角色只填写角色名称即可加入本次任务。
- 调整 Sprint 48 角色提取：`/tasks/extract-character-names` 不再使用程序规则，改为后端同步调用硅基流动 `Qwen/Qwen3.6-27B` 的 JSON 角色名提取 prompt；前端文案同步为后端 AI 提取，接口失败时明确返回错误，不静默切回规则提取。`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend/tests/test_user_characters.py`、`backend/.venv/bin/python -m compileall backend/app`、`npm run build --prefix frontend`、`git diff --check` 和 `./scripts/check.sh` 通过；本地真实模型烟测输入“三只小猪盖房子，大灰狼来敲门。小红帽在森林里遇见了外婆。”返回 `三只小猪`、`大灰狼`、`小红帽`、`外婆`，耗时约 16.3 秒。
- 修复 Sprint 48 AI 角色提取接口响应 500：日志确认模型已返回 `我`、`妈妈`、`爸爸`，但 API 层把内部 `ExtractedCharacterNames` 对象直接交给响应 schema 校验导致 500；已改为显式返回 `CharacterNameExtractionResult(names=...)`，并补充 API 层单测。使用 Playwright 以普通用户浏览器流程注册、打开创建任务、粘贴同一段母亲织毛裤故事并点击 `提取角色`，页面成功显示 `我`、`妈妈`、`爸爸` 三个角色卡片，后端接口 200，模型耗时约 22.7 秒。`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend/tests/test_user_characters.py`、`backend/.venv/bin/python -m compileall backend/app`、`git diff --check` 和 `./scripts/check.sh` 通过。
- 增强 Sprint 48 固定角色一致性：上传角色参考图时新增 SiliconFlow 视觉模型识别外观锚点，自动填入可编辑的角色 `description`；创建/换图时如果描述为空，后端会用同一 VL 结果补齐，后续生成任务直接复用保存后的描述，不重复调用 VL。最终生图参考说明也从“角色参考图”增强为包含外观锁定和参考强度规则：固定角色身份 > 当前剧情动作/情绪 > 风格表现方式 > 风格模板默认人物外观，要求年龄、发型、体态、服装轮廓和标志性配饰保持一致，颜色可按当前风格转译。`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend/tests/test_task_worker_prompt.py backend/tests/test_user_characters.py`、`./scripts/check.sh` 和 `git diff --check` 通过；本地服务已通过 `./scripts/restart-dev.sh` 重启，浏览器验证 `/characters` 新建角色表单可见自动识别描述入口，并用真实参考图调用 `/api/v1/characters/describe-reference` 返回三只小猪外观描述。
- 修复 Sprint 48 固定角色与临时角色混合生成：定位任务 `0da41c30efe844beb25fe3d69a2c6a71` 只显示固定角色，是因为任务创建时已写入 `fixed_1`，worker 看到已有 `task_characters` 后直接跳过人物提取，导致 `妈妈`、`爸爸` 没有进入临时参考图生成。现已改为固定角色保留且优先，worker 仍会提取故事里的其他主要人物，并只追加非同名临时角色；故事方案和提取分镜模式下，已有临时角色链接也不会再阻止固定角色按名字补链。`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend/tests/test_user_characters.py backend/tests/test_task_worker_prompt.py`、`backend/.venv/bin/python -m compileall backend/app`、`./scripts/check.sh` 和 `git diff --check` 通过。
- 调整 Sprint 48 角色录入体验：角色管理和创建任务快速新建角色时，上传参考图只做本地预览，不再立即调用 VL 或禁用保存按钮；后端先保存角色和参考图，再通过 FastAPI 后台任务调用 SiliconFlow 视觉模型补齐 `description`。后台识别失败时最多重试 3 次，最终失败只记录日志，不阻断用户保存角色。`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend/tests/test_user_characters.py`、`backend/.venv/bin/python -m compileall backend/app`、`npm run build --prefix frontend`、`./scripts/check.sh` 和 `git diff --check` 通过；本地服务已通过 `./scripts/restart-dev.sh` 重启，浏览器验证 `/characters` 新建角色弹窗不再显示识别中状态，保存提示改为留空后台识别且不阻塞保存。
- 调整 Sprint 48 最终生图 prompt 编译：新增 `compose_final_image_prompts_v1.md` 和后端 LLM 编译接口，正式任务与单 panel 修改不再直接把参考、风格和结构化分镜字符串拼接成最终 prompt；worker 会把全局角色表、每页分镜中间态、图片内文字、风格信息和参考图顺序一次性提交给 LLM，由这一层处理固定角色/临时角色的全局一致性、角色外观与分镜或风格模板默认人物外观的冲突，并输出每页完整画师指令。编译失败会让 `generate_images` 或单图版本明确失败，不静默回退到旧拼接逻辑。
- 修复 Sprint 48 未点击角色提取时跳过临时角色的问题：任务创建 schema 和前端普通任务/DY 复刻入口默认开启 `use_character_references`，后端创建任务改为尊重 payload 的人物参考开关，而不是只按 `story_characters` 是否有固定角色绑定来决定；因此用户不点击 `AI 提取角色`、不绑定固定角色时，任务仍会进入 `extract_characters` 和 `generate_character_references` 临时角色链路。创建弹窗里的角色提取按钮改为更醒目的主操作，并增加“不操作也会自动走临时角色一致性”的提示。
- 补强 Sprint 48 线上风格一致性：最终生图 prompt 仍先由 LLM 基于全局角色表、分镜中间态、图片内文字和参考图顺序编译，负责处理角色/剧情/风格冲突；在 `prompt` 风格参考模式下，worker 会在发送图片 Provider 前把完整 `style_prompt_snapshot` 显式拼接到 LLM 画师指令外层，并附带“角色身份与外观锁定 > 当前剧情动作/情绪 > 风格表现方式 > 风格模板默认人物外观”的执行优先级，避免风格模板吞掉角色外观，也避免线上任务因为只依赖 LLM 摘要而风格控制变弱。
- 移除故事方案模式的特殊封面设定：`plan_storyboard_from_brief_v1.md` 和后端数量指令不再要求额外生成封面，固定图片数量就是最终图片张数；后端会把新规划出的 panel 统一归一为 `scene`，前端创建任务文案和详情卡片不再展示“封面”概念，所有图片进入同一套分镜、角色参考和最终生图 prompt 逻辑。
- 简化创建任务固定角色交互：创建弹窗默认不展示角色卡片、添加角色卡片或 AI 提取按钮；用户不勾选 `使用固定角色` 时点击 `创建任务` 会直接提交。只有勾选固定角色后，底部主按钮才切换为 `提取角色`，提取完成后展示角色列表和绑定入口，再允许用户创建任务。
- 压缩创建任务弹窗交互密度：顶部 4 个输入模式卡片在桌面改为一行紧凑展示，创建弹窗默认只显示 3 个风格并保留“展开更多风格”选择入口；固定角色勾选、提取等待态和提取后的角色列表移动到风格选择之后、底部主按钮之前，确保用户点击 `提取角色` 后能在按钮附近看到结果。`npm run build --prefix frontend`、`./scripts/check.sh` 和 `git diff --check` 通过；Playwright 浏览器验证 `/tasks` 创建弹窗默认显示 3 个风格，勾选固定角色后等待提示距底部按钮约 20px，真实提取“三只小猪盖房子，大灰狼来敲门。”后角色卡片距底部按钮约 20px。
- 继续压缩创建任务弹窗底部交互：`使用固定角色` 勾选项从普通表单区移动到底部操作区，与 `创建任务` / `提取角色` 主按钮同区展示，避免用户滚动到下方后看不到是否提取角色的开关；风格模板卡片改为更小的横向紧凑条目，只保留单个缩略图和一行描述。`npm run build --prefix frontend`、`./scripts/check.sh` 和 `git diff --check` 通过；Playwright 验证创建弹窗默认仍显示 3 个风格，风格区高度约 140px、单个风格卡片约 67px，勾选固定角色后等待提示在底部按钮上方，主按钮文案切换为 `提取角色`。
- 再次收紧创建弹窗风格模板展示：主弹窗内风格卡片不再展示风格描述、比例、模型名或启用状态，只保留单张缩略图和风格名称；顶部风格说明在主弹窗中隐藏，详细信息仍通过“展开更多风格”查看。`npm run build --prefix frontend`、`./scripts/check.sh` 和 `git diff --check` 通过；Playwright 验证主弹窗风格区高度约 126px、单个风格卡片约 55px，描述元素已隐藏，底部 `使用固定角色` 开关仍可见。
- 优化创建任务风格选择结构：经过两轮浏览器检查与迭代，主弹窗和“展开更多风格”弹窗的风格卡片都改为只展示单张风格图和风格名称，不再展示比例、描述、模型名或启用状态；无图占位文案从“模板比例”改为“无图片”。更多风格弹窗移除说明文字，网格卡片统一为稳定的图片框加名称结构。`npm run build --prefix frontend`、`./scripts/check.sh` 和 `git diff --check` 通过；Playwright 两次打开 `/tasks` 创建弹窗和更多风格弹窗验证：主弹窗默认 3 个风格、单卡约 55px、更多风格单卡约 152px、每张卡只有 1 张图和名称，底部 `使用固定角色` 开关仍可见。
- 修复创建任务风格图尺寸不统一：主弹窗和“展开更多风格”弹窗的风格图统一放进 `3:4` 图片框，图片使用 `object-fit: cover` 裁切，多出的部分隐藏；移除响应式规则对创建任务风格图高度的覆盖，避免竖图撑出卡片并造成选中框与图片视觉尺寸错位。`npm run build --prefix frontend`、`./scripts/check.sh` 和 `git diff --check` 通过；Playwright 验证主弹窗与更多风格弹窗图片框比例均为 `0.75`，图片不再超出卡片，底部 `使用固定角色` 开关仍可见。
- 修复 `gpt-image-2` 参考图数量限制：根据 `docs/api_v4.md` 和真实接口验证，ListenHub 路径的 `gpt-image-2` 支持 4 张参考图；后端已把该模型参考图上限从 3 改为 4。任务生图和单 panel 修改在参考图超过模型上限时保留前 N 张并丢弃末尾多余参考图，同时同步裁剪最终 prompt 编译使用的参考说明，避免本地配置错误阻断生成。
- 优化任务详情预加载范围：任务详情接口不再默认返回分镜原文、图片内文字、文字布局和生图 prompt；新增分镜 debug 按需接口，用户点击后才加载图片文字，管理员点击后才额外加载 Prompt。前端图片懒加载提前量从 `640px` 收窄到 `160px`，图片展示强制使用原图 URL，任务列表缩略预览和详情分镜图改为 `contain` 完整展示，不引入会裁切原图的缩略图生成，避免缩略图比例不一致导致画面被裁剪。
- 修复普通任务误粘抖音分享链接和空角色提取失败：创建弹窗检测到抖音作品链接时会自动按 `DY爆款复刻` 提交到内容提取流程，后端普通任务 API 也会拒绝抖音链接，避免分享口令被当成提取分镜文本进入生成链路；任务执行阶段如果人物提取返回空角色，后端会记录 `character_extraction_empty` 并跳过任务级临时人物参考，继续后续生图，不再让任务停在 `extract_characters`。
- 开始并完成 Sprint 49 抖音热门样本调研 Skill：新增项目本地 `.agents/skills/douyin-hot-sample-research/`，把 `douyin-downloader` 明确为热门图文样本库采集底座；Skill 第一阶段固定为关键词/热榜调研、最近热门筛选、候选样本分层，再下载少量入选作品；新增 `references/research-fields.md` 统一样本字段，新增 `scripts/summarize_samples.py` 从搜索 JSONL、下载 metadata 和额外数据目录中汇总日期、标题、作者、图文类型、图片数和互动数据。该版本先把 Codex 人工抽检与 VL 批量提取分开，后续由 Sprint 50 明确改为复用 DoodleStory 现有内容提取 VL 链路。
- 完成 Sprint 50 抖音样本 Skill 复用现有 VL 链路：更新 `.agents/skills/douyin-hot-sample-research/`，把图片理解策略改为复用 DoodleStory 现有内容提取 VL，而不是另起模型链路；Skill 明确区分 `preview_vl` 与 `full_story_document`，只判断开头、结尾或中段转折时只传对应图片窗口，只有样本进入故事文档或任务创建候选时才走完整图集提取；字段参考新增 VL 输入页码、结果类型、是否需要全量提取和内容提取 ID 等记录项。

## 已知缺口

- 当前 React/FastAPI 代码仍是骨架，尚未达到产品设计完整要求。
- 任务创建、任务详情、取消、下载、完整 worker 流程尚未实现。
- 风格测试已接入真实生图 Provider；参考图模式要求参考图具备公网 HTTP(S) URL，仍建议用真实七牛风格参考图跑一次端到端验证。
- LLM 客户端和 prompts 已实现，但尚未接入任务 worker 流程。
- 任务 worker 已接入 LLM 和统一生图 Gateway 客户端，基础任务详情、批量下载和预览已完成；更精细的运行中恢复策略、单图下载入口和更系统的组件拆分仍可继续完善。
- 历史本地资产尚未迁移到七牛；七牛对象存储已通过独立上传/访问烟测，仍建议用真实任务生成链路做一次端到端验证。
- 旧的多 profile registry 已移除；生图链路已收敛到 `docs/api_v3.md` 对应的统一 OpenAI Images 兼容 Gateway，旧 SiliconFlow 直连、XG edits 和 ApexerAPI Chat 不再作为默认生图路由。
- UI 已开始切换到 Runway / Creative AI Studio 风格，但任务页、详情页和整体组件拆分仍需继续深化。
- 内容提取已完成同机 `127.0.0.1:8010` 可达时的真实图文下载、旧版图文 OCR、故事总结、列表和详情弹窗验证；Sprint 25 已把图文内容提取切换为 SiliconFlow 视觉模型整组图片顺序理解，仍建议用真实漫画图文链接做一次端到端验证。视频音频转写仍需用真实视频链接单独端到端验证。

## 建议下一步

1. 用真实七牛配置跑一条风格参考图上传、任务生成、缩略图访问和打包下载的端到端验证。
2. 保持独立抖音下载服务 `127.0.0.1:8010` 可用，并用真实链接持续验证内容提取链路。
3. 继续做组件拆分，把当前 `frontend/src/main.tsx` 拆成页面、组件和 API 模块。
4. 补充更细的自动化测试和任务 worker 运行恢复策略。
5. 用真实抖音视频链接验证 `内容提取` tab 的视频下载、音频分离和语音转写链路。
