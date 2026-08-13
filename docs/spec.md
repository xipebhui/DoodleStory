# 产品规格

## 产品概述

`DoodleStory` 是一个文本转图片的故事生成产品。用户提供完整故事、故事方案或简化故事，选择生成风格后，系统将故事转成一组 panel，并为每个 panel 生成对应图片。

产品必须原样保存用户输入的原始文本。完整故事模式下，LLM 优先负责把原文按语义和阅读节奏切成连续 panel，应尽量保留原文并避免改写、摘要、补字或删字；允许为了切割流畅对标点、换行、空格做轻微规范化，但不能改变句意、人物关系、事件顺序和关键信息；自动数量模式下以画面单元、情绪转折和叙事节奏为首要目标，30-40 字只是次级偏好，不能为了凑长度硬合并两个本应分开的画面动作或情绪转折；同一核心行动的补充信息不要拆开；单个 panel 原文不能超过 50 字。如果 LLM 切割结果结构、顺序或长度不合格，后端允许退回确定性标点切割：当前片段超过 20 字后，遇到下一个标点符号即截断；如果连续 50 字没有标点，则在 50 字硬切，保证不突破后端硬上限。故事方案模式下，LLM 直接根据用户方案规划图文分镜，不再先扩写成长篇故事再切分；规划概要必须与原始输入分开保存。提取分镜模式下，系统把内容提取结果结构化为可生图 panels，只保留和转化页序、画面、旁白、对白、内心 OS 和分格布局，不做故事扩写。知识方案模式下，LLM 只负责根据知识点、章节、条目、空行、标题、正文结构和用户指定数量把连续知识图文方案拆成可独立生图的页面；可以识别用户显式页标，但不能要求用户必须写页标；`正向提示词 / 负向提示词` 中的页眉、纸张、边框、作者栏、字体和插画风格通常视为全局模板，自动模式的页数优先由后续知识条目、`副文字 + 画面` 组合和收尾金句块决定，只有用户明确写“单页 / 一张图 / 全部内容放同一页”时才把多个条目合并成一页；不做人设提取、不拆图片内文字字段、不做最终 prompt LLM 编译。人物对白必须写进 `visual_prompt`，和说话人物、动作、表情、对象绑定，不再作为 `image_text.dialogue` 单独字段传递，避免同一句台词重复入图。完整故事、故事方案和提取分镜进入生图前都先统一为页式分镜中间态：内部分镜编号、`【分格】`、`画面`、`旁白`、`对话`、`内心OS`；最终发送给图片模型的 prompt 再由 LLM 基于中间态、全局角色表、风格和参考图顺序统一编译。知识方案则直接把拆页后的单页完整提示词与风格、比例和参考图说明拼接后送入生图。

## 用户

- 希望把短故事文本转换成连续图片的创作者。
- 负责调试可复用图片风格、维护风格 prompt 和风格绑定生图模型名的运营/维护者。
- Admin 用户，可查看所有用户的任务并处理运营排查。

## 核心概念

- 风格：可复用图片风格，包含参考图片、基础信息、风格提示词、参考方式和绑定图片模型；参考方式可选 `prompt` 或 `image`。`prompt` 模式下实际生图风格由 `style_prompt` 控制；`image` 模式下任务和风格测试会把风格参考图作为生图模型参考输入。
- 用户：通过邮箱和密码注册登录。第一版只有 `user` 和 `admin` 两种角色。
- 用户角色：用户长期维护的固定角色资产，包含名字、参考图和描述。角色资产按用户隔离，普通用户只能访问自己的角色；创建任务时可以把故事里快速提取出的角色名绑定到自己的角色资产。
- 积分：用户用于生成图片的额度。所有模型同价，成功产出一张图片扣 `1` 积分；新注册用户默认获得 `30` 积分，Sprint 44 上线迁移时当前已经注册的用户统一初始化为 `1000` 积分。
- 激活码：管理员生成的固定积分面额兑换码。用户在设置页输入激活码后自助兑换积分；激活码单次使用，过期、禁用或已兑换后不能再次使用。
- 风格测试：将测试文本与风格提示词组合后，发送给该风格绑定的模型生成测试图。
- 生图 Provider：部署级默认值可选 `qy`、`xgapi` 或 `grok`。Native Agent 用户可以在对话中
  明确要求使用其中一种方式，Agent 必须通过 `generate_image.provider` 结构化参数执行并为每张
  图片保存实际 Provider；未指定时使用部署默认值。任何 Provider 失败后都不得自动改走其他
  Provider。Grok 通过 `grokcli` 和持久化 OAuth 凭据使用订阅能力，无参考图走 image、最多三张
  公网参考图走 image-edit。
- AI 视频短镜头：Native Agent 可选择 `generate_video_clip(prompt, image_id?, duration_seconds,
  aspect_ratio)`。工具固定通过精确版本的 `grokcli` 调用 `grok-imagine-video-1.5`，支持 1–15 秒
  文生视频，或使用当前 Conversation 中一张 `NativeAgentImage` 作为首帧执行图生视频；默认
  720p。每次 Tool Call 只启动一次真实生成，不自动重试、不切模型或 Provider。输出必须经
  ffprobe 验证为 H.264/MP4 后保存为 `generated_video` 与 `NativeAgentVideo`，并记录 Prompt、
  Provider、模型、模式、源图片、请求参数和 grokcli 版本。该短镜头不是完整成片，现阶段也不会
  自动输入 `render_story_video`。
- 任务：用户发起的一次文本转图片请求。
- 音频参考：管理员上传并管理的参考音频资产，用于后续视频任务的旁白音色或参考音频选择。音频管理只对管理员可见，普通用户不能访问音频参考列表、详情、上传、转写、试听、编辑、删除或音频参考文件资产。音频参考创建时由后端本地 Whisper 自动从上传文件转写参考文本，并统一转换为简体中文；管理员不手动填写参考文本、Provider、模型或音色名。管理员可以为音频参考设置产出语速，后续视频任务会在创建时快照该语速。
- 视频任务：管理员发起的一次故事转图文视频请求。视频任务不对普通用户可见。视频任务不重写故事切分或生图逻辑，而是先创建并关联一个普通生成任务，由现有 `GenerationTask` 负责把 `故事文本 + 风格` 转成 panels、旁白结构和图片；视频任务在上游图片任务成功后继续承接旁白转音频、提交图文视频生成服务和最终视频资产状态。
- 输入模式：`完整故事` 保持原文切分；`故事方案` 直接识别用户方案中的显式或隐式 panel 逻辑，并规划连续分镜、画面内容、分格布局和图片内文字；`提取分镜` 接收内容提取结果，按页结构化为 panels，不新增图片、不合并页、不扩写故事；`知识方案` 接收知识卡片、图鉴、清单或方法论生图方案，系统用 LLM 按知识结构自动拆成连续内容页，可识别显式页标但不强制用户写页标，不做故事改写、人物提取、图片文字字段拆解或版式字段补全；`DY爆款复刻` 是任务创建前置模式，用户提交抖音分享文本或链接后，系统先执行内容提取，再自动用提取结果创建 `提取分镜` 生成任务。故事方案、提取分镜和知识方案中用户明确写出的画面、构图、文字、重点和禁止事项优先于风格规则、默认分镜方法和剧情增强建议。
- Panel：由用户原始故事或故事方案规划出的画面片段。Panel 保存剧情意图、类型、图片内文字、生图画面 prompt 和分格布局；这些字段先形成页式分镜中间态，最终生图 prompt 由 LLM 统一编译为完整画师指令。
- 人物参考：任务级可选能力。用户显式绑定的角色会作为固定角色快照到任务内人物参考；故事中未绑定但被任务人物提取识别为主要人物的角色，会生成只属于当前任务的临时参考图。固定角色和临时角色进入任务后使用同一套一致性规则，都会按 panel 引用顺序传入生图请求，并作为最终 prompt 编译的全局角色约束。
- 最后一张真人图片：任务创建时的显式可选项，默认关闭。开启后，仅最后一个 panel 按真实摄影/真人自拍/生活照质感生成，不自动推断用户意图；该 panel 不携带漫画风格参考图或人物参考图，也不拼接全局漫画风格提示词，避免真实照片被拉回手绘风。其他 panel 仍按任务所选风格和人物参考链路生成。
- 生成图片：任务中某个 panel 对应的图片输出。
- 内容提取：用户粘贴抖音分享文本或链接，系统从中解析真实抖音 URL，下载图文或视频；图文按原顺序逐张提交，每次请求只包含一张图片，模型只提取当前图片实际可见、可用于复刻的分格、画面、原文文字和文字布局，不理解或补写连续故事；每张图片先使用 `TEXT_FALLBACK_*` 当前指向的火苗 OpenAI 兼容多模态模型，失败后切换到现有 `LIO_*` 平台并最多发起 3 次 LIO 请求，仍失败才让整个内容提取任务失败；视频继续通过音频多模态模型转写。
- DY 来源元信息：抖音下载服务返回的原作品标题、描述和标签会保存到内容提取记录；通过 `DY 爆款复刻` 自动创建出的生成任务下载压缩包时，会额外包含 `meta.txt`，其中只写入标题、描述和标签。

## 部署与运行

- 本地开发保持前后端双服务：FastAPI 后端默认监听 `127.0.0.1:8000`，Vite 前端默认监听 `127.0.0.1:3000`。
- 同一主机上指向同一数据库的 DoodleStory 后端必须保持单实例。后端在任何 startup 恢复动作前
  获取基于数据库标识的跨进程锁；第二实例必须明确启动失败，不能先恢复任务再因端口冲突退出。
  Windows 使用系统文件区间锁，POSIX 使用 `flock`；正常关闭与 startup 失败释放锁，进程异常退出时
  由操作系统释放锁。
- Docker 生产部署中，DoodleStory 应用镜像使用单容器形态：构建阶段生成前端静态文件，运行阶段由 FastAPI 同时提供前端页面和 `/api/v1/*` API。
- Docker Compose 部署同时编排 DoodleStory 和同级目录的多平台 `douyin-import-service`；该服务组合 `douyin-downloader`、`wechat-article-crawler` 与 `XHS-Downloader` 的隔离运行环境，并以 Compose 服务名 `douyin-import-service` 暴露内部端口 `8010`。DoodleStory 通过 `http://douyin-import-service:8010` 调用，导入服务不暴露公网入口。
- 生产容器内部只监听 HTTP 端口 `8000`；在 Coolify + Traefik 节点上只能通过 `expose: "8000"` 暴露给 Traefik，不手动映射宿主机 `80/443`。
- Docker 生产镜像通过 `DOODLESTORY_FRONTEND_DIST` 指向前端构建目录；该变量为空时不启用静态前端挂载，保留本地开发行为。
- 容器启动时必须先执行 Alembic migration，再启动 Uvicorn。
- SQLite 数据库和本地文件资产默认放在 `/app/data` 下，Coolify 部署时必须把 `/app/data` 配置为持久化 volume。
- 抖音导入服务的下载产物必须放在独立持久化 volume，并以同一路径挂载给 DoodleStory 容器读取；因为导入服务返回的是本地文件路径，两个容器不能使用彼此不可见的私有文件系统路径。
- 生产前端默认同源调用 API，不需要 `VITE_API_BASE_URL` 指向独立后端域名；如外部站点需要跨域访问 API，再显式配置 `FRONTEND_ORIGIN`。
- 容器内的 `127.0.0.1` 只代表当前容器自身。抖音导入服务在同一个 Compose 应用内时应使用服务名访问；图文视频服务、图片 Gateway 等其它依赖如果不在同一容器或同一 Compose 网络内，必须配置为容器可访问的真实地址。

## 核心用户路径

0. 进入工作台。
   - 已登录用户访问根路径 `/` 时进入任务页 `/tasks`。
   - 传统构建继续使用旧工作台 `/tasks`；Agent 创作使用独立模块 `/agent`。两者共享用户、积分、风格、角色、任务、Panel、图片版本和资产数据，但不共享页面 Shell，也不在 Agent 页面常驻旧后台导航。
   - `/agent` 的主导航是新建对话、搜索和历史会话；页面保留 DoodleStory 品牌、用户、积分和一个低层级“返回传统工作台”入口，不显示旧 `图文任务/内容提取/风格/角色` 导航或 `传统构建 / AI 构建` 分段切换。Agent 的 Task、Attempt、依赖和 Checkpoint 是后端执行事实，但用户主界面仍是聊天：只在对话中展示可读阶段摘要、产物、确认卡和可展开的“本次计划”，不把页面做成传统任务后台、DAG 画布或原始模型 Response/Tool 参数查看器。
   - `/agent/{conversation_id}` 稳定恢复指定 Agent 会话；`/agent/{conversation_id}/tasks/{task_id}` 在同一 Agent 上下文中打开 AI 专属任务检查器。Agent 任务检查器不复用旧 Pipeline 任务抽屉，旧 `/tasks/{task_id}` 继续服务传统工作台。
   - `/agent` 以 Sprint 103 已调试 Demo 的会话优先交互为视觉事实来源，但正式页面的 Conversation、Message、Run、Style、Character、Task、Panel、Image Version、Artifact、Approval 和 Event 必须来自真实 API/数据库，不得包含 Mock、占位成功或未接通假操作。
   - 传统工作台页面保持稳定二级路径：`/tasks`、`/video-tasks`、`/audio-references`、`/content-extractions`、`/styles`、`/characters`、`/users`、`/credit-usage`、`/settings`。
   - 用户刷新页面、复制链接或使用浏览器前进后退时，当前工作台页面必须与 URL 保持一致，不能刷新后回到默认任务页。
   - 普通用户和管理员都应在工作台左下角实时看到当前积分余额；余额变化后，任务提交、风格测试、单图修改和激活码兑换等操作应刷新该余额。

1. 管理风格。
   - 创建、查看、更新、删除风格。
   - 删除风格时，如果没有任务或风格测试引用则物理删除；如果已有历史引用，则软删除并从风格库隐藏，历史任务继续使用创建时保存的风格快照。
   - 添加参考图片和风格基础信息；创建风格时可以先选择参考图，风格创建成功后自动上传到新风格，编辑风格时继续支持上传和删除参考图。
   - 风格参考图上传期间必须展示明确进度，并阻止关闭编辑抽屉、重复提交、重复上传、删除参考图或删除风格，避免网络慢时产生半完成或重复上传状态。后端只接受真实 PNG、JPEG 或 WebP 图片，单张图片最大 10MB；文件内容为空、伪造图片、客户端声明类型与真实图片内容不一致或超过大小上限时必须明确报错。
   - 配置风格提示词。为了降低手写复杂度，用户不需要手写风格提示词；提供至少 3 张风格参考图后，系统可以使用 `TEXT_FALLBACK_*` 配置的 `gpt-5.4` 多模态模型提取这些图片共同的视觉风格。保存风格时如果风格提示词为空，前端必须先自动提取提示词再继续保存；提取结果必须只描述画法、色彩、线条、肌理、构图和透视等风格交集，禁止提及图片中的具体情节、人物、动物、建筑物或故事内容。提取结果填回风格提示词表单供用户继续编辑；少于 3 张参考图、`gpt-5.4` 配置缺失或模型返回结构不合格时必须明确报错，不切换到其它 VL 模型。后端允许草稿风格暂时没有提示词，但启用风格时必须有非空提示词。
   - 配置风格参考方式：`prompt` 表示最终生图 prompt 编译时必须吸收风格提示词；`image` 表示把风格参考图传入生图模型作为风格参考。旧风格默认使用 `prompt`。
   - 风格只绑定生图模型名，不暴露 provider、API key 或默认参数；图片模型名由用户手动填写，不使用下拉选择，密钥和固定平台配置由 env 维护。

2. 测试风格。
   - 选择风格。
   - 输入测试文本后提交测试；后端创建 `style_test` 记录并在后台生成，前端不等待图片 Provider 完成。
   - 风格测试页必须按当前风格读取历史测试列表，展示测试文本、状态、结果图、失败原因和创建/完成时间；有 `queued` / `running` 记录时自动轮询刷新。
   - 后台生成时将测试文本与风格提示词组合，并使用风格绑定的模型与同一套风格参考方式生成测试图片。
   - 测试图成功产出后扣 `1` 积分；如果积分不足，风格测试不调用图片 Provider，并在历史列表中显示明确错误。
   - 服务启动时必须把遗留的 `queued` / `running` 风格测试标记为失败，并释放可识别的积分占用，避免历史列表长期显示卡住。
   - 根据结果调整风格提示词、参考图、参考方式或风格绑定的生图模型名；风格测试必须和正式任务使用同一套风格参考方式。

3. 管理角色。
   - 用户进入 `角色管理` tab。
   - 创建角色时填写名字并上传参考图；保存时不等待 VL，后端先保存角色和参考图，再后台调用 SiliconFlow 视觉模型自动生成可编辑的角色外观描述，并保存到角色 `description`。后台识别失败时最多重试 3 次，不阻塞用户保存。
   - 角色描述作为后续固定角色的一致性锚点使用；生成任务不再为同一角色重复调用 VL，而是直接读取已保存的描述和参考图快照。
   - 角色列表、详情、更新和删除都只作用于当前登录用户自己的角色。
   - 删除角色采用软删除，从角色库隐藏；历史任务使用任务创建时保存的角色快照，不受删除影响。
   - 角色参考图不会展示给其他用户；任务创建时传入的角色 ID 必须由后端校验属于当前用户。

4. 创建生成任务。
   - 用户注册或登录。
   - 通过居中弹窗创建任务。
   - 选择输入模式：完整故事、故事方案、提取分镜、知识方案或 DY 爆款复刻。完整故事会保持故事不变，用户应只提交故事本身，不混入说明、标签或额外要求；故事方案可以提交故事设计、人物设定、画面要求或简化想法；提取分镜适合提交内容提取结果；知识方案适合提交已经按页写好的知识卡片、图鉴、清单或方法论生图提示词；DY 爆款复刻适合直接提交抖音分享文本或作品链接。前端创建弹窗检测到抖音分享链接时必须自动按 DY 爆款复刻提交到内容提取流程；后端普通任务创建接口必须拒绝抖音分享链接，不能把分享口令当成故事或分镜文本创建任务。
   - 输入原始文本、故事方案或创作要求。
   - 创建弹窗默认不展开固定角色绑定流程；普通用户不勾选 `使用固定角色` 时，点击 `创建任务` 直接提交任务，不等待角色提取。
   - 如果用户勾选 `使用固定角色`，底部主按钮先显示为 `提取角色`；系统通过后端接口同步调用当前 LIO/Gemini 文本模型提取角色名，并使用 `CHARACTER_EXTRACTION_TEMPERATURE` 控制低温识别，提取完成后才展示角色卡片、添加角色入口和固定角色绑定控件，并允许用户继续创建任务。
   - 勾选固定角色后，提取出的角色名可以从本次任务中删除；用户可以点角色卡片的加号打开自己的角色库，并从带参考图的角色列表中选择已有角色绑定。
   - 勾选固定角色并完成提取后，用户也可以手动添加一个新角色名；手动添加只需要填写角色名称。如果后续明确选择“融入故事文本”，系统调用 LLM 把新增角色自然并入当前故事文本。
   - 用户显式绑定了参考图的角色会作为固定角色进入人物参考链路；未绑定角色不会保存到用户角色库。
   - 选择自动判断图片数量，或输入固定图片数量。
   - 普通创建弹窗展示 `最后一张真人图片` 开关，默认关闭；用户勾选后，普通图文任务和 DY 爆款复刻自动创建的生成任务都应保存 `last_panel_real_photo=true`。`去掉画面文字` 开关仍不展示，前端创建和 DY 爆款复刻提交时固定为关闭。后端字段继续保留，用于历史任务、视频任务上游图和后续内部流程。
   - 选择风格。
   - 当风格数量较多时，创建任务弹窗内展示紧凑风格宫格，并支持展开二级弹窗选择更多风格。
   - 提交任务。
   - DY 爆款复刻提交后，后端先保存内容提取记录并后台下载素材、提取逐页漫画内容；内容提取成功后自动创建 `story_input_mode=extracted_storyboard` 的生成任务并入队。前端轮询内容提取记录，拿到关联任务 ID 后跳转到任务详情。
   - DY 爆款复刻会保留下载服务返回的原作品 `title`、`description` 和 `tags`，后续关联生成任务下载图片包时一并导出为 `meta.txt`。

5. 执行任务生成。
   - 所有正式图片生成请求在调用图片 Provider 前必须检查并占用 `1` 积分，避免同一任务内并发生图超出用户余额。Provider 失败或未产出图片时释放占用；图片资产保存成功后转为实际扣费。
   - 如果任务是故事方案模式，调用 LLM 直接做图文 storyboard planning，输出标题、规划概要、每个 panel 的剧情意图、画面 prompt、分格布局和图片内文字；用户输入的故事方案是最高创作约束，和风格规则、默认分镜方法或剧情增强建议冲突时优先满足用户需求。
   - 如果任务是完整故事模式，后端调用 LIO/Google 文本模型按语义切分原文；LLM 应尽量保留原文并避免改写或重构文本，但允许为了切割流畅轻微规范化标点、换行或空格。自动数量模式下以画面单元、情绪转折和叙事节奏为首要目标，30-40 字只是次级偏好；短句如果承担独立转折可以单独成 panel，同一核心行动的补充信息不要拆开。后端必须校验单个 panel 原文不超过 50 字；如果 LLM 切割结果不合格，后端退回标点切割，超过 20 字后在下一个标点截断，连续 50 字没有标点时按 50 字硬切。
   - 如果用户选择固定图片数量，将故事切成对应数量的 panels。
   - 故事方案模式下，固定图片数量就是最终图片张数，不额外插入特殊图片。
   - 如果未固定数量，完整故事模式按语义边界自动切分，让每段形成一个顺滑画面动作、连续事件、情绪转折或完整叙事单元；如果固定数量过少导致无法保证每个 panel 原文不超过 50 字，任务必须明确失败。
   - 故事方案模式下，所有 panel 都按同一套剧情分镜逻辑处理，并区分旁白、人物对白和内心 OS；人物对白必须写进 `visual_prompt` 的说话动作中，不拆到 `image_text.dialogue`。如果用户明确写出上格/下格、上下两部分、左右两部分、分屏、单页构图、字体不能过小、必须出现或不要出现等要求，对应要求必须写入相关 panel 的画面、图片文字设计或 `text_layout`。
   - 提取分镜模式下，调用 LLM 只把内容提取结果结构化为 panels；输入中的 `第X页` 对应同序号 panel，不自动新增图片，不合并页，不扩写剧情。旁白和内心 OS 必须进入图片文字结构；对白必须逐字写入 `visual_prompt` 并绑定说话人物、气泡位置和动作；分格/多栏信息必须进入 `text_layout`。
   - 提取分镜模式下，如果用户选择固定图片数量，而解析出的分镜页数或 panel 数量与设置数量不一致，任务必须明确失败并提示“图片解析出的分镜数量和设置图片数量不一致”，引导用户调整图片数量或分镜内容；不能只显示泛化的结构化失败。
   - 知识方案模式下，后端调用 LLM 根据知识点、章节、条目、空行、标题、正文结构和固定图片数量把用户输入拆成连续内容页；如果用户已经写了 `第1页` / `图1` / `P1` 等页标，必须按这些页保留顺序，不合并、不重排、不插入封面。每个 panel 的 `generated_prompt` 必须是单页完整可执行的生图提示词，并包含该页需要保留的主题、版式、文字、插图/图标/场景要求、统一风格要求和禁止事项；全局要求需要带入每一页必要位置，让单页 prompt 离开上下文也能独立生成。知识方案默认不启用人物参考，不创建人物提取或人物参考图步骤；不主动拆 `image_text`，不强行生成 `text_layout`。最终生图 prompt 跳过最终 prompt LLM 编译，只在拆页后的单页提示词外拼接所选风格、画面比例、风格参考图说明和去文字最高指令。固定图片数量时必须输出对应页数，否则任务明确失败。
   - 如果任务绑定了用户固定角色，后端把用户角色名字、描述和参考图快照保存为任务内人物参考；固定角色参考图不重新生成，不额外扣人物参考图积分。绑定固定角色时，任务仍会继续提取故事里的其他主要人物，并为未绑定主要人物生成任务内临时参考图。
   - 任务级临时人物提取使用角色提取专用低温配置；当故事没有直接写外貌时，LLM 必须根据全文、称呼、人物关系、恋爱/亲情/校园/职场语境推断年龄阶段和性别呈现，例如第一人称“我”也要结合上下文推断为女学生、男孩、母亲等可统一形象，而不是输出“性别不明”的模糊人物。
   - 任务执行阶段的人物提取如果没有识别到可用于参考图的主要人物，必须跳过任务级临时人物参考并继续后续生图，不能把该任务直接标记为失败。
   - 固定角色和任务临时角色进入最终生图 prompt 编译时必须带上角色描述、外观锚点和参考强度规则：角色身份优先于当前剧情动作/情绪，当前剧情动作/情绪优先于风格表现方式，风格表现方式优先于风格模板默认人物外观。
   - 固定角色在完整故事模式下复用 panel prompt 生成阶段判断每格引用哪些角色；故事方案和提取分镜模式按角色名在 panel 文本和画面提示词中做确定性匹配。
   - 旧的纯自动人物参考不再替代用户固定角色；固定角色优先使用用户资产，未绑定主要人物使用任务内临时参考图。
   - 完整故事模式下，再次调用 LLM 输入原始故事和 panel 原文，只生成每张图的 `visual_prompt`；图片内文字不由 LLM 生成，固定使用该 panel 的原文片段，并在最终 prompt 编译输入中作为页式分镜中间态的 `旁白`。所选风格提示词进入该 LLM 调用的 system prompt，作为图像设计规则使用，不再作为普通 user 字段传入。
   - 完整故事模式必须更克制：LLM 只能设计画面，不允许新增、改写或概括 panel 原文，不允许把原文之外的对白、旁白、标题或字幕写进 prompt。
   - 故事方案模式下，图文设计已经在 storyboard planning 中生成，不再额外走 chunk 后的 panel prompt 生成。
   - 开启人物参考时，完整故事模式的 panel prompt 生成还需要标注当前 panel 涉及哪些固定角色和临时角色；故事方案和提取分镜模式使用确定性名字匹配绑定参考图顺序。
   - 中间态 prompt 应描述主体、动作、场景状态、静态视觉内容和图片内文字在画面中的呈现方式，且已经吸收所选风格提示词的画风、人物、构图和文字规则。最终单图生图 prompt 不得要求绘制“第几页”“第 X 页”“Page X”这类页码、编号或角标。
   - 正式生图前，后端必须调用最终 prompt 编译 LLM，把全局角色表、每页分镜中间态、图片内文字、风格信息和参考图顺序整理成每页完整画师指令。该编译层负责解决角色外观与当前分镜、风格模板默认人物外观之间的冲突，并保证同一任务内固定角色和临时角色全局一致。最终生图 prompt 编译优先使用 LIO/Google JSON 通道；如果该通道未配置或调用失败，任务应明确失败，不自动退回其他文本模型。
   - 完整故事模式下，每张图片必须包含对应 panel 原文，文字必须逐字一致，不能额外添加“旁白”“字幕”“标题”等标签；如果原文直接引语已经在 `visual_prompt` 中绑定到人物说话动作，后端在最终 prompt 编译前会从旁白文字计划中确定性移除这段重复对白，最终只画一次这句台词，使用对白气泡，旁白框只保留剩余叙述文字；如果剩余叙述只是不完整的短促说话引导语，则不再额外生成旁白框。故事方案模式下，每张图片必须包含图文设计中的图片内文字，并可按当前 panel 需要包含标题、旁白和内心 OS；人物对白从 `visual_prompt` 读取并画成对白气泡。提取分镜模式下，每张图片必须区分旁白框、对白气泡和内心 OS 思想气泡或心理独白框，但对白来源是 `visual_prompt`，不是 `image_text.dialogue`。最终 prompt 可以使用页级画师指令结构描述全域场景、分格、人物完整描述和文字位置，但必须明确中间态字段名只用于理解结构，不要把字段名画进图片。所有文字字号偏大、清晰可读。所有指定图片内文字只能出现一次，不能在上下分格、多栏或不同分屏里重复绘制同一段文字；如果是分格页面的整页旁白，最终生图 prompt 必须约束为只使用一个旁白框，除非文字列表已经明确拆成上格旁白、下格旁白等对应文字。文案应短、清楚、与画面强相关；旁白优先补充前因后果、人物关系、剧情信息或来自内容提取的原文，不只复述画面状态。如果任务勾选 `去掉画面文字`，上述文字结构仍保留用于任务追踪和后续视频旁白，但最终 prompt 编译层必须把图片内文字字段视为画面理解材料而不是绘制目标，最终生图提示词必须追加最高指令，并且不得包含 `【文字】` 段、旁白/字幕/标题/对白/内心 OS 的写入指令、文字区布局或任何其他可读文字绘制要求。
   - `prompt` 模式下，最终 prompt 编译 LLM 必须理解任务保存的 `style_prompt_snapshot`，先处理风格与角色、分镜之间的冲突；后端在发送图片 Provider 前还必须把完整 `style_prompt_snapshot` 显式拼接到最终生图 prompt 中，用于加强画风、人物比例、线条、色彩、构图、文字呈现和整体质感的一致性。该显式风格模板不得覆盖已锁定的固定角色或临时角色外观。所有正式 panel 生图和单 panel 修改最终发送给图片 Provider 的 prompt，第一行必须固定写明任务画面比例，并要求严格按该宽高比构图和出图；风格模板、参考图说明和最终画面指令都必须排在比例约束之后。`image` 模式下，最终 prompt 不再把大段 `style_prompt_snapshot` 作为风格来源，风格由任务快照中的参考图传入模型控制。完整故事模式的图片文字固定为 panel 原文；故事方案和提取分镜模式必须把分格布局、旁白和内心 OS 保存在结构字段中，人物对白必须写进 `visual_prompt`。
   - `image` 模式下，任务创建和重试必须保存当时的风格参考图快照；正式 panel 生图和单 panel 修改只使用任务快照，不实时读取风格库当前参考图。未开启人物参考时只携带风格参考图；开启人物参考时先按固定顺序传入该 panel 绑定的人物参考图公网 URL，再传入风格参考图公网 URL，并把相同顺序提供给最终 prompt 编译 LLM。统一生图 Gateway 的参考图请求体使用 `image`、`image2`、`image3` 独立字段，不使用 `images` 数组，也不把参考图转成 `data:image/...;base64,...`。
   - 如果任务开启 `最后一张真人图片`，最后一个 panel 是明确的单页风格覆盖：不携带任务人物参考图和风格参考图，不拼接任务漫画风格提示词，最终 prompt 必须明确要求真实摄影、真人自拍、真实人物、真实环境和真实光线，并明确禁止漫画、手绘、绘本、水彩、线稿、二次元、卡通或插画纸张质感。非最后一个 panel 不受影响。
   - 将每个 panel prompt 发送给该风格绑定的图片模型。
   - 每张 panel 图成功产出后扣 `1` 积分；任务重试只对本次重新产出的成功图扣费；单 panel 修改重新生成成功后同样扣 `1` 积分。

6. 查看和下载结果。
   - 在任务详情页查看生成图片。
   - 从任务列表打开详情时，浏览器地址必须进入 `/tasks/{task_id}`；刷新、复制链接或浏览器前进后退时必须保持同一个任务详情。
   - 开启人物参考时，任务详情只展示人物参考图、人物姓名和年龄/阶段，不展示内部人物分析、使用 notes 或完整人物设定；人物参考图可以点击放大预览，并支持下载或打开原图；如果该人物参考图由任务生成链路产出且保存了最终生图提示词，用户可以在前端点击查看完整提示词。
   - 点击图片放大预览。
   - 生图提示词不在任务列表或详情首屏预加载；用户在任务详情里点击查看时，前端再按 panel 加载图片文字和 prompt，并以弹窗展示完整生图提示词。
   - 预览图片左右切换时，新图片加载完成前必须显示空白/加载态，不能继续显示上一张图片。
   - 一键下载所有生成图片，优先以压缩包方式提供；打包必须读取服务器本地已有资产文件，不能为了生成压缩包从公开 CDN 回拉图片，生成的 zip 也应作为本地资产由后端直接响应下载。
   - 如果任务来自 `DY 爆款复刻` 自动创建流程，下载 zip 还必须包含 `meta.txt`，内容为原抖音作品的标题、描述和标签；非 DY 来源任务不额外生成该文件。
   - 普通用户只能看到自己的任务；Admin 可以看到所有用户的任务。
   - Admin 在任务列表页可以通过用户下拉筛选指定用户的任务，筛选条件必须发送到后端任务列表接口执行，不能只在浏览器中过滤当前页结果。

7. 联系维护者。
   - 普通用户和管理员都可以在左侧底部用户信息区看到轻量联系入口。
   - 鼠标悬浮或键盘聚焦联系入口后，页面展示微信二维码，并提示使用微信扫一扫。

8. 提取抖音内容文案。
   - 用户进入 `内容提取` tab。
   - 输入抖音分享文本或作品链接；分享文本中可能包含口令、标题、话题、说明文字和短链。
   - 后端从输入中解析真实抖音 URL，例如从整段分享文案中提取 `https://v.douyin.com/Vcpjpg3pcMk/`。
   - 用户创建内容提取任务后，后端先保存一条真实任务记录并返回，列表立刻展示 `处理中` 状态。
   - 后端随后在同进程后台处理该记录：调用同机抖音下载服务下载图文或视频，并把下载媒体登记为 DoodleStory 资产；下载媒体登记完成后必须先提交数据库，让详情页可以在后续内容提取仍在处理时先展示图片。
   - 内容提取当前是同进程后台任务，不能跨后端进程重启继续执行；后端启动时如果发现上一进程遗留的 `processing` 内容提取记录，必须标记为失败并写入明确错误，避免列表长期卡在处理中。
   - 如果作品是视频，后端从下载服务返回的本地原始视频路径分离音频，再调用 SiliconFlow 音频多模态能力转录原始口播、旁白或对白。
   - 如果作品是图文，后端按图片顺序逐张把下载服务返回的原始图片登记后的公网 URL 输入视觉理解模型，每次请求只含一张图；模型只输出该图实际可见的分格、构图、人物、动作、表情、环境、道具、色彩、光线、旁白、对话、内心 OS 和文字布局。后端为每个成功结果确定性添加 `第X页` 并按原顺序合并，不依赖模型生成页码。任意图片在火苗失败且 LIO 最多 3 次请求仍失败时，整个内容提取任务失败，不跳过该图。
   - 页面以内容提取任务列表为入口；创建任务使用弹窗，详情查看使用弹窗。
   - 任务完成后不自动打开详情；用户从列表点击任务行查看详情。
   - 列表页只加载内容提取摘要，不加载所有图片；完整媒体只在打开详情后按需加载。
   - 详情页以最终内容提取结果为主；下载后的媒体只作为辅助预览，多图默认折叠。
   - 下载后的图片媒体允许点击放大预览，并可在同一批图片内切换。
   - 内容提取结果存在时，详情页可点击 `提交任务`，跳转到任务页并以 `提取分镜` 模式预填创建任务。
   - 内容提取记录可以保存自动关联的生成任务 ID、任务创建状态和任务创建错误。自动创建任务失败时，不覆盖已经提取出的内容；用户仍可复制内容或通过详情页手动提交任务。
   - 内容提取记录保存下载服务返回的原作品标题、描述和标签。当前只把 `title`、`description` 和 `tags` 作为后续复刻下载元信息，`author_name` 和 `publish_timestamp` 暂不进入 DoodleStory 业务数据。

9. 管理音频参考。
   - 用户进入 `音频管理` tab。
   - 用户填写名称和可选描述，并上传参考音频文件。
   - 用户上传音频时必须同时设置产出语速，语速范围为 `0.5 - 2.0`。
   - 前端选择音频文件后立即调用后端本地 Whisper 转写接口；后端必须把转写结果统一转换为简体中文，转写过程中不允许保存。
   - 转写成功后页面展示只读识别文本，并允许保存音频参考；转写失败时保留表单并显示错误，不能保存。
   - Provider、模型、音色名等非必填高级字段不暴露给前端用户。
   - 音频参考支持编辑，但只能编辑名称、描述和产出语速，不能替换参考音频文件、参考文本、Provider、模型或音色名。
   - 音频参考支持测试试听：用户输入测试文本后，后端使用该音频参考注册或复用 voice，并按当前语速生成一次性音频流供前端试听；测试音频不保存为资产，也不写入测试历史。
   - 音频参考列表必须紧凑展示，不常驻长条原生播放器；原始参考音频只能通过紧凑入口打开或试听。
   - 音频参考列表支持搜索和分页，只展示当前用户自己的音频参考；Admin 可以看到全部音频参考。
   - 删除音频参考采用软删除，从音频库隐藏；历史视频任务继续使用创建时保存的音频参考快照。

10. 创建视频任务。
   - 用户进入 `视频任务` tab。
   - 用户输入故事正文，选择图片数量模式，选择现有风格，选择一个参考音频。
   - 提交后后端先创建一个普通生成任务，复用当前任务链路完成故事切分、旁白结构、人物参考和图片生成。
   - 视频任务创建出的上游图片任务必须默认启用 `去掉画面文字`，让视频素材图默认不包含画面文字；普通图片任务的默认值仍保持关闭。
   - 视频任务保存并关联上游生成任务 ID、参考音频快照、产出语速快照和任务状态。上游图片任务未完成时，视频任务显示等待图片生成。
   - 上游图片任务失败时，视频任务必须显示明确失败原因，不能静默创建视频或返回占位结果。
   - 上游图片任务成功后，视频任务后续阶段才允许把 panels 中的旁白/原文文本转为音频，并把图片与音频提交给图文视频生成服务。
   - 提交给图文视频生成服务的 episode resolution 必须跟随上游图片任务的 `style_aspect_ratio_snapshot`；默认配置的 9:16 仍为 `1080x1920`，横版 16:9 应为 `1920x1080`。如果风格比例快照无法解析，视频任务必须明确失败，不能静默回退到 9:16。
   - 在图文视频服务真实接入前，视频任务不能伪造音频或视频产物，也不能把等待后续实现显示为成功。
   - 失败的视频任务支持用户手动重试。若失败来自上游图片任务，重试应复用图片任务重试链路并让视频任务回到等待图片状态；若上游图片已经成功，则按失败阶段从旁白音频或图文视频提交阶段继续重试。重试不自动删除历史资产文件，也不引入 provider 兜底。

11. 管理积分和用户。
   - 普通用户进入设置页后，可以查看当前积分余额、占用积分和使用说明；积分流水默认不加载，用户点击 `查看明细` 后才分页加载。
   - 普通用户可以在设置页输入激活码兑换积分；兑换成功后余额立即刷新，并写入积分流水。
   - 设置页必须展示当前用户最近 `1` 天、`7` 天和 `30` 天的积分消耗折线图，数据只统计成功出图扣费流水。
   - 设置页积分流水明细需要支持分页，并提供 `消耗积分` 和 `重置积分` 快捷筛选。`消耗积分` 对应成功出图扣费流水，`重置积分` 对应管理员调整流水。
   - Admin 通过单独的 `用户管理` tab 查看用户列表、用户积分余额、任务数量、成功图片数、消耗积分和注册时间。
   - 用户管理列表需要分页，默认每页显示一批用户，并支持按邮箱或昵称搜索。
   - Admin 通过单独的 `积分消耗` tab 查看全站成功出图扣费大盘，包括最近 `1` 天按小时聚合、最近 `7` 天和 `30` 天按日期聚合的柱状图、总消耗积分、扣费次数和消耗用户数。
   - `积分消耗` tab 需要支持按用户筛选。筛选后柱状图、汇总指标和明细列表都只展示该用户的成功扣费流水。
   - `积分消耗` tab 需要提供成功扣费明细分页，明细展示时间、用户、扣减积分和关联任务。
   - Admin 可以手动增减用户积分，但必须填写原因；调整结果写入积分流水并记录管理员操作者。
   - Admin 可以在用户管理页生成固定面额的激活码，并可查看激活码状态、兑换人和兑换时间。

## YouTube 频道与发布

- 第一版仅由管理员管理和发布 YouTube 频道。DoodleStory 使用后端环境变量中的外部发布服务
  API Key，不在产品内实现 YouTube OAuth 或新账号绑定。
- 频道以远程 `channel_id` 为稳定标识，保存远程名称、Handle、状态和同步数据；频道别名、
  账号定位、目标受众、阶段目标、AI 说明、运营备注和对标账号属于 DoodleStory 本地知识，
  远程同步不能覆盖。
- 每个频道账号可以绑定一个当前创作风格，多个账号可以复用同一风格。已有频道允许处于“尚未
  绑定”的待配置状态，但系统不得自动分配默认风格；管理员只能绑定启用且未删除的 Style，
  更换绑定只影响后续新建内容，历史任务和 Native Agent Run 继续使用创建时的风格快照。
- Native Agent 的“创作账号”与真实 YouTube 发布目标是两个独立上下文。选择创作账号后，后端
  必须从账号绑定唯一推导 Style 并锁定名称、Prompt、模型、比例和参考图快照；账号未绑定、
  绑定风格不可用或请求显式传入不同 `style_id` 时必须拒绝创建。没有选择创作账号的实验性
  Run 仍可直接选择 Style。
- Native Agent 的 Skill、创作账号、直接 Style、YouTube 发布频道和审核视频统一通过输入区
  `@` 资源菜单添加，不使用常驻下拉配置栏。每一轮提交前都可重新增删资源；已选资源显示为
  可移除结构化标签。创作账号与直接 Style 互斥，账号标签必须展示其绑定 Style，但请求仍只
  提交账号 ID 并由后端唯一推导 Style。发布频道被移除时，审核视频和本轮发布参数必须一并清理。
- 被频道账号绑定的 Style 不允许删除，也不能自动解绑；风格停用后保留绑定事实，新内容创建时
  明确提示管理员先更换账号风格。
- 管理员 Native Agent 可以通过只读
  `get_account_creation_context(account_name)` Tool 按账号别名、频道标题、Handle 或远程
  `channel_id` 读取上述本地创作知识，不要求用户知道内部账号 ID。只有唯一精确匹配才能返回
  完整策略、统计、对标账号和最多 10 条近期视频；重名或部分匹配只返回最多 5 个候选并等待
  确认。结果不得包含账号邮箱或原始 Analytics JSON。
- 频道、频道分析和频道已发布视频均由用户点击按钮手动同步；第一版不增加定时循环、隐藏轮询或
  Webhook。已发布视频列表必须显式按 `channel_id` 过滤，不能读取无频道约束的全局视频池。
- 频道账号列表和单频道已发布视频列表均使用服务端分页，每页默认显示 10 条并返回准确总数；
  频道详情不嵌套加载完整视频关系，视频 Tab 通过独立分页接口读取当前页。列表使用稳定排序，
  搜索或状态筛选变化后回到第一页。
- 可发布视频必须关联一个真实成功的 `NativeAgentVideo.id`，保存视频 URL、封面 URL、默认标题、
  描述、标签、发布时间、AI 合成标记和审核状态。未审核或没有公网视频 URL 的视频不能发布。
- 一次发布由本地异步发布任务承载，保存频道、视频、提交参数快照和远程任务 ID；创建远程任务后
  当前 HTTP/Agent 请求立即结束，用户随后通过按钮手动获取状态。
- Agent 对话使用结构化 `@频道` 引用，展示本地别名并绑定稳定频道 ID。真实发布前必须展示频道、
  视频、标题、可见性和发布时间并取得用户明确确认。
- 发布成功后必须持久化 `NativeAgentVideo.id → PublishTask.id → youtube_video_id` 关联，同时
  保存 YouTube URL 和永久已发布视频记录，为后续按生成过程、账号和成片数据分析提供事实链。
- 外部创建接口没有幂等参数。网络结果不明确时不得自动再次创建发布任务；外部任务状态由本地
  明确映射为等待、执行中、成功、失败或用户取消。

## 产品优先级

1. 精确保留用户原始文本。
2. 通过风格基础信息、提示词、参考图、参考方式、测试生成和生图模型名，让风格调试明确且可重复。
3. 任务流程必须可检查：原始文本、panels、生成 prompts、模型和图片都应可追踪。
4. LLM 或图片生成步骤失败时必须可见，不能静默忽略。
5. 使用 Codex harness 作为后续实现工作的持久项目记忆。

## 技术形态

- 前端：React + Vite。产品 UI 设计见 `docs/design/ui.md`。
- 后端：Python + FastAPI + SQLAlchemy + Alembic。REST API 设计见 `docs/design/api.md`。
- 存储：关系型 OLTP 数据库设计见 `docs/design/database.md`。
- 现有生成链路外部集成：任务生成链路中的文本 JSON LLM 统一使用 LIO/OpenAI 兼容配置，当前线上主模型为 Gemini；不再把分镜结构化、故事方案规划、角色名提取、任务级人物提取、panel prompt、最终生图 prompt 编译或 policy prompt 改写发送到 SiliconFlow 文本模型。用户已明确授权文本模型兜底：当 LIO/Gemini 当次请求失败时，后端使用 `TEXT_FALLBACK_*` 配置的 OpenAI 兼容文本模型继续请求；进入兜底后，同一次调用的后续重试只使用该兜底模型，不再切回 Gemini。图文内容提取逐图使用 `TEXT_FALLBACK_*` 当前指向的火苗多模态模型作为主平台，单图失败后反向切换到 `LIO_*` 并最多请求 3 次，不把 SiliconFlow/Qwen 作为降级路径；风格提示词提取仍只使用 `TEXT_FALLBACK_*` 配置的 `gpt-5.4`，失败时不切 LIO。SiliconFlow 仍保留给视频音频转写和用户角色参考图外观理解等多模态能力。生图默认使用 `docs/api_v4.md` 中已同意的 OpenAI Images 兼容统一服务（`IMAGE_PROVIDER=qy`），生图 API key 和 base url 从 `IMAGE_GATEWAY_API_KEY`、`IMAGE_GATEWAY_BASE_URL` 读取。为临时排查内部 QY 多图不稳定，允许通过 `IMAGE_PROVIDER=xgapi` 显式切到 xgapi 直连；该切换不是 fallback，所选 provider 失败时任务必须明确失败，不自动切换到另一个 provider。无论使用 QY 还是 xgapi，请求体里的 `model` 都必须来自任务保存的风格模型快照，不允许用环境变量或代码默认值覆盖用户在风格中指定的模型；如果任务风格模型为空或 provider 不支持该模型，必须明确报错。当前 QY 可用生图模型精确限定为 `gpt-image-2`、`gpt-image-2(线路XF)`、`gr-image-2`、`nano-banana`、`nano-banana-hd`、`nano-banana-pro`、`Tongyi-MAI/Z-Image`、`Qwen/Qwen-Image`、`baidu/ERNIE-Image-Turbo`、`gemini_3.1_flash_image_preview`、`gemini_3.0_pro_image_preview`、`gemini_3.1_flash_image_preview_4K`、`gemini_3.0_pro_image_preview_4K`、`gemini-3.1-flash-image-preview` 和 `gemini-3-pro-image-preview`。QY 请求 `/v1/images/generations`；QY 图片接口只对已验证的 `1:1`、`16:9`、`9:16` 显式传 `size`，`3:4` 和 `4:3` 这类画面比例只写入最终生图 prompt，不把视频/Grok 的 `864x1152`、`1152x864` 映射误传给图片接口；xgapi 无参考图请求 `/v1/images/generations` JSON，有参考图请求 `/v1/images/edits` multipart，后端必须先下载任务资产公网 URL 对应的参考图，再用重复的 `image` 文件字段提交，不把参考图 URL 数组放进 JSON。xgapi 图片接口只允许 `auto`、`low`、`medium`、`high` 质量参数；当环境里沿用 `1k`、`2k`、`4k` 配置时，xgapi generation 和 edit 请求都统一发送为 `high`。QY 的参考图直接使用资产公网 URL；xgapi 的参考图只在发起 edit 请求前下载为请求文件，不改变资产事实来源。返回的 `data[0].url` 或 `data[0].b64_json` 必须立即下载或解码并保存为 DoodleStory 资产；未列入清单或未配置所选 provider 的模型/API key 必须明确报错。
- Agent 当前真实基线由 Sprint 105–115 完成：除 Conversation/Message/Run/Step 外，已有版本化 `agent_artifacts`、hash 绑定 `agent_approval_requests` 和用户安全 `agent_events`；`agent_runs.task_id` 继续关联同一 `generation_tasks`。正式漫画创建加载 `idea-to-comic`，生成 2–8 Panel 方案并停在 `waiting_for_input`，owner 批准后才创建 Task/Panel/Image Job；页面通过 SSE cursor 读取持久化事件，不再轮询 Agent 进度。资源输入支持显式 Style、Character、Task、Panel 与 Image Version，并在入队前完成权限、状态、父子关系和组合校验；消息保存规范引用与安全快照，模型重放不接触 owner、存储路径、密钥或无关任务。Character 会真实进入任务角色快照和图片参考，Task 引用进入同一 GenerationTask 的只读续作，不开放版本写操作。
- Sprint 107/108 已完成的统一 Shell 和旧 Task 详情跳转保留为历史实现记录，但其产品方向已被 2026-07-23 的最新决定替代。Sprint 111 已把 `/agent` 拆为独立 Agent 模块；Agent Task 仍与传统列表共享同一个 GenerationTask，但使用 `/agent/{conversation_id}/tasks/{task_id}` AI 专属只读检查器。检查器数据只允许通过 `GET /api/v1/agent/conversations/{conversation_id}/tasks/{task_id}` 读取，并同时校验当前用户拥有 Conversation、Task 经 Agent Run 关联到该 Conversation、Task owner 与 Conversation owner 一致；Admin 也不能越权读取他人的 Agent 会话任务。
- Agent 漫画 V1 的目标架构是“通用创作 Agent + 按需加载 Skill + 原子 Tool + 通用 Runtime”。Skill 定义创作方法、步骤、质量门槛和确认点；Tool 只代表真实基础能力，V1 使用 `generate_image` 与 `inspect_image`；Runtime 负责权限、状态、预算、幂等、Provider 路由、等待、恢复、暂停、取消、安全事件和 MLflow 观测。不为每种创作方式增加硬编码 Workflow，不把旧故事拆分、复杂 Prompt 拼接或重试编排包装成 Tool。
- Durable Agent Runtime 将一次完整用户目标建模为 Workflow Run；Run 内保存受控动态 Task 图，Task 的每次真实执行是 Attempt，用户可见产物是版本化 Artifact，人工介入点是 Gate，恢复锚点是 append-only Checkpoint，外部副作用通过 Tool Effect 账本保存。Skill 可以声明允许的 Task 类型、阶段、质量门槛和 Gate 意图，模型可以建议后续计划，但 Runtime 必须验证依赖无环、输入 Artifact、权限、预算和完成契约。批准非终态 Gate 只能推进同一 Run 的后继 Task，修改只失效目标及下游；已终态 Task、Attempt、Artifact、Gate 和 Checkpoint 不得覆盖。SDK Session 仅属于单个 Attempt，不能替代业务恢复事实。
- Sprint 117 已把产品运行时 Skill 的正式事实来源迁移为数据库中的 `agent_skills` 与不可变 `agent_skill_versions`：用户只编辑名称、适用场景、纯文本正文和可选的相关 Tool 说明，不编写 JSON/YAML/代码；Tool 勾选用于帮助用户理解 Skill 可能使用的能力，不作为对话选择或 Run 创建门禁，Runtime 实际开放的 Tool 仍以当前代码注册能力为准。草稿用 revision 做乐观并发控制，发布使用幂等键创建递增版本并默认启用，历史版本只能读取或显式重新启用。系统 `idea-to-comic` 由原受控文件幂等种入数据库，普通用户只读且可复制为个人草稿；`agent_runs.skill_version_id` 固定准确发布版本，Skill 后续发布、切换或归档不得改变已有 Run。基础 Agent 只读取可用 Skill catalog，选定并固定准确版本后才加载完整正文；skill_version_id、name、version、内容 hash、选择来源和相关 Tool 说明写入 AgentStep、安全 Event 与默认脱敏的 MLflow span。
- Sprint 113 已实现最小 Skill/Tool Runtime：服务启动扫描受控 Skill 根目录，校验目录/name、frontmatter、正整数版本、重复 name、文件大小和路径边界，并自动计算完整文件 SHA-256；catalog 不包含正文。代码级 Tool Registry 当前只注册 `load_skill` 与 `generate_image`，所有 schema 拒绝额外字段，模型不能提供数据库 Session、用户 ID、Provider、API key、预算或幂等键。Generic Tool Executor 在副作用前提交 `tool_call` AgentStep，按 Run/Conversation/已授权 Task/Panel 构造 RuntimeContext，保存 wait checkpoint，并在恢复模型前提交 `tool_result`；稳定幂等键重放只复用既有 Step/job/result。当前固定两格正式链路仍使用旧 ComicPlan 规划入口，但真实图片 job 创建已经通过统一 Executor/adapter 执行；没有新增数据库表或 Workflow DSL。
- 首个生产 Skill 为 `idea-to-comic`：用户提交 Idea 与一个真实风格后，Agent 补齐并检查故事、规划 2–8 个连续 Panel、生成简洁的最终单图 Prompt，先保存用户可见 ComicPlan Artifact 并进入 `waiting_for_input`；只有 Conversation owner 批准与当前 Artifact hash 一致的方案后，Runtime 才能创建 GenerationTask、Panel 和图片 job。请求修改会创建方案新版本，不能覆盖历史或提前占用图片积分。
- Agent 用户安全进度使用数据库持久化 Event 和 SSE 展示，包括 Skill 加载、Artifact、Approval、Tool 开始/进度/完成/失败和最终消息；不得展示 chain-of-thought、完整系统 Prompt、Provider 原始响应或敏感 URL。断线重连从事件 cursor 补发，不得重复副作用；未经明确授权不增加隐藏轮询兜底。
- `@风格/@角色/@任务/@Panel/@图片版本` 是用户显式选择的结构化上下文。Runtime 必须在消息入队前完成所有权、状态、父子关系与组合校验，并用数据库规范数据覆盖客户端 display name。引用已有 Task 表示继续同一个 GenerationTask，不创建新任务；引用 Character 必须真实进入任务角色快照和图片参考链路。
- Panel 修改只为目标 Panel 创建新的 GeneratedImage 版本；恢复历史版本只切换 `is_current`，不调用图片 Provider、不扣积分。`inspect_image` 提供真实视觉证据，单个用户修改 Turn 最多自动创建一个额外版本；VL 失败、预算耗尽或需要判断时进入 `waiting_for_input`，不允许无限自动循环。
- Native `inspect_image` 使用 `SILICONFLOW_VISION_MODEL` 对当前 Run 的真实图片执行检查；该调用禁用客户端自动重试，技术失败明确结束当前媒体 Gate，不回退 `TEXT_FALLBACK_MODEL` 或其他 VL Provider。
- MLflow 只承担 Agent/Skill/Tool/Provider/Approval 的观测和 Evaluation 输入，DoodleStory 数据库仍是业务状态、恢复与权限事实来源。默认不记录用户全文、完整 Prompt、图片 URL、API key 或 Provider 原始响应。
- Agent MLflow 基线锁定 `mlflow==3.14.0`。默认 `MLFLOW_TRACING_ENABLED=false`，关闭时不导入 MLflow、不连接 Tracking URI；启用时 URI 与 Experiment 必须在启动阶段验证。每个 Agent Run 使用 `agent_run_id` 根 trace tag 唯一检索，模型 attempt、Tool Call、图片等待、Tool Result 和 finalize 作为同一 trace 的子 span；不新增 MLflow trace 数据库列，不用 trace 驱动恢复、权限、预算或取消。
- `MLFLOW_TRACE_CONTENT=false` 时，MLflow span processor 在客户端导出前覆盖 inputs/outputs，并拒绝 Prompt、消息正文、完整 URL、内部路径、Authorization 和已配置密钥。观测初始化或运行时上报错误必须记录明确 `observability_error`；上报错误不能回滚已经提交的图片、消息、积分或 Agent Run 业务状态。
- Sprint 117 已实现用户 Skill CRUD、不可变发布版本、`@Skill` 与由数据库发布版本驱动的通用内容创作 Agent Loop；每个 Run 第一版最多使用一个纯文本 Skill。Tool 必须先由 Runtime 代码注册；Native Agent 再按本轮固定 Skill Version 的 `tool_names_json` 构造实际函数列表，未勾选的已注册 Tool 不传给模型。旧 Agent Runtime 的历史 Tool 语义不因此增加新能力。不支持脚本、MCP、多 Skill、Workflow DSL 或用户自定义 Tool。漫画方案继续使用最小 ComicPlan control action 和既有 Artifact/Approval adapter，但正式路径不再按 Skill 名称或 `style → create_comic` 资源路由编排。用户 Memory 与抠图继续顺延；多媒体能力必须先新增原子 Tool，再由 Skill 组合，不预建通用媒体 Workflow。正式 Evaluation 推迟到用户确认功能路线冻结后的最后阶段，届时重新编号并确定 `GO_INTERNAL/NO_GO` 门槛。
- Sprint 118 已补齐 Skill 管理的产品导航闭环：传统工作台主侧栏直接提供 `/agent/skills` 入口，独立 Agent Studio 的 Skill 管理侧栏提供返回 `/tasks` 的入口；两端继续使用稳定 URL，不复制 Skill 编辑器，也不重新合并两套 Shell。
- Skill 管理使用明确的列表、详情和编辑路径：`/agent/skills/{skill_id}` 只读展示完整正文、状态、权限、Tools、revision、当前版本和更新时间，`/agent/skills/{skill_id}/edit` 只用于个人且未归档 Skill 的修改。列表对所有 Skill 提供“查看详情”，对可编辑的个人 Skill 额外提供“编辑”；系统 Skill 详情只读且可复制，已归档个人 Skill 需先恢复才能编辑。
- Sprint 142 将 Skill 软归档统一呈现为 Disable / Enable：`archived` 表示 Disabled，
  定义、不可变版本、`active_version_id` 和历史 Run 全部保留，但它不能进入新的 `@Skill`
  查询或创建新 Run。管理员可以 Disable / Enable 系统 Skill，普通用户只能改变自己的
  Skill 状态；系统 Skill 正文和版本仍只读。启动种子不得把已 Disabled 的系统 Skill
  自动恢复为 `published`。
- Sprint 119 已完成用独立数据模型重建正常 `/agent` 执行入口：当前最小 Runtime 直接使用 Agents SDK
  `Agent(tools=[generate_image])` 和 SDK 自带 Loop，Skill 负责故事改写、分镜、完整图片 Prompt、
  真实图片 Review 与是否重画。`generate_image` 返回 `ToolOutputImage` 给同一个多模态模型；
  Runtime 不再按 Style、Skill 名称、Panel 数量或漫画阶段编写 Python 业务分支，也不启动旧
  Agent 队列。新路径只复用用户、发布版 Skill、Style、文件存储和图片 Provider，运行状态写入
  `native_agent_conversations/runs/items/images`，不写旧 Agent Step、ComicPlan、Artifact、
  Approval、GenerationTask、Panel 或 GeneratedImage。第一版 Tool 串行执行；积分、审批和正式
  Evaluation 明确留待后续独立合同。
- Sprint 120 已把 Native Loop 接入现有 MLflow 3.14.0 脱敏观测层：每个 Run 以
  `native_agent_run_id` 创建唯一 `native_agent.run` 根 Trace，模型 SDK Loop、
  `generate_image` Tool 和图片 Provider 分别作为子 Span，记录模型、状态、调用次数、延迟、
  图片尺寸和 Provider request ID。仓库提供只监听 localhost、SQLite metadata、artifact
  named volume、健康检查和单 worker 的 `docker-compose.mlflow.yml`；开发环境显式启用时后端
  启动必须连接成功。本机为了查看模型调用与后续内容评估可显式设置
  `MLFLOW_TRACE_CONTENT=true`，生产与示例默认 `false`；两种模式都必须清除密钥、
  Authorization、URL 和内部路径。正式 Evaluation 规则仍为 Deferred。
- Sprint 122 已把 Native Run 从阻塞式 HTTP 执行改为“数据库 queued Run + 进程内单 Worker”：
  POST 只完成校验、持久化和入队并返回 `202 Accepted`，Worker 只接收 Run ID，再从数据库读取
  Skill、Style、用户输入和当前状态。启动时 queued Run 重新入队；running/waiting Run 因模型
  Loop 没有可安全重放的 checkpoint，会明确标记为中断失败，不自动重复可能已发生的生图副作用。
  每个 Run 提供 owner-only SSE 快照流，前端按 Item/Image/终态实时更新对话时间线和图片，并在
  新状态到达时自动滚动；刷新仍从数据库详情恢复。Native MLflow 中 `generate_image` 保持
  `TOOL`，内部图片 Provider 使用 `TASK`，成功和失败显式记录 `OK/ERROR`。MLflow 3.14 Trace
  图的 Tool 暗红色属于 Span 类型配色，不能作为错误判断；执行结论以 Trace/Span 状态字段为准。
- Sprint 123 在保持 OpenAI Agents SDK 负责 Tool Loop 的前提下，为 Native Run 增加最小可恢复
  Runtime。`native_agent_steps` 记录模型、Tool 和 final 的 prepared/running/succeeded/failed/
  unknown 边界；`native_agent_context_items` 通过 Agents SDK Session 协议保存完整模型上下文；
  `native_agent_events` 保存 Run 内单调 sequence 的结构化进度和分批文本 delta。Runtime 使用
  SDK `tool_call_id` 派生生图幂等键，Provider 调用前先提交 Tool Step；成功图片、Tool Result、
  输出引用和完成 Event 在同一事务保存。同一成功调用重放时直接返回已有图片，不重复请求
  Provider。服务重启只恢复纯模型中断，或所有成功 Tool 都能在 SDK Session 找到对应
  `function_call_output` 的 Run；prepared/running Tool、unknown/failed Tool，或成功 Tool 缺少
  SDK 输出时明确标记 unknown 并失败，不自动重画。SSE 按 Event sequence 提供 `id`，支持
  `Last-Event-ID` 和 `after` 补发，Run snapshot 只是事件后的当前投影，不再充当唯一进度来源。
  Worker lease、heartbeat、多实例领取和人工审批仍不在本阶段范围内。
- Sprint 124 为 Native Agent 新增真实 `generate_speech(text)` Function Tool。Provider 固定使用
  火山引擎 V3 单向流式 TTS、Resource `seed-tts-2.0`、Model
  `seed-tts-2.0-standard`、Speaker
  `zh_female_xinlingjitang_uranus_bigtts`、MP3/24kHz/正常语速和正常音量；模型只能提供非空
  `text`，不能覆盖 Provider、模型、音色或音频参数。接口按连续 JSON frame 解码 Base64 音频，
  必须收到 `20000000` 成功终态；HTTP、Provider code、解析、空音频或配置错误均明确失败，不
  fallback、不生成空资产。成功结果保存为 `native_agent_audios` 与 `generated_audio`
  FileAsset，Tool Step、Result、Event、调用计数和 Provider request ID 可审计；同一 SDK
  `tool_call_id` 只允许一次副作用，成功重放复用已有资产。音频只允许当前 Native Conversation
  owner 或 Admin 读取，并通过 SSE Run snapshot 在对话内播放。Skill 编辑页的 Tool 勾选对
  Native Runtime 是发布版本白名单：`generate_image`、`generate_speech` 仅在被选择时暴露；
  `inspect_image` 仍属于旧 Runtime 能力。纯语音 Run 不要求 Style；若 Skill 允许并实际调用
  `generate_image` 但本轮没有 Style，必须明确失败，不使用隐藏默认 Style。
- Sprint 125 为 Native Agent 新增真实
  `render_story_video(scenes, bgm_asset_id?)` Function Tool。V1 只使用固定
  `narrated-panel-v1` Remotion 模板：1080×1920、30fps、H.264/AAC、固定字幕样式和固定
  BGM 混音；模型只能为每个 Scene 提供当前 Run 的 `image_id`、`audio_id`、整段字幕，以及
  `static/zoom/pan` 七种 Motion Preset 之一。Scene 时长严格取对应 Native Audio 的
  `duration_ms`，不得由模型猜测。可选 BGM 必须是当前会话生成的语音资产或 owner 未删除的
  Audio Reference。成功 MP4 保存为 `native_agent_videos` 与 `generated_video` FileAsset，
  并保存模板、渲染器版本、Scene/BGM 快照、时长、帧数、fps 和分辨率；同一成功
  `tool_call_id` 重放复用原视频。Tool 仅在发布 Skill 勾选后暴露；对话 SSE 投影提供 owner
  可播放的视频，其他用户不能读取。Runtime 不接受任意 React/CSS、任意动画数值、视频素材
  混剪、逐字字幕或分布式渲染，依赖、Chromium、输入或编码失败都必须明确失败。
- Sprint 126 将 `narrated-panel-v1` 的 Composition 宽高改为跟随首张源图真实尺寸；H.264
  要求偶数尺寸时仅把奇数边向上补 1 像素，同一视频内图片比例不一致时明确失败。`image_id`
  可引用同一 Native Conversation 的历史 Native 图片，或当前 owner 已有 Generation Task
  中成功且 current 的图片，不能读取其他用户资产。火山语音在 Provider 未返回 duration 时
  必须使用本地 `ffprobe` 读取真实 MP3/WAV/OGG 时长，探测失败则语音 Tool 明确失败，不能把
  空时长或估算时长交给视频 Tool。
- 当前跟随首图尺寸的行为不能直接满足 Paynes Creek 锁定的 1920×1080 交付：Gateway 对 16:9 当前请求
  1792×1024，若 Provider 返回该尺寸，现有模板也会输出 1792×1024。Sprint 188 / G8-A 已设计但尚未实施
  版本化 `youtube_16_9_1080p` preset：保留旧 `source / narrated-panel-v1` 行为，新模板固定
  1920×1080、30 fps；源图仍需通过 2% 的 16:9 比例 Gate 和跨 Scene 0.01 规则，等比 `cover` 的基准中心
  裁切每边不得超过 1%，并在视频保存前用显式 `FFPROBE_EXECUTABLE` 核对真实 H.264 / yuv420p、AAC、
  尺寸、fps、流和时长。不得降低交付尺寸、拉伸、补黑边或信任 Node stdout 代替文件事实。
- Sprint 189 / G8-B 已设计但尚未实施冻结 Render Manifest Run：认证用户先通过无写入 / 无 enqueue 的
  preview 检查由服务端编译的 canonical snapshot 与 SHA-256，再携带 exact expected hash 明确确认 Scene
  顺序、Native 图片 / 音频 / 字幕 ID、Motion、审核记录 ref / hash、BGM 和固定 1080p preset；Run 创建时
  服务端从同 owner、同 Conversation、已成功来源 Run 和实际 FileAsset 重新编译，hash 一致才保存并
  enqueue。专用 `youtube-frozen-render` Skill 只暴露零参数 `render_story_video()`，运行时复验 snapshot、
  lineage 与实际文件 hash，模型不能重传或改变 Scene。同一 Manifest-bound Run 跨不同 Tool Call ID 也只能
  进入一次 Render；技术成功只进入 `rendered_awaiting_frame_evidence`，不得自动写 `pass_local_pilot`、
  创建发布任务或通过 Follow-up 修改 Manifest。
- Sprint 190 / G8-C 已设计但尚未实施成片逐镜帧证据包：只接受绑定上述 Manifest、固定
  `youtube_16_9_1080p / narrated-panel-16x9-1080p-v1`、1920×1080、30 fps 的已保存 Video。owner 携带
  Video 与 Render Manifest 的 exact SHA-256 创建独立数据库作业；服务端按每镜真实帧区间固定抽取淡入端点、
  安全起点、中点、安全终点和淡出端点，并从持久化 Subtitle cues 唯一定位事实限定词帧。Worker 必须重做
  ffprobe、完整解码和一次性 ffmpeg select，生成只含 canonical manifest、离线 HTML 和 PNG 的一个 ZIP
  Asset。Pack 成功才允许进入 `ready_for_full_watch_review`；像素统计、`blackdetect` 与证据完整性都不能
  代替审核人观看同一 Video SHA-256 后签字，也不得触发重渲染、自动重试或发布。
- Sprint 191 已设计但尚未实施 G8 不可变人工验收与严格发布登记门禁：当前客户端可在登记
  `PublishableVideo` 时直接提交 `review_status="approved"`，该状态不能证明某个 exact Video bytes、Render
  Manifest 和 Evidence Pack 已被完整观看。未来只允许成功 Pack 的 owner 先调用零写入 preview，由服务端
  复验 Video / Archive 实际 bytes 与四类 SHA-256，编译包含四个固定维度和
  `publication_authorized=false` 的 canonical snapshot；再携带 exact snapshot hash 提交一次不可编辑的
  `pass_local_pilot | needs_revision`。Manifest-bound 视频只能从通过的 Acceptance 进入严格
  `PublishableVideo` 路径，来源 Video、`approved` 与 synthetic 标志由服务端推导；创建 PublishTask 前再次
  复验 Acceptance lineage 和实际 Video hash，漂移时远程调用必须为 0。历史普通视频保持 Sprint 134 / 135
  路径，不把它当作 Manifest 成片的兼容 fallback。
- Sprint 127 把 Native 多媒体链路拆为三个可组合 Tool：
  `generate_speech(text, speed)` 只接受 0.5、0.75、1.0、1.25、1.5、2.0 六档倍速，并映射到
  Seed-TTS 2.0 的 `speech_rate=-50/-25/0/25/50/100`；`generate_subtitles(audio_id)`
  使用本地 faster-whisper 生成带 segment 起止时间的 WebVTT 资产；`render_story_video`
  允许每个 Scene 在整段 `subtitle` 与匹配音频的 `subtitle_id` 之间二选一，引用字幕资产时
  Remotion 只在 cue 时间窗口显示对应文本。字幕属于音频派生层并保存 provider、模型、语言、
  全文、cue JSON、时长和 owner 权限；Skill 发布版本可独立勾选这三个方法。
- Sprint 133 将系统自生成语音的字幕改为原文约束对齐：`generate_subtitles(audio_id)`
  必须读取对应 `NativeAgentAudio.text`，faster-whisper 开启词级时间戳并只提供时间锚点；
  最终字幕全文、cue 文字和 WebVTT 均使用语音生成原文，按原文标点和固定可读长度切分。
  Whisper 识别字符与原文规范化字符通过单调序列匹配映射时间，模型快照追加
  `source-aligned-v1`；原文为空、缺少词级时间戳或匹配率不足时明确失败，不保存未经校准的
  Whisper 文本，也不自动切换在线服务。
- 当前 Native 媒体仍有明确的 Run 边界：`generate_subtitles` 只接受本 Run 音频，
  `render_story_video` 只读取本 Run 的 `audio_id` / `subtitle_id`；Follow-up 会创建新 Run，不能把父 Run
  的音频或字幕当成新 Run 资产。需要“逐镜独立人工语音 Gate → 独立成片 Run”的流程在真实媒体前必须
  另行实现同一 Conversation 内的跨 Run 渲染引用：来源 Run 必须成功、Conversation 与 owner 必须匹配、
  Subtitle 必须绑定 Scene Audio，并在视频 Scene 快照中保存音频与字幕来源 Run ID。不得通过复制 / 移动
  资产、跨 Conversation 放宽权限，或把全部语音与渲染塞进一个未暂停 Run 来绕过人工审核。
  Sprint 187 / G7-0 已把未来实现固定为：保持 Tool 输入不变，由服务端推导来源；当前渲染 Run 继续可用
  自己的媒体，历史来源只接受同 Conversation、同 owner 且 `succeeded` 的 Run；Subtitle 还必须与 Audio
  的 ID 和来源 Run 同时匹配，新 Scene 快照保存图片、音频和字幕来源 Run ID。该合同当前仅设计就绪，
  尚未改变上述运行时事实。
- Sprint 129 将火山语音缺失 duration 时使用的媒体探测器改为显式
  `FFPROBE_EXECUTABLE`。本地启动脚本必须在启动后端前解析并校验可执行文件绝对路径，再将其
  传入服务进程；容器继续由 `ffmpeg` 包提供 `ffprobe`。不得依赖不确定的子进程 PATH，也不得
  用文本长度估算音频时长。
- Sprint 130 为 Native Agent Run 增加 owner 隔离且幂等的终止能力。Run 使用
  `cancel_requested → cancelled` 持久化状态；排队任务直接取消，执行中任务取消本地
  asyncio Agent Task，所有 prepared/running Tool Step 标记为 `cancelled`。取消请求提交后
  不得再开始新的图片、语音、字幕或视频 Tool，Provider 返回后的迟到结果不得保存或覆盖取消
  状态；同一 Conversation 在取消收敛前不得提交下一轮。Native composer 在活动 Run 时把提交
  按钮切换为“终止任务”，点击后显示“正在终止…”并禁用输入、选择器和按钮，直到 SSE 返回
  `cancelled`。已经被第三方同步 HTTP Provider 接收的请求无法由本地强制撤销或保证不计费。
- Sprint 131 统一时间契约：数据库继续保存 UTC，现有 SQLite `CURRENT_TIMESTAMP` 与
  `datetime.utcnow()` 产生的无时区值在 API 输出边界一律解释为 UTC；所有 `ApiData`、
  `ApiList`、Native Agent SSE 和普通 Agent SSE 的时间必须输出带 `Z` 的 ISO 8601 字符串。
  前端所有日期时间及今天/昨天分组固定按 `Asia/Shanghai` 展示，不依赖服务器或浏览器本地
  时区。不得把历史数据库时间整体增加 8 小时，也不得通过修改 SQLite Session 时区改变存储
  语义。
- Sprint 132 为 Native Agent 增加 Conversation 内最近 Run 原地重试。用户在已有会话提交去除
  首尾空白后精确等于“重试”的消息时，前端调用
  `POST /agent-loop/conversations/{conversation_id}/retry-latest`；后端按创建时间倒序选择最近
  Run，不创建新 Run，也不接收或采用提交区当前 Skill/Style，继续使用目标 Run 固定的 Skill
  Version、Style/模型快照、SDK Context 和成功资产。是否可重试必须同时检查 Run 与 Tool Step：
  Tool 失败但模型已用说明文字把 Run 收尾为 succeeded 时仍允许重试；真正完成、活动中、用户
  取消或存在 unknown Tool 的 Run 必须明确拒绝。已知失败 Tool 在同一 Step 上增加 attempt，
  首次重试必须使用原 Tool 名和原参数；模型未执行指定 Tool、改写参数或仍有 failed Tool 时
  Run 不得被标成成功。`retrying` 状态必须在服务重启后重新入队。
- Sprint 181 完成 Native Agent G2-A Run 路由快照基础。新 Run 创建前必须解析并验证部署默认
  `huomiao_responses` route、`NATIVE_AGENT_HUOMIAO_MODEL`、当前 `TEXT_FALLBACK_API_KEY` 与合法 HTTP(S)
  Base URL；失败返回 503，且不得写 Run、Item、Workflow 或 enqueue。成功后把
  `model_route_snapshot / model_provider_snapshot / model_api_shape_snapshot / model_snapshot` 原子保存，
  普通执行、文章 Workflow Compiler、Director、Writer、Reviewer、重试、恢复、Follow-up、API 与 trace
  均只读取这四个快照。历史 Run 固定回填为 `huomiao_responses / huomiao / responses` 并保留原模型；未知或
  矛盾的持久化组合必须在模型请求前使 Run 明确失败。`AGENT_MODEL` 继续只服务旧 Agent Router，不能作为
  Native 模型隐式回退。
- Sprint 192 完成 G2-B `siliconflow_chat_v1` 有界离线适配。默认 Route 仍只能是
  `huomiao_responses`；只有 Admin 可在 Run API 显式选择 SiliconFlow，并固定快照为
  `siliconflow_chat_v1 / siliconflow / chat_completions / deepseek-ai/DeepSeek-V3.2`。该 Route 只接受 Tool
  集精确等于 `generate_image + inspect_image`、有可用 Style 且无创作账号或 YouTube 发布上下文的 Run；
  普通用户、配置错误或能力越界必须在写库和 enqueue 前明确拒绝，不回退到火苗。
- SiliconFlow Native Provider 使用 Chat Completions、关闭 client / Runner retry、关闭 thinking，并用 SDK
  同一 Converter 对最终消息计数；含 system message 最多 10 条，11 条及以上必须在 HTTP 前失败，不截断、
  摘要或删除上下文。模型 Step 使用应用 `model_call_id`，另存可空 Provider response ID、route、model、
  execution attempt、ordinal、消息数、延迟与 usage；SDK `__fake_id__` 不得成为持久化身份。Chat 工具事件按
  `output_index + call_id` 隔离并由 Item done 合成参数完成，累计参数不一致、Provider ID 冲突或未完成 Tool
  参数都必须失败。
- 该 Chat Route 只向模型返回生图结果的文本 ID，不回传图片 data URL；同一 Run 最多一次新的图片 Provider
  attempt，必须对唯一图片完成一次真实 `inspect_image` 终态后才能正常结束，且不允许 Follow-up 绕过预算。
  G2 只记为 `pass_offline`：尚未执行真实 SiliconFlow G3，也不授权 S03 生图、媒体制作或发布。
- Agent 正常 `/agent` 与 `/agent/skills` 使用统一深色 Agent Studio 视觉；Native composer
  textarea 必须显式定义浅色文字、深色背景、placeholder、caret 和 focus，不能同时继承全局
  深色背景与局部深色文字。
- Sprint 137 为 Native Agent 新增 `capture_wechat_article(url)` Function Tool。Runtime
  在请求外部服务前只接受 `https://mp.weixin.qq.com/` 链接，通过多平台导入服务
  `/api/v1/import` 获取已调通的公众号抓取结果；完整 UTF-8 Markdown 正文必须登记为
  `external_content` 文件资产，来源 URL、标题、作者、发布时间、标签和指标登记为
  `native_agent_external_contents` 记录。Tool 只向模型返回稳定素材 ID、来源摘要和最多
  1600 字预览，不无条件注入完整长文。该 Tool 只有在固定 Skill Version 的白名单包含
  `capture_wechat_article` 时才暴露，Skill 管理页显示名称“微信公众号文章”。
- Sprint 138 为 Native Agent 新增 `inspect_youtube_channel` 只读 Function Tool，通过同级
  多平台导入服务调用官方 YouTube Data API v3。频道输入支持完整频道 URL、`@handle`、
  handle 文本和 `UC...` Channel ID；模型可按任务选择最近视频数、每条评论数以及
  `relevance` / `time` 评论顺序。Agent 边界为 1–5 条视频和每条 0–10 条评论，Import
  服务边界为 1–10 条视频和每条 0–20 条评论。
- YouTube 研究结果必须包含频道资料与统计，以及视频标题、完整描述、标签、发布时间、时长、
  播放量、点赞数、评论数和所请求的顶级评论。Import 服务真实下载频道头像和每条视频最高
  可用分辨率封面；Tool 向模型提供结构化文字与视觉输出，但不暴露 Import 服务端本地路径。
  任一官方 API 请求或图片下载失败时整次调用明确失败，不返回部分结果。
- `inspect_youtube_channel` 仅在固定 Skill Version 白名单包含该 Tool 时暴露。已有
  `publish_youtube_video` 也必须同时满足 Skill 白名单和已确认的结构化发布上下文，不能因
  对话携带发布参数而绕过白名单。公开研究不写频道快照，不包含 OAuth、YouTube Analytics、
  私有账号指标、视频下载、字幕或定时同步。
- Sprint 139 为 Native Agent 新增 `get_account_creation_context(account_name)` 只读
  Function Tool。用户只需说账号别名、频道标题或 `@Handle`，模型自行调用 Tool；Runtime
  根据当前 Run 找到 Conversation owner，并保持既有频道资源的管理员权限边界。匹配优先级为
  别名、Handle、频道标题、远程频道 ID，只有唯一精确命中才返回账号创作策略、频道汇总指标、
  最多 10 个对标账号和最多 10 条近期视频；部分匹配或同优先级重名只返回最多 5 个候选，
  不静默选择。Tool 不返回账号邮箱、原始 Analytics JSON，并且只在固定 Skill Version
  白名单包含该能力时暴露。
- Sprint 143 修复结构化 `@创作账号` 的 Context 断链：前端提交准确
  `creation_channel_id` 后，Run 创建必须在同一事务内把账号定位、目标受众、阶段目标、
  AI 定义、运营备注、频道指标、最多 10 个对标账号和最多 10 条近期视频保存为
  `creation_channel_context_json` 安全快照。普通 Agent 与多 Agent 文案的 Director、
  Writer、Reviewer instructions 必须直接注入该快照，不依赖模型调用
  `get_account_creation_context`；账号后续编辑不得改变旧 Run。未选择账号时不注入，
  快照解析失败时明确失败，不能静默退化成只有绑定 Style。
- Sprint 134 为 Native Agent 增加单 Skill 驱动的多 Agent 文案链路。系统
  `article-creation-team` Skill 在一份 instructions 中定义 Director、Writer、Reviewer
  的职责与固定协作顺序；每个 Run 首次执行时由一次 Workflow Compiler 模型调用理解完整
  Skill，输出结构化的角色局部 instructions、执行步骤、分支条件与质量门槛，并按 Skill
  content hash 保存到数据库 Checkpoint。Runtime 只校验固定角色与 Tool 能力边界，不通过
  Markdown 标题自行解析 Skill。Director 使用 OpenAI Agents SDK `agent.as_tool()` 调用两个
  只接收自身局部 instructions 的子 Agent，不使用 handoff。Writer 草稿、Reviewer 审稿和最终
  文案保存为带版本与内容 hash 的数据库 Artifact；最终稿创建 Approval 后根 Run 进入
  `waiting_for_input`，不占用 Worker。
  用户批准后同一 Run 以纯文本结果完成；要求修改时反馈写回同一个数据库 SDK Session，并将
  同一 Run 重新入队产生新 Artifact 版本。该 Skill 只开放 `write_article`、
  `review_article`、`submit_final_article`，不得生成图片、语音、字幕或视频。同一 Run 的
  Event sequence 必须通过 `native_agent_runs.event_sequence` 原子自增分配，不能使用
  `MAX(sequence) + 1`；父 Agent 流式事件与子 Agent Artifact 事件会并发写入。模型调用总数
  必须由 SDK LLM 生命周期覆盖 Compiler、Director 和所有子 Agent 的真实请求开始事件，
  不能再用父 Agent `response.created` 数量代替；每个 MLflow 根 Trace 标记
  `execution_attempt`、本次调用总数、完成数和角色拆分。
- Sprint 144–146 在保留现有 `/agent-loop` 页面、Skill、账号和 `@` 资源交互的前提下，以
  数据库 Durable Workflow 补强文案与媒体控制面。每个 Native Run 关联唯一 Workflow，Task、
  Attempt、Checkpoint、Artifact、Gate、Plan Revision 和 Tool Effect 是恢复与完成判定事实。
  视觉方案通过 owner-scoped API 保存为版本化 Artifact，并在用户批准后为每个 Panel 创建独立
  图片 Task/Attempt；Native `generate_image` 在 Provider 请求前写入 prepared/submitted Tool
  Effect，成功时原子绑定 `NativeAgentImage`，明确失败创建新的 retry Attempt，unknown 状态阻止
  自动重放。每张成功图片创建独立质量 Task，由真实 VL 输出结构化 verdict、评分与问题；全部
  accepted 后才能打开 `image_quality_review` Gate。Panel 局部重跑只重置目标图片与质量 Task，
  其它 Panel、正文和 Review 保持不变。Sprint 146 新表必须通过独立 Alembic revision 添加，不能
  修改已经执行过的 Sprint 145 migration。
- Agent SDK 继续锁定 `openai-agents==0.18.3` 与 `openai==2.45.0`。旧 `AgentModelRouter` 使用
  `AGENT_MODEL`，在火苗 `TEXT_FALLBACK_*` 与 LIO `LIO_*` Responses 路径间执行既有有界重试和 fallback；
  Native Agent 则使用 Run 创建时的独立 `NATIVE_AGENT_HUOMIAO_MODEL` 与
  `huomiao_responses / huomiao / responses` 快照，不复用该 fallback。两条路径底层 client / SDK retry 均关闭。
  旧 Router 只对连接、超时、429 与语义明确的临时 5xx（包括 Provider 以 HTTP 408/5xx 包装的明确 stream
  interrupted / disconnected 错误）在火苗重试一次，仍失败时切换一次 LIO；其它 `invalid_request`、
  401/403、schema、内容策略、`model_not_found`、无渠道或能力错误明确失败。每次模型输入从应用数据库完整
  重放，不使用 Provider `previous_response_id` 或 remote conversation。
- 认证：第一版需要邮箱/密码注册登录、找回密码和 `user/admin` 两级角色，不做组织或团队隔离。
- 积分：使用关系型数据库保存 `user_credit_accounts`、`credit_transactions`、`credit_activation_codes` 和 `credit_activation_code_redemptions`。数据库是积分余额和流水的事实来源；不得只在前端或进程内维护余额。图片生成积分占用、成功扣费和失败释放必须通过数据库原子变更更新账户余额，避免同一用户多个图片 job 并发时丢失占用积分。
- 后台工作流：图片生成是异步流程，第一版采用轻量工作流：进程内队列 + 数据库持久化任务状态。
- 图片生成并发：任务队列由进程内 worker 池领取任务前置步骤，默认 `TASK_WORKER_CONCURRENCY=3`；真正调用图片 Provider 的单位是 `generated_images` 图片 job，由全局图片 worker 池调度。图片 job 使用 `job_kind` 区分 `panel_image` 和 `character_reference`，panel 图绑定 `panel_id`，人物参考图绑定 `character_appearance_id`。全站图片 job 并发通过 `IMAGE_JOB_CONCURRENCY` 配置，默认 6；单个普通用户同时运行的图片 job 通过 `IMAGE_JOB_USER_CONCURRENCY` 配置，默认 2。大任务会把人物参考图和每个 panel 都排成独立图片 job 逐步推进，不能独占全站图片 Provider 并发。
- 图文生成任务失败告警：如果配置 `TASK_FAILURE_ALERT_WEBHOOK_URL`，当 `GenerationTask` 明确进入 `failed` 状态时，后端必须向飞书自定义机器人发送一次文本告警；同一个 failed 状态通过 `failure_alert_sent_at` 去重，避免恢复流程或重复检查刷屏。告警包含任务 ID、标题、用户 ID、输入模式、当前步骤、生图模型、风格、错误码、错误信息、失败时间和可选任务链接，不推送用户原始全文。用户手动重试任务时应清空该告警标记，重试后再次失败需要重新告警。飞书 webhook 调用失败时必须记录日志并保留未发送状态，但不能覆盖任务原始失败原因或把告警失败当作任务失败原因。
- 任务取消：用户取消图文任务后，任务下仍处于 `queued` 或 `running` 的图片 job 必须同步标记为 `cancelled`，已占用积分必须释放；图片 worker 不得继续领取已取消任务下的图片 job，Provider 返回后如果任务已取消，不得保存成功资产、不得扣费、不得把任务状态从取消态改回运行或成功。已经发到第三方 Provider 的同步 HTTP 请求不依赖本地状态强制撤销，但其返回结果必须在本地丢弃并保持取消状态。
- 任务取消接口必须保持幂等；已经处于 `cancelled` 的任务再次点击取消时，后端仍应重新执行残留图片 job 清理和积分占用释放检查，避免历史错误状态让用户无法再次停止任务。
- 图片 Provider timeout 重试：生图请求和结果图下载如果出现 timeout，会自动重试 `IMAGE_PROVIDER_TIMEOUT_RETRY_ATTEMPTS` 次，默认 3 次；任一重试成功即停止，最终仍失败时必须写入明确错误。
- 文件存储：支持本地磁盘、七牛对象存储和阿里云 OSS。`STORAGE_BACKEND=local` 时使用本地磁盘，存储根目录通过 `DOODLESTORY_STORAGE_ROOT` 配置，未配置时默认项目目录下的 `./storage`；`STORAGE_BACKEND=qiniu` 时新上传和新生成资产写入七牛对象存储，七牛配置兼容 `QINIU_*` 和现有 `QNY_*` 命名。QNY 公开访问域名优先使用 `QNY_PUBLIC_BASE_URL`，历史 `QNY_DOMAIN` 继续兼容；当 QNY 域名没有显式 `http://` 或 `https://` 时，由 `QNY_USE_HTTPS` 决定协议。`STORAGE_BACKEND=aliyun_oss` 时新上传和新生成资产写入阿里云 OSS，配置读取 `ALIYUN_OSS_ACCESS_KEY_ID`、`ALIYUN_OSS_ACCESS_KEY_SECRET`、`ALIYUN_OSS_BUCKET`、`ALIYUN_OSS_ENDPOINT` 和可选 `ALIYUN_OSS_PUBLIC_BASE_URL`；未配置自定义公开域名时，公开 URL 使用 `https://<bucket>.<endpoint-host>/<storage_key>`。对象存储资产使用固定公开原图 URL；为避免 CDN 忽略 query string 时用缩略图参数污染原图缓存，任务列表、小尺寸预览和原图展示均直接使用无 query 的对象原图 URL。本地资产由后端按需生成 WebP 缩略图。
- 使用对象存储时，新写入资产上传成功后默认删除服务器存储根目录下的本地镜像，避免 `generated_image`、`douyin_media` 和 `download_archive` 长期占用系统盘；只有显式设置 `OBJECT_STORAGE_KEEP_LOCAL_MIRROR=true` 时才保留完整本地镜像。后端处理流程需要把对象存储资产转成本地文件时，允许通过 `materialize_asset_to_local` 下载到 `_cache` 短期使用，并在任务下载打包等一次性流程结束后清理该缓存。任务批量下载生成的 zip 跟随当前 `STORAGE_BACKEND` 保存；对象存储模式下 zip 上传到对象存储，不再固定保存为本地资产。
- 多平台素材导入：同级 `douyin-import-service` 统一提供旧抖音 `/api/v1/download` 和自动识别平台的 `/api/v1/import`；`内容提取` tab 与 Native Agent 都只能由 DoodleStory 后端调用该服务，前端不得直连。Docker Compose 默认地址为 `http://douyin-import-service:8010`，本地非 Docker 开发可配置为 `http://127.0.0.1:8010`。外部服务返回的服务器绝对路径不能暴露给浏览器，所需内容必须先登记为 DoodleStory 资产。
- 内容提取模型：图文图片内容提取按原顺序逐张调用 OpenAI 兼容 `/chat/completions`，每个请求只传一个公网原图 `image_url`，不要求模型理解跨页故事。单图先使用 `TEXT_FALLBACK_BASE_URL`、`TEXT_FALLBACK_API_KEY` 和 `TEXT_FALLBACK_MODEL=gpt-5.4` 当前指向的火苗平台；配置、请求、空响应或单图固定结构校验失败时，改用 `LIO_BASE_URL`、`LIO_API_KEY` 和 `LIO_MODEL` 对同一张图最多发起 3 次请求，前两次失败后有界退避，第三次仍失败则整个内容提取失败。LIO 配置缺失属于永久错误，不重复请求。后端不依赖模型输出页码，而是给每份成功单图结果确定性添加 `第X页` 并按输入顺序合并；任意图片失败时不跳过、不返回占位或部分结果。图片素材登记为 DoodleStory 资产时必须使用抖音下载服务返回的原始文件 bytes，不做压缩、缩放或格式转换，并在对象存储上传完成后把资产公网原图 URL 按原顺序传给 VL，不再把图片转成 base64 data URL；没有公网 HTTP(S) URL 时必须明确失败。视频音频转写继续使用 SiliconFlow 多模态模型。内容提取和视频转写必须使用抖音下载服务返回的本地原始媒体路径，不应为了处理流程从对象存储公开 CDN 回拉刚下载的媒体。
- 内容提取创建使用轻量后台处理：提交后立即保存记录并返回列表，后台分阶段完成解析下载和内容提取；下载媒体登记后先提交，内容提取完成后标记成功。列表按需刷新处理状态；如果后端进程重启导致同进程后台任务中断，启动恢复会把遗留 `processing` 记录标记失败并提示重新提取。仍保留显式重新提取接口用于用户在详情中重新执行，不引入外部队列或复杂状态机。
- DY 爆款复刻复用内容提取轻量后台处理；复刻请求中的风格、图片数量和人物参考配置只作为当前同进程后台任务参数使用，内容提取成功后通过普通任务创建服务创建 `提取分镜` 任务，任务执行仍由现有进程内任务队列负责。
- 视频任务第一版复用现有图片任务轻量后台处理。视频任务自身保存独立状态，但上游 `GenerationTask` 仍是图片、panel、旁白结构和人物参考的事实来源。音频参考和后续生成音频、最终视频都必须保存为明确文件资产，不得返回 mock 路径或占位 URL。
- Paynes Creek 首片允许使用独立的确定性矢量本地样片路径验证内容与渲染：该路径只读取已审计的 12 镜
  生产草案，用 Remotion 内联 SVG / CSS 图形表达机制，不把随机生图失败候选伪装为 approved 图片，也不
  改写事实旁白。它只用于当前首片的本地 MP4 交付，不替换通用视频任务的上游图片事实来源，不新增前端
  产品入口或数据库工作流。旁白允许一次直连 SiliconFlow `FunAudioLLM/CosyVoice2-0.5B` 系统预置音色，
  不需要上传音频参考；渲染必须固定 1920×1080、30fps、H.264/AAC、yuv420p，并保存 Manifest、真实
  ffprobe、hash 和逐镜帧证据。该路径始终保存 `publication_authorized=false`，不授权上传。
- Paynes Creek 还允许使用独立的 Grok AI 五镜本地短片路径验证真实生成媒体：五个选中首帧由
  `grok-imagine-image-quality` 生成，五个短镜头由 `grok-imagine-video-1.5` I2V 生成并逐一通过
  ffprobe 与人工接触表检查；Remotion `paynes-creek-grok-ai-short-v1` 模板只读取已冻结 hash 的 MP4，
  根据一次 SiliconFlow `FunAudioLLM/CosyVoice2-0.5B` 中文旁白的真实时长有界调整播放速率并显示逐镜
  字幕。该路径固定 1920×1080、30fps、H.264/AAC、yuv420p、无 BGM、无 Provider fallback，且始终保存
  `publication_authorized=false`；它不改写原 G4 随机图片 Gate，也不自动上传。
- 同一五镜模板支持显式 `zh-CN` / `en-US` 本地化 Manifest。语言版本必须各自冻结标题、证据标签、
  逐镜旁白、页脚和独立 artifact slug；英文版复用已验收 Grok 媒体 hash 时不得新增 Grok 调用。Renderer
  按 locale 选择字体、字号和标签白名单，Runner 为英文场景之间加入语音停连所需空格；每个带独立
  artifact slug 的不可变 attempt 只能执行一次 TTS、一次 Remotion 和一次 FFmpeg 规范化，不覆盖其他
  语言或已拒绝 attempt 的成片。
- 视频任务执行采用进程内队列 + 数据库状态。上游图片任务成功后自动入队视频任务；服务启动时恢复 `waiting_for_images`、`ready_for_audio`、`audio_generating`、`audio_ready` 和 `video_generating` 等可恢复状态。视频任务按 panel 生成旁白音频，因为 `comic-video-studio` 的 `episode.shots[*].audio` 是每个 shot 的时间基准。每段生成音频必须保存为 `generated_audio` 资产；最终 MP4 必须保存为 `generated_video` 资产。`comic-video-studio` 默认通过 `COMIC_VIDEO_SERVICE_BASE_URL` 指向 `http://127.0.0.1:51103`，如配置 `COMIC_VIDEO_SERVICE_API_KEY` 则请求必须携带 `X-API-Key`。TTS 第一版使用 SiliconFlow `/uploads/audio/voice` 和 `/audio/speech`；参考音频没有已注册 voice uri 时，必须用参考音频文件和参考文本注册声音。参考文本在音频参考创建时由本地 Whisper 自动转写并保存；转写失败或缺少参考文本时，音频参考不能保存或视频任务必须明确失败。视频任务生成旁白音频时必须使用创建任务时保存的音频参考语速快照，不受后续音频参考编辑影响。
- 规范：`docs/standards/` 下保存 Python、Java、数据库、后端工作流、前端、UI 交互和通用模块规范。

## 约束

- 未经用户明确要求，不引入兜底策略、降级逻辑、兼容性回退、占位实现、Mock 结果或静默错误处理。
- 积分不足时，相关生图请求必须明确失败，不允许静默免费生成、自动透支、自动切换到免费模型或返回占位图。
- 创建任务时，不改写、不摘要、不清洗用户提交的源文本。完整故事模式必须保存用户源文本；LLM 语义切分应尽量保留原文并避免改写句意，但不要求所有 panel 拼接后逐字等于源文本。完整故事语义切分每个 panel 原文必须不超过 50 字；如果 LLM 首轮或碎片化二次合并结果存在超长 panel，后端应把超长 panel 和字数规则交给同一 LLM 链路做受限修复重试，自动数量模式允许增加 panel 数量，固定数量模式仍必须保持用户指定数量；如果 LLM 切割结果仍不合格，后端按标点确定性兜底切割，超过 20 字后在下一个标点截断，连续 50 字没有标点时按 50 字硬切。
- 故事方案模式可以生成图文分镜规划概要，但必须保留原始输入，并将规划概要保存在独立字段中。
- 故事方案模式如果规划失败，任务失败并显示明确错误，不能生成占位分镜或静默切回普通模式。
- 提取分镜模式只能结构化内容提取结果，不能把它当作故事方案重新创作；解析失败时任务失败并显示明确错误。知识方案模式只能把用户输入的知识方案拆成可独立生图的内容页，不能自动策划用户没有提供的知识主题，不能补写新知识点、总结压缩成短摘要或改写成故事。
- Panel prompt 生成必须在 LLM system prompt 层遵守所选风格提示词；最终 panel 生图 prompt 必须由最终编译 LLM 基于任务保存的风格、全局角色表、参考图顺序和页式分镜中间态生成，不能只做代码字符串拼接。最终生图 prompt 的结构不应因为风格参考方式分裂成两套流程：只要 panel 携带人物参考图，就必须在最终 prompt 前部写入 `人物参考（第一优先级，必须严格执行）` 和 `人物外观参考图N（角色名）` 映射；`prompt` / `image` 风格参考方式只决定风格参考图是否随 Provider 请求传入，不影响人物参考图是否传入和是否写入映射。`image` 模式下如传入风格参考图，最终 prompt 只能把它写成 `风格参考（仅控制画风，不代表人物身份）`，用于画风、线条、色彩、背景质感和整体视觉气质，不能和人物身份或外观混用。`prompt` 和 `image` 风格参考模式下，LLM 编译结果外层都必须显式拼接任务保存的风格提示词快照，让图片模型直接执行风格规则；该拼接只增强风格一致性，不允许覆盖人物参考外观锁定。人物参考图 prompt 仍必须显式拼接任务保存的风格提示词快照。
- 风格参考图在 `prompt` 模式下只用于风格库展示、风格样张和用户理解视觉方向，不作为风格测试、任务 panel 生图或单 panel 修改的模型输入；在 `image` 模式下作为风格测试、任务 panel 生图和单 panel 修改的模型参考输入。风格参考图不参与人物参考图生成。
- 完整故事模式下，Panel 原文需要作为图片内可读文字进入最终生图 prompt，不能删改文案内容，也不能添加“旁白”“字幕”“标题”等标签；直接引语可以通过 `visual_prompt` 绑定到人物说话动作并画成对白气泡，但不能在旁白框重复。故事方案和提取分镜模式下，旁白、来自 `visual_prompt` 的人物对白和内心 OS 需要在 prompt 中区分呈现方式。最终 prompt 编译时可以读取 `旁白`、`对话`、`内心OS` 等中间态字段，但字段名只是结构化指令，不得画进图片。
- 风格测试和任务必须使用所选风格绑定的模型，除非用户明确修改该风格绑定。
- 所有模型同价，风格测试、人物参考图、正式 panel 生图、任务重试和单 panel 修改均按成功产出的图片数扣积分，每张成功图扣 `1` 积分。
- 图片 Provider 排障时可以通过 `IMAGE_PROVIDER_DEBUG_LOG_RAW_IO` 临时开启请求/响应正文日志；日志不得输出 Authorization、完整结果图 base64 或敏感图片 URL，只保留 prompt、请求结构和已脱敏的 URL host 用于确认。
- 任务列表接口只能返回摘要字段、图片数量和少量缩略图预览；不能默认返回完整 panels、generated_images、prompts 或原图内容。任务详情必须通过独立详情接口按需加载。
- 七牛对象存储配置缺失、上传失败、公开 CDN URL 访问失败或资产下载失败时必须明确报错，不能静默切回本地存储。
- 抖音下载器仓库路径缺失、Cookie 缺失、Cookie 文件无效、下载器执行失败或执行后没有媒体文件时必须明确报错，不能静默切换到无 Cookie、浏览器兜底或占位结果。
- 抖音下载服务不可达、下载失败、下载后没有媒体文件、视频音频分离失败或 SiliconFlow 文案提取失败时必须明确报错，不能静默跳过媒体、自动改写文案或返回占位结果。
- 视频任务必须复用真实上游生图任务产物。上游图片任务未成功、缺少当前图片、缺少可用旁白文本、参考音频不可访问、TTS 失败、图文视频服务失败或最终视频下载失败时，视频任务必须明确失败或停留在对应等待状态，不能静默跳过、自动换音色、自动换视频 provider 或返回占位结果。
- 内容提取必须保存用户粘贴的原始输入和后端解析出的 URL；图文内容提取必须按原顺序逐张读取同一作品的图片并保留每张图中可见的标题、旁白、对话、内心 OS 和其他文字原文，同时客观记录分格、构图和文字布局，不做跨页故事理解、总结、润色、扩写或故事化改写。
- 普通用户只能访问自己创建的任务；Admin 可以访问所有任务。
- 视频任务和音频管理只允许 Admin 访问；普通用户不能通过导航、直接 URL、API 或文件资产接口查看、创建、编辑、试听、重试或下载视频任务、音频参考、旁白音频和最终视频。
- 普通用户只能访问自己的角色资产；创建任务绑定角色时，后端必须校验角色归属当前用户，不能只依赖前端隐藏。
- 暂不做组织、团队、项目空间或租户级隔离。
- 图片模型不作为独立模块管理；风格只保存生图模型名，provider、API key 和默认参数由 env 维护，不暴露给普通用户。
- 支持用户对单个 panel 提交画面修改方向；系统调用一次 LLM 基于当前 `image_prompt` 生成新版本提示词，再重新生成该 panel 图片。
- 单个 panel 可以保留多次图片生成版本；当前展示和下载只使用标记为当前版本的成功图片。
- 任务重试时，上一轮仍处于 `queued` 或 `running` 的旧图片版本必须明确标记为失败并从当前展示中移除；任务已经完成后，详情页不能因为旧的非当前运行中版本而显示生成中。
- 用户显式点击任务重试时不限制重试次数；`attempts` 只用于排查和标记重试来源，不作为阻止用户操作的上限。
- 任务队列支持最多按 `TASK_WORKER_CONCURRENCY` 并发执行多个生成任务前置步骤，默认 3；同一进程内同一个任务 ID 不允许并发执行两次。
- 任务 `generate_character_references` 阶段只负责为缺少成功参考图的人物外观创建 `generated_images.job_kind=character_reference` 图片 job；人物参考图成功后写回 `task_character_appearances.reference_image_id`，失败则让任务明确失败。任务 `generate_images` 阶段只负责为缺少成功图的 panel 创建 `generated_images.job_kind=panel_image` 图片 job；正式 panel 图片生成、任务内人物参考图生成和单 panel 修改都由统一图片 job worker 执行。图片 job worker 使用 `IMAGE_JOB_CONCURRENCY` 控制全站并发，使用 `IMAGE_JOB_USER_CONCURRENCY` 控制单用户并发，并通过 `IMAGE_JOB_LEASE_SECONDS` 标记运行租约，服务重启后会恢复中断的 running 图片 job。任务详情接口中的 `generated_images` 只返回 panel 图片版本；人物参考图通过 `character_references` 字段展示。
- 取消中的图文任务不得继续恢复、领取或执行任务内图片 job；取消发生在 Provider 调用之后时，返回结果只用于释放本地占用和结束 job，不得转成成功资产或积分扣费。
- 任务生图请求和结果图下载遇到 timeout 时自动重试 3 次；非 timeout 的配置错误和校验错误不得因为该规则被隐藏。所选生图 Provider 的响应错误在既有重试耗尽后必须明确失败，不得在 DoodleStory 后端静默切换到 XG、QY 或其它 provider。
- 当图片 Provider 明确返回 Google policy blocked 类错误，例如 `Unable to show the generated image`、`Generative AI Prohibited Use policy` 或 `filtered out`，说明当前 prompt 被上游策略拦截；此时先调用 LLM 改写最终生图提示词中的敏感动作意图表达，在不改变画面效果、主体、构图、风格、图片内文字和参考图关系的前提下，把疼痛、伤害、惩罚、触碰、危险意图等表达改为更中性客观的视觉状态，然后使用原图片模型和原参考图重新提交一次。该逻辑只适用于明确 policy blocked 错误，不适用于普通 Provider 响应错误。
- 开启人物参考的任务如果没有识别到可用于参考图的主要人物，任务应失败并显示明确错误，不能静默降级为普通生图。
- 单 panel 修改在人物参考任务中必须继续携带该 panel 已绑定的人物参考图。
- SiliconFlow 使用免费额度模型时，配置只能选择 `docs/integrations/llm-agent-endpoints.md` 第 2.1.1 节的白名单；未接入的模型类别不能仅通过改环境变量假定可用，也不得自动切换为清单内的其它模型。当前是配置与运营约束，尚未在代码中增加模型名强制校验；如需强制校验，必须单独评估已有图片风格和媒体配置。
- Agent Runtime 已由 Sprint 105 的真实双平台 SDK Tool Loop 锁定为 `openai-agents==0.18.3`、`openai==2.45.0` 和 Responses API；后续 Sprint 不得改变应用侧持久化、完整输入重放或 Router 错误分类契约。

## 非目标

- 构建通用 prompt 市场。
- 构建独立图片模型管理模块。
- 在具体 provider 选定前构建泛化图片模型抽象层。
- 在项目规模证明需要之前引入生产级工作流基础设施。

## 验收方向

主要验收流程是：定义 sprint，在 sprint 范围内实现，运行验证，记录 QA，并为下一次 Codex 会话留下明确进度。

## 未决问题

- 最终 Evaluation 第一轮真实 baseline 后，质量、延迟、成本和 fallback 告警阈值应设为多少。
- 风格除了名称、描述、参考图片、prompt、状态和生图模型名外，还需要哪些元数据？
- 批量下载支持哪些图片格式和命名规则？
