# 进度记录

## Sprint 199（进行中）

- 已审计 `ele-yufo/grokcli` 最新主线并把依赖从 0.1.0 精确升级到 commit
  `2dcd4d4b2dc6c35f013a6b2a826721e4b98bfe13`（0.2.0）；继续复用持久化浏览器 OAuth，项目不直接
  实现 xAI token 或视频 HTTP 请求。
- 新增独立 Grok 视频适配器，固定使用 `grok-imagine-video-1.5`，支持 1–15 秒 T2V 和当前会话单图
  I2V。命令使用参数数组与独立输出目录；每次 Tool Call 只执行一个 `grokcli video`，失败、超时或
  网络结果未知时不重试、不切模型或 Provider。
- 输出必须是隔离目录中的唯一文件，并由本地 ffprobe 验证 H.264、MP4、宽高、时长、帧率与帧数；
  CLI 的认证、额度、网络、超时与内容审核退出码保留为明确错误，日志中的 token 字段会脱敏。
- grokcli 0.2.0 上游 352 项测试在 Windows 通过 346 项；POSIX 权限位、回调端口复用与 `fcntl`
  文件锁共 6 项不通过。OAuth 实测成功；针对 Windows `fcntl` 不可用的问题，DoodleStory 图片与
  视频适配器共用单进程串行锁，避免并发刷新凭据。项目单实例约束继续是该锁成立的运行前提。
- Native Agent 新增 `generate_video_clip`，已接入 Skill Tool Catalog、Capability API 和前端名称；
  复用 `generated_video` 与 `NativeAgentVideo`，保存 Provider、模型、T2V/I2V 模式、Prompt、源图片、
  请求参数和 grokcli 版本。成功 Tool Call 重放只返回原视频，不再次调用 Grok。
- 65 项 Grok/Native 聚焦回归与 432 项后端全量测试已通过，另有前端 14 项、Remotion 8 项、
  前端 build、空库迁移和控制器校验通过；覆盖参数边界、目录逃逸、非 MP4、退出码、禁止自动重试、
  当前会话图片权限、资产保存和幂等重放。本机 OAuth 已成功；唯一一次 Paynes Creek 8 秒 I2V 在提交阶段
  返回 xAI 403 额度/订阅错误，未生成 MP4，未自动重试或切换 Provider。失败记录见
  `docs/testing/paynes-creek-grok-video-smoke-2026-08-13.json`，当前外部阻断为
  `xai_video_credits_or_subscription`。
- 合同：`docs/contracts/sprint-199-grokcli-native-agent-video-clip-tool.md`。
  实现验收记录：`docs/qa/sprint-199-grokcli-native-agent-video-clip-tool-report.md`。

## Sprint 144（已完成）

- 已根据 2026-08-01 的最新决定收紧为后端优先：保留已调试的 Agent 页面、Skill、账号与 `@`
  资源交互；Sprint 144 只替换任务、审批、恢复和终态的后端事实，不重做页面。
- 已新增后端 Durable Workflow、Task、Attempt、Checkpoint、Artifact、Gate 与 Tool Effect 表；它们
  通过 `native_run_id` 关联现有 `NativeAgentRun`，不删除 `native_agent_*` 表、不替换
  `/agent-loop` 请求/响应形状。
- 现有 Run 创建会初始化唯一 Durable Workflow；原页面产生的候选选题审批会镜像为
  `topic_selection` Gate。用户批准“使用第一个选题就可以”后，后端写回同一 Run 的持久化上下文
  并准备正文 Attempt，而不是把 Run 标记成功或创建新的“继续”Run。
- 已将现有 Writer/Reviewer 产物同步到 Durable Task；当前 Durable Task 会限制旧 Loop 只暴露
  当前阶段的 Writer 或 Reviewer Tool，候选选题、正文和 Review 依次使用现有页面可见的审批
  容器。旧 Loop 在 Durable required Task 未完成或仍有 Gate 时不能将 Run 标记成功。
- 迁移副本验证新增 7 张 Durable 后端表后仍保留 34 用户、21 风格、18 频道和 82 条传统任务；
  原 Agent 页面浏览器验证确认 Simple Agent Loop、Skill 管理、返回工作台、`@` Skill/Style
  菜单和资源标签保持不变。定向 42 项回归及 `./scripts/check.sh`（343 项后端测试、14 项前端
  测试、构建和 Remotion）通过。
- 最终实现确认：Sprint 144 从规划基线只修改后端、Alembic、测试和文档；没有修改
  `frontend/src`。当前页面继续由原 `NativeAgentView` 和 `/agent-loop` 支撑，后续 Sprint 的
  前端控制重构不在本 Sprint 提前实施。
- 首条链路固定为：初始计划 → 选题研究/确认 → 正文撰写/确认 → Review/确认 → 完成。非终态
  Gate 的批准必须在同一 Run 内推进后继 Task；“继续/重试”不再依赖精确自然语言。
- Runtime 将采用 Run → 动态 Task 图 → Attempt → append-only Checkpoint → Artifact/Gate 的
  权威模型。初始计划仅固定当前阶段与近端 Gate；上游产物、用户决定与 Review 结果可以受控调整
  后续计划，已终态事实不可覆盖。
- 本 Sprint 不实施图片并行、图片质量 Gate、局部图片重跑或 Probe；这些留给后续 Sprint 接入
  同一 Runtime。仍不引入外部工作流引擎。
- 合同：`docs/contracts/sprint-144-native-agent-durable-task-control-plane.md`；实现与验收记录见
  `docs/qa/sprint-144-durable-backend-runtime-report.md`。

## Sprint 145（已完成）

- 在 Sprint 144 的 Task / Attempt / Checkpoint 基础上，增加固定 Skill Version 约束下的动态计划
  修订：上游 Artifact、用户决定和 Review 可追加、替换或取消未执行的后续 Task，但不能覆盖
  已终态事实。
- 本 Sprint 不改已调试的 `/agent` 页面；先完成后端计划修订、局部失效/重试和恢复投影，正式
  页面控制留到后续 Sprint。
- 新增 append-only `agent_durable_plan_revisions`：初始 Task 图、Task 产物完成、Gate 打开、
  Gate 批准/修改、lease 过期恢复和补充研究分支都会记录不可变计划版本，关联来源 Checkpoint。
- 正文 Gate 修改只重置正文及其下游 Review/最终 Gate；已批准选题保持成功且不重跑。最终 Review
  修改意见包含“补充研究”时，后端只追加 allowlist 内的 `supplement_research` Task，研究完成后
  才准备正文修订 Attempt，禁止重复追加或任意模型动态建图。
- 新增 owner-scoped `GET /agent-loop/runs/{run_id}/plan-revisions`，为后续页面控制提供只读计划
  事实来源；当前页面没有调用它，因此 Simple Agent Loop、Skill 管理、账号和 `@` 资源交互保持
  原样。
- 迁移副本升级至 `q8r9s0t1u2v3` 后保留 34 用户、21 Style、18 频道与 82 条传统任务；原页面
  浏览器回归确认 Simple Agent Loop、Skill 管理入口和 Style `@` 菜单未变化。`./scripts/check.sh`
  通过 346 项后端测试、14 项前端测试、构建和 Remotion。
- 真实文本链路验证：隔离 Run `802937baf304454199b5f6c9df0e13cb` 只引用文案 Skill，真实生成
  候选选题后进入 `topic_selection` Gate；确认后在同一 Run 创建 `write_draft` initial Attempt，
  Checkpoint 与 Plan Revision 连续推进，模型输入只包含已批准选题和正文阶段约束。验证期间
  图片/语音/字幕/视频调用均为 0；正文返回前主动取消。修复现有 SSE schema 对
  `topic_candidates` 的兼容和选题确认 adapter 的缺失导入后复验通过。
- 合同：`docs/contracts/sprint-145-agent-dynamic-task-planning-and-chat-projection.md`。

## Sprint 146（已完成）

- 将图片方案、并行 Panel 图片 Task、逐图质量检查、图片质量 Gate 和局部重跑接入同一 Runtime；
  用户在聊天中处理方案与质量，系统只重跑不合格 Panel。
- 传统 GenerationTask、积分、图片版本和资产继续是领域事实，Agent 通过明确 adapter 调用，
  并由 Tool Effect 防止未知结果和重复扣费。
- 合同：`docs/contracts/sprint-146-agent-media-quality-gates-and-partial-rerun.md`。
- 新增 Durable 媒体绑定、图片质量结论和质量汇总 Gate 后端事实。传统 `GenerationTask` /
  `TaskPanel` / `GeneratedImage` 继续是传统图片任务的唯一事实；Native Agent 图片继续使用
  `NativeAgentImage`，Durable 仅记录关联 ID、Task/Attempt、Tool Effect 和质量结论，不复制资产。
- 视觉方案注册后创建 `visual_plan_review` Gate；图片质量结论未全部完成时不能打开
  `image_quality_review` Gate。对指定 Panel 请求重跑时，仅该 Panel 的图片/质量 Durable Task
  进入 rerun，其他 Panel 保持 accepted。
- 对 Native Agent 图片，绑定记录使用原 `NativeAgentImage.id` 和 Tool Step 幂等键，避免侵入
  原图片 Tool 的资产事实；Provider 请求前写 prepared/submitted Effect，成功后在同一事务绑定
  图片、Attempt 和质量 Task，明确失败产生新的 retry Attempt，unknown 阻止自动重放。逐图质量
  Task 复用真实 VL 检查器，保存 verdict、评分、问题、Provider/model 和延迟；VL 失败明确记录为
  blocked，不会伪装通过。
- 新增独立迁移 `r9s0t1u2v3w4`，已验证旧库停在 Sprint 145 revision 后升级、downgrade、再次
  upgrade，避免修改已执行 migration 导致现有数据库漏表。owner-scoped API 覆盖视觉方案、媒体
  Gate、媒体状态、质量决定和 Panel 重跑；当前页面布局不变。
- `./scripts/check.sh` 通过 354 项后端测试、空 SQLite 全量迁移、14 项前端测试、前端生产构建、
  Remotion 类型检查与 5 项测试；聚焦 Durable/Native/恢复回归 54 项通过，`git diff --check`
  通过。
  Playwright 使用本地 QA 用户验证 `/agent → /agent/skills → /agent`，新对话、Skill 管理、返回传统
  工作台和 `@` 资源入口均可用；启动时未登录产生的两条预期 401 是唯一 Console error。未调用
  真实图片 Provider，未产生模型或图片费用；VL 执行器通过注入式真实 schema 回归验证。

## Sprint 147（已完成）

- 已根据真实全媒体测试暴露的问题将 Draft 收紧并激活：本 Sprint 聚焦六类统一控制命令、取消、
  重启恢复、unknown Effect 人工处理、SSE/刷新收敛，以及 Review Gate、纯媒体终态、字幕重试复用
  和图片检查顺序修复。Follow-up Run 与受控 Probe 移交下一 Sprint，避免在控制闭环中混入未完成
  分支语义。
- 合同：`docs/contracts/sprint-147-agent-durable-control-and-recovery-acceptance.md`。
- 已新增 `agent_durable_commands` 与 owner-scoped `control-state / commands` API；六类命令统一校验
  `allowed_actions`、`state_version`、目标归属和 unknown Effect。相同幂等键重放只返回首次结果，
  不会再次入队或取消 Worker；旧文案审批、媒体 Gate 与取消入口已委托统一命令服务。
- 非文案 Skill 现在只初始化空 Durable Workflow，不创建 ARTICLE_TASKS；Run 正常完成时同步收敛
  Workflow 终态。`article_review` 明确映射 `editorial_review_gate`，避免 Review 审批退回正文 Gate。
- 原生 Runtime 已开放并持久化 `inspect_image`；Skill 暴露该 Tool 时，视频渲染强制要求对应图片
  `verdict=accept`。字幕对同一音频最多自动失败两次，字幕失败后的相同文本/语速 TTS 调用复用
  已成功音频，不再重复请求 Provider。
- 前端按后端 `allowed_actions + state_version` 展示重试、恢复、unknown 处理与取消操作；运行中的
  Tool 展示名称和真实已等待时间。SSE 检测 cursor 缺口时发出 `run.resync_required`，页面重新拉取
  Conversation Projection 与控制状态，不以 heartbeat 伪造业务进度。
- 最终检查已通过 361 项后端测试、空 SQLite 全量迁移、14 项前端测试、生产构建、Remotion
  类型检查和 5 项测试；新增故障回归覆盖命令幂等/过期版本、取消、unknown Effect、纯媒体空
  Workflow、图片检查顺序、TTS 复用、字幕失败上限与 SSE cursor 缺口。
- 隔离 SQLite + 真实 FastAPI/Vite 浏览器验收确认 unknown 处理、取消、长 Tool 等待、失败后的
  retry/resume、终态刷新和 0 console error/warning。验收发现并修复 unknown 已处理但 Native Step
  仍显示 running 的收敛问题。操作手册见 `docs/deployment/agent-durable-runtime-operations.md`，
  QA 报告见 `docs/qa/sprint-147-durable-control-and-recovery-report.md`。

## Sprint 148（已完成）

- 已激活显式 Follow-up Run 合同：只允许从同一 owner/Conversation 的成功终态 Run 续接固定
  Checkpoint，创建隔离的新 Run、Workflow、Task、Attempt 和 Effect；不靠“继续”文本猜测来源。
- Follow-up 固定继承父 Run 的 Skill Version、Style、账号与结构化资源，并把父最终输出和已确认
  Artifact 作为带 ID/hash 的只读 snapshot 注入；父 Run 事实不可修改。
- 本 Sprint 不实现 Probe。只读预算、Probe Artifact 和显式采纳留给 Sprint 149，Deferred
  Evaluation 继续保持延后。
- 已完成 Follow-up 后端主链：新增父 Run/Checkpoint 关系、请求幂等键与 hash、64KB/50 产物的
  完整 snapshot 上限和数据库形状约束；只有同 owner、同会话的成功 Run 且存在当前 Checkpoint
  时才能创建。子 Run 固定继承 Skill/Style/账号与发布对象引用，但清除发布确认，并初始化独立的
  文案或非文案 Durable Workflow。
- 普通 Agent 和文案多角色 instructions 均已注入 `<follow_up_context>`，明确父事实只读、本轮输入
  是唯一新目标、未重新完成父 Tool 且不得沿用发布确认。Run Projection/SSE 已返回父 Run 与来源
  Checkpoint ID。
- 页面已加入“基于此结果继续”、固定资源提示、取消续接、父子定位与稳定幂等键；提交失败保留
  输入和父 Run 选择，Follow-up 模式禁止改选资源。专项后端 6 项与 `./scripts/check.sh` 全部通过：
  367 项后端测试、空 SQLite 全量迁移、14 项前端测试、生产构建、Remotion 类型检查与 5 项测试；
  开发库已升级到 `t1u2v3w4x5y6`。
- 隔离 SQLite + 真实 FastAPI/Vite 浏览器验收确认成功/失败 Run 按钮边界、固定资源提示、取消模式
  保留输入、真实 409 后保留父选择和文本、父子标签刷新、幂等 API 重放，以及登录后刷新 0 console
  error/warning。浏览器验收发现并修复了非文案空 Workflow 被 Worker 永久跳过的问题；现在只有
  “存在 Durable Task 但没有 ready Attempt”的 Workflow 才会阻止 Native Loop。
- 合同：`docs/contracts/sprint-148-explicit-follow-up-run.md`。
- QA：`docs/qa/sprint-148-explicit-follow-up-run-report.md`。

## Sprint 149（已完成）

- 新增 `grok` 显式图片 Provider，通过已认证的 `grokcli image` 调用 Grok 订阅生图；Provider
  失败明确返回错误，不自动切换到其它图片平台。
- Native Agent 生图 Tool 支持逐次显式选择 Provider，并把实际 Provider 快照保存到图片事实；
  传统任务继续使用环境配置的默认 Provider。
- Grok Provider migration 已调整为在 Durable Runtime 与 Follow-up migration 之后执行，使用
  唯一 revision `u2v3w4x5y6z7`，不再与 Sprint 144 的 `p7q8r9s0t1u2` 冲突。
- 合同：`docs/contracts/sprint-149-grokcli-image-provider.md`。

## Sprint 150（已完成）

- 修复本地手动 Uvicorn 与 KeepAlive LaunchAgent 并存时，在端口绑定失败前反复执行 startup
  恢复的问题。新增按数据库标识生成的跨进程单实例锁，任何队列初始化和恢复动作都必须在持锁
  后执行；锁冲突时第二实例明确退出，startup 初始化失败与正常 shutdown 均释放锁。
- 事故 Run `d41010e722604b758d0d909ad10a388e` 已保留全部 Trace 和事件并收敛为 `failed`；真实
  并存测试中第二实例退出码为 3，事件数在测试前后保持 245，没有新增恢复或 Provider 调用。
- 发现未提交 Grok 图片 Provider migration 复用了 Sprint 144 revision `p7q8r9s0t1u2`。开发库
  已从事故前完整备份恢复，按正式 Durable migration 链升级到 `t1u2v3w4x5y6`，11 张 Durable
  表全部存在且 SQLite `integrity_check=ok`；冲突 migration 未进入运行库，后续整合时必须改用
  新 revision。
- 本地前后端改由各自唯一的 launchd job 管理，后端 job 运行已修复的 Durable Runtime 分支并
  指向主工作区数据库与存储。健康检查通过，`8000` 与 `3000` 各一个监听进程，两个 job 均只
  启动 1 次且保持 running。
- `scripts/restart-dev.sh` 在手动启动前会明确 bootout 已加载的 DoodleStory 前后端 launchd job，
  避免 KeepAlive 在脚本停止旧监听端口后立即抢占端口；因此 launchd 与手动脚本不会同时成为
  服务 owner。
- `./scripts/check.sh` 通过 372 项后端测试、空 SQLite 全量迁移、14 项前端测试、前端生产构建、
  Remotion 类型检查与 5 项测试；新增 5 项单实例锁测试。目标 URL 可加载且控制台 0 error / 0
  warning，但浏览器无登录态，未在 UI 内展开受保护的 Trace 详情；终态与事件稳定性由数据库和
  后端日志验收。
- 合同：`docs/contracts/sprint-150-single-instance-startup-recovery.md`。
- QA：`docs/qa/sprint-150-single-instance-startup-recovery-report.md`。

## Sprint 143（已完成）

- 修复 `@创作账号` 只推导绑定 Style、没有进入 Agent Context 的断链。Run 现在按准确账号 ID
  持久化账号定位、受众、阶段目标、AI 定义、运营备注、频道指标、对标账号和近期视频的有界
  JSON 快照，账号后续修改不会改变旧 Run。
- 普通 Native Agent 以及多 Agent 文案 Director、Writer、Reviewer 都会直接收到同一
  `<creation_account_context>`；不再依赖 Skill 是否开放 `get_account_creation_context`
  或模型是否主动调用 Tool。
- 开发库真实“中国文明长纪录片”账号已解析出完整策略和 1 个对标账号，instructions 实测包含
  账号定位与目标受众。真实浏览器完成 `@创作账号` 选择和绑定 Style 标签验收；未调用收费
  模型、未创建新 Run。
- 新迁移已应用到开发库和空库链路。定向 44 项后端测试及 `./scripts/check.sh` 全部通过，
  完整检查覆盖 339 项后端测试、14 项前端测试、前端生产构建和 Remotion 检查。合同见
  `docs/contracts/sprint-143-native-agent-account-context.md`。

## Sprint 142（已完成）

- Skill 软归档已统一呈现为 Disable / Enable。管理员可在系统 Skill 列表和详情中改变状态，
  普通用户不能改变系统 Skill 状态；个人 Skill 继续使用同一套可恢复状态操作。
- Disabled Skill 保留正文、不可变版本、当前版本引用和历史 Run，但从 Native Agent 与旧
  Agent 的 `@Skill` 查询及新 Run 创建中排除；系统 Skill 的启动种子不会在重启时覆盖
  Disabled 状态。
- 真实浏览器逐项 Disable 当前三个系统 Skill，服务重启后仍全部显示 Disabled 和 Enable
  操作，Native Agent 的 `@` 菜单不再显示 Skill 分组，控制台 0 error / 0 warning。
- 定向后端 44 项测试、前端 14 项测试和生产构建通过；统一检查结果见当前基线。合同见
  `docs/contracts/sprint-142-system-skill-disable.md`。

## Sprint 141（已完成）

- Native Agent 输入区已从 Skill、创作账号、Style、YouTube 频道和审核视频的常驻下拉框，
  改为统一的 `@` 资源引用交互。输入 `@` 或点击资源按钮即可搜索，支持键盘上下选择、Enter
  确认、Escape 关闭和可移除标签；每一轮对话都能重新组合当前上下文。
- 创作账号与直接 Style 保持互斥，账号标签显示绑定 Style，提交仍只发送账号 ID 并由后端唯一
  推导风格；发布频道和审核视频也作为资源加入，频道存在时才展示可见性和计划时间，移除频道
  会同步清理发布上下文。
- 新增纯函数和 6 项资源规则测试。真实浏览器完成 `@` 打开、键盘选择、账号/Style 双向替换、
  发布参数显示与移除，控制台 0 error / 0 warning；未运行收费模型或触发真实发布。
- `./scripts/check.sh` 通过 338 项后端测试、空库迁移、14 项前端测试、前端生产构建、Remotion
  TypeScript 与 5 项模板测试。合同见
  `docs/contracts/sprint-141-native-agent-resource-mentions.md`。

## Sprint 138（已完成）

- 已把官方 YouTube Data API v3 公开频道研究接入同级 `douyin-import-service`，新增
  `/api/v1/youtube/channel-insights`；支持频道 URL、Handle 和 Channel ID，返回频道资料、
  最近视频标题、完整描述、标签、发布时间、时长、基础统计和可配置排序的顶级评论。
- Import 服务会真实下载频道头像与每条视频最高可用分辨率封面；任一官方 API 或图片下载
  失败时整次请求明确失败。DoodleStory 新增“读取 YouTube 频道”
  `inspect_youtube_channel` Tool，模型可在受控边界内选择视频数、评论数和排序，并把头像与
  封面作为视觉 Tool Output 一起分析，不暴露服务端文件路径。
- Tool 严格服从固定 Skill Version 白名单；同时修正已有 `publish_youtube_video` 只凭
  发布上下文即可暴露的旁路，现在必须同时满足 Skill 白名单和发布确认上下文。
- 真实频道 `@HistoryEagle-u9d` smoke 已取得频道信息、最新视频完整包装信息和 2 条评论，
  下载 `800×800` 头像与 `1280×720` 封面；完整 Agent Tool 输出为 1 份文字和 2 份视觉结果。
- Import 服务 17 项测试通过；DoodleStory `./scripts/check.sh` 通过 328 项后端测试、空库
  迁移、8 项前端测试、前端生产构建、Remotion 类型检查与 5 项测试。合同见
  `docs/contracts/sprint-138-youtube-channel-research-tool.md`。

## 当前基线

- 分支：`codex/durable-runtime-backend-144`
- Harness 状态：`active`
- 产品：`DoodleStory`，文本转图片故事生成项目
- 最近验证状态：Sprint 150 已完成；单实例 startup recovery lock、事故 Run 收敛和本地唯一
  launchd 运行入口已验证。`./scripts/check.sh` 已通过 372 项后端测试、空库迁移、14 项前端测试、
  前端生产构建和 Remotion 检查；本 Sprint 未调用收费 Provider，Deferred Evaluation 未实施。
- 最新规划状态：用户于 2026-07-26 决定把 Evaluation 推迟到全部计划功能完成后的最终阶段，并把 Skill 管理与真实 Runtime 接入合并为 Sprint 117。新合同覆盖用户 Skill CRUD、草稿和不可变发布版本、系统 Skill clone、受控 Tool 白名单、AI 编写辅助、独立管理页面、对话 `@Skill`、Run 固定 Skill Version、通用内容创作 Base Instructions，以及移除漫画专用 Runner/资源路由硬编码后的统一 Agents SDK Tool Loop；第一版不做 Workflow DSL、多 Skill、脚本/MCP、Memory 或新媒体 Tool。
- Sprint 117 前端视觉基准已补充：基于当前 Agent Studio 生成并归档 Skill 列表、Skill 编辑器、版本历史、对话 `@Skill` 与执行状态四张高保真效果图，同时新增页面结构、AI 建议、发布/激活/归档、导航恢复、必备状态、响应式和交互验收说明；实施窗口必须先阅读 `docs/design/sprint-117-skill-ui/README.md`，不得把正式页面做成通用后台模板、JSON/Workflow 编辑器或只有简单文本框的草率实现。
- 当前合同状态：Sprint 149、150 Complete；Sprint 144、145、146、147、148 Complete；Sprint 143、Sprint 142、Sprint 141 Complete；
  Sprint 135 真实外部发布 smoke 待用户授权；正式 Evaluation 保持 Deferred。

## 当前 Sprint 合同

- Complete：`docs/contracts/sprint-150-single-instance-startup-recovery.md`
- Complete：`docs/contracts/sprint-149-grokcli-image-provider.md`
- Complete：`docs/contracts/sprint-148-explicit-follow-up-run.md`
- Complete：`docs/contracts/sprint-144-native-agent-durable-task-control-plane.md`
- Complete：`docs/contracts/sprint-145-agent-dynamic-task-planning-and-chat-projection.md`
- Complete：`docs/contracts/sprint-146-agent-media-quality-gates-and-partial-rerun.md`
- Complete：`docs/contracts/sprint-147-agent-durable-control-and-recovery-acceptance.md`
- Complete：`docs/contracts/sprint-143-native-agent-account-context.md`
- Complete：`docs/contracts/sprint-142-system-skill-disable.md`
- Complete：`docs/contracts/sprint-141-native-agent-resource-mentions.md`
- Complete：`docs/contracts/sprint-140-youtube-account-style-binding.md`
- Complete：`docs/contracts/sprint-138-youtube-channel-research-tool.md`
- Complete：`docs/contracts/sprint-134-youtube-channel-account-and-video-registry.md`
- Complete：`docs/contracts/sprint-135-youtube-publishing-and-agent-channel-mention.md`
- Complete：`docs/contracts/sprint-136-youtube-list-pagination-and-readability.md`
- Complete：`docs/contracts/sprint-133-native-subtitle-source-alignment.md`
- Complete：`docs/contracts/sprint-132-native-agent-latest-run-retry.md`
- Complete：`docs/contracts/sprint-131-api-utc-shanghai-display.md`
- Complete：`docs/contracts/sprint-130-native-agent-run-cancellation.md`
- Complete：`docs/contracts/sprint-129-native-speech-ffprobe-executable.md`
- Complete：`docs/contracts/sprint-127-speech-speed-whisper-subtitle-tools.md`
- Complete：`docs/contracts/sprint-126-remotion-source-image-ratio-real-task-smoke.md`
- Complete：`docs/contracts/sprint-125-native-agent-remotion-video-tool.md`
- Complete：`docs/contracts/sprint-124-native-agent-volcengine-speech-tool.md`
- Complete：`docs/contracts/sprint-123-native-agent-durable-runtime.md`
- Complete：`docs/contracts/sprint-122-native-loop-streaming-and-trace-semantics.md`
- Complete：`docs/contracts/sprint-121-skill-detail-and-edit.md`
- Complete：`docs/contracts/sprint-120-native-loop-mlflow-and-agent-ui.md`
- Complete：`docs/contracts/sprint-119-minimal-native-agent-loop.md`
- Complete：`docs/contracts/sprint-111-agent-independent-shell-readonly-inspector.md`
- Complete：`docs/contracts/sprint-112-agent-mlflow-observability-baseline.md`
- Complete：`docs/contracts/sprint-113-agent-skill-tool-runtime-foundation.md`
- Complete：`docs/contracts/sprint-114-idea-to-comic-skill-hitl-event-stream.md`
- Complete：`docs/contracts/sprint-115-agent-structured-resource-context.md`
- Complete：`docs/contracts/sprint-116-agent-panel-version-vl-loop.md`
- Complete：`docs/contracts/sprint-117-pluggable-skill-management-agent-loop.md`
- Complete：`docs/contracts/sprint-118-skill-management-navigation-discoverability.md`
- Deferred（最终阶段，暂不编号）：`docs/contracts/deferred-agent-evaluation-internal-release-gate.md`
- Complete：`docs/contracts/sprint-110-agent-default-model-gpt55.md`
- Superseded（未实施）：`docs/contracts/sprint-109-agent-panel-iteration-vl-draft.md`
- Complete：`docs/contracts/sprint-108-agent-demo-alignment.md`
- Complete：`docs/contracts/sprint-107-agent-frontend-workspace-integration.md`
- Complete：`docs/contracts/sprint-106-agent-comic-creation-vertical-slice-draft.md`
- Complete：`docs/contracts/sprint-105-agent-runtime-foundation.md`
- 全局路线：`docs/implementation/agent-v1-implementation-roadmap.md`
- Durable Runtime 路线：`docs/implementation/agent-durable-chat-runtime-roadmap.md`
- `docs/contracts/sprint-104-agent-foundation-and-provider-spike.md`
- `docs/contracts/sprint-103-agent-conversation-demo.md`
- `docs/contracts/sprint-102-single-image-content-extraction-lio-fallback.md`
- `docs/contracts/sprint-101-restore-last-panel-real-photo-entry.md`
- `docs/contracts/sprint-100-task-failure-feishu-alert.md`
- `docs/contracts/sprint-99-knowledge-plan-template-block-chunking.md`
- `docs/contracts/sprint-98-content-extraction-gpt54-vl.md`
- `docs/contracts/sprint-97-knowledge-plan-llm-auto-chunk.md`
- `docs/contracts/sprint-96-original-story-dialogue-narration-dedupe.md`
- `docs/contracts/sprint-95-docker-coolify-deployment.md`
- `docs/contracts/sprint-94-async-style-test-history.md`
- `docs/contracts/sprint-93-style-prompt-vl-extraction.md`
- `docs/contracts/sprint-92-knowledge-plan-direct-prompt-mode.md`
- `docs/contracts/sprint-91-friendly-panel-count-mismatch-error.md`
- `docs/contracts/sprint-90-task-cancel-image-job-interrupt.md`
- `docs/contracts/sprint-88-admin-video-audio-visibility.md`
- `docs/contracts/sprint-89-aliyun-oss-storage.md`
- `docs/contracts/sprint-80-image-result-aspect-ratio-retry.md`
- `docs/contracts/sprint-87-video-resolution-follow-style-aspect-ratio.md`

## 最新规划

- 用户于 2026-07-28 确认 YouTube 能力最多拆为两次交付。Sprint 134 先完成管理员频道账号、
  频道别名与 AI 定义、对标账号、Native Agent 可发布视频登记，以及频道/分析/已发布视频的
  按钮式手动同步；不调用真实发布接口。
- Sprint 135 在 Sprint 134 事实来源上增加页面与 Native Agent 共用的异步发布服务、结构化
  `@频道`、发布确认、按钮式任务状态获取和永久已发布视频关联。发布成功必须保存
  `NativeAgentVideo.id → PublishTask.id → youtube_video_id`，供后续内容分析和迭代闭环使用。
- 真实接口只读探测已确认：频道列表返回 17 个频道；频道分析和视频分析 HTTP 200；随机频道
  `UCBC_-h9spHLqy23bAeYcPzg` 有 79 条已上传视频。无过滤视频列表返回 2005 条全局数据，因此
  正式同步必须使用服务端实际接受的 `where.one.channel_id`，不能照搬文档中缺少 `one`
  包装的示例。

## 最近完成的工作

- 完成 Sprint 143 Native Agent 创作账号 Context 修复：选择 `@创作账号` 后，后端不再只
  推导绑定 Style，而是持久化完整账号安全快照，并注入普通 Agent 与文案 Director、Writer、
  Reviewer。真实账号数据、浏览器标签、开发库迁移、定向测试和完整检查均已验证。
- 完成 Sprint 142 系统 Skill Disable / Enable：复用现有 `archived` 状态软删除 Skill，
  管理员可改变系统 Skill 状态，普通用户越权请求明确失败；Disabled Skill 保留全部历史，
  但不会进入新的资源引用和 Run。真实浏览器 Disable 三个系统 Skill 后完成服务重启验证，
  `@` 菜单不再出现 Skill，控制台无错误。
- 完成 Sprint 141 Native Agent 对话式资源引用：删除输入区顶部常驻的 Skill、创作账号、
  Style、频道和视频下拉框，改为统一 `@` 菜单、搜索、键盘选择和可移除标签。账号与直接 Style
  双向替换，账号标签展示绑定 Style 且后端仍按账号唯一推导；发布频道和审核视频按上下文出现，
  频道移除时级联清理发布参数。真实浏览器验收控制台无错误；完整检查覆盖 338 项后端测试、
  14 项前端测试和 Remotion 检查，未运行收费模型或真实发布。
- 完成 Sprint 140 YouTube 账号绑定风格：频道账号新增当前 Style 外键和绑定时间，列表、详情及
  独立绑定 API 展示和维护启用风格；远程频道同步保留本地绑定，被账号引用的 Style 删除请求会
  明确冲突。Native Agent 新增与真实发布目标分离的“创作账号”上下文，选中账号后由后端唯一
  推导并快照名称、Prompt、模型、比例和参考图，前端 Style 控件同步锁定；未绑定、风格停用/
  删除或请求试图覆盖账号风格都会失败，不使用默认风格。迁移已应用到开发库和空库全量链路；
  44 项定向测试及 `./scripts/check.sh` 全部通过，完整检查覆盖 338 项后端测试、8 项前端测试、
  前端生产构建、Remotion TypeScript 与 5 项模板测试。真实浏览器确认频道列表新增绑定风格列
  和未绑定状态；服务重启后的继续访问被 localhost 安全策略阻止，改由本地 API 验证绑定摘要和
  详情均为 HTTP 200，临时管理员与临时频道已删除。
- 完成 Sprint 136 YouTube 列表分页与可读性：频道账号前端不再固定读取 100 条，改为使用现有
  cursor/limit 后端分页，每页 10 条，并在搜索或状态筛选变化时回到第一页。新增单频道已发布
  视频分页 API，按 `uploaded_at DESC, id DESC` 稳定排序并严格过滤 `channel_id`；频道详情不再
  通过 ORM 关系整体加载视频，视频 Tab 独立读取当前页。两个列表统一展示总条数、当前页、总页数
  和边界禁用的上一页/下一页。YouTube 管理页面正文、表头、辅助信息、状态、表单和发布任务文字
  上调约 1–2px，保持既有深色暖橙、扁平紧凑视觉。真实浏览器确认 17 个频道分成 2 页、73 个
  视频分成 8 页且翻页数据正确，控制台无错误；`./scripts/check.sh` 通过 312 项后端测试、空库
  全量迁移、前端生产构建、Remotion TypeScript 检查和 5 项模板测试。
- 完成 Sprint 135 YouTube 异步发布与 Agent 频道引用：新增本地发布任务、两条 Alembic 迁移和
  页面/Agent 共用应用服务；创建前锁定频道、审核视频、标题、描述、标签、封面、视频 URL、
  可见性、AI 合成标记和计划时间快照。提交请求在保存远程任务 ID 后立即返回，网络结果不明确时
  标记为不可自动重建，频道详情只允许用户点击“获取状态”查询单个任务，不增加轮询或后台刷新。
  远程完成后同步永久已发布视频并保存三段 ID 事实链。Native Agent 使用结构化 `@频道` 和
  不可变 Run 确认快照，模型不能自行改频道或视频；页面发布和 Tool 均拒绝未确认、频道异常、
  视频未审核或无公网 URL 的请求。前端延续 Agent Studio 深色暖橙、扁平紧凑视觉，新增任务表、
  发布确认弹窗、状态标签、手动刷新和 Agent 视频审核登记入口。真实浏览器验证了频道任务空态及
  `@频道` 后置字段门禁；`./scripts/check.sh` 通过 310 项后端测试、空库全量迁移、前端生产
  构建、Remotion TypeScript 检查和 5 项模板测试。真实发布 smoke 因会创建外部任务，等待用户
  指定测试频道、测试视频并显式授权。
- 完成 Sprint 134 YouTube 频道账号与可发布视频基础：新增后端专用发布平台 Client、四张持久化
  表和 Admin API，频道远端事实与本地别名/账号定位/AI 定义分开保存，频道分析与视频数据只
  通过按钮同步；视频列表严格使用服务端实际接受的 `where.one.channel_id` 并处理游标分页，
  不会混入其他频道。可发布视频通过外键和唯一约束固定关联 `NativeAgentVideo.id`，并要求
  owner、成功生成结果和公网 URL。前端在 Agent Studio 增加 Admin-only“频道账号”，按用户
  确认的深色、暖橙、扁平信息层级实现列表、搜索/筛选、详情指标、账号定义、对标账号、已发布
  视频和明确的 Sprint 135 发布任务空态。真实只读 smoke 读取 17 个频道，并在样本频道读取
  51,345 总观看、236 小时观看时长和 73 条已发布视频；真实浏览器完成列表、详情和视频页验收。
  `./scripts/check.sh` 通过 303 项后端测试、空 SQLite 全量迁移、前端生产构建、Remotion
  TypeScript 检查与 5 项模板测试，`git diff --check` 通过。
- 完成 Sprint 126 Remotion 跟随源图比例与指定会话真实验收：修复开发库缺少 Sprint 124/125
  migration 导致历史会话 ORM 查询失败的问题；四张历史 Native 图片和 OSS 文件均完整。
  `render_story_video` 现在可读取同一 Conversation 历史 Native 图片和 owner 的成功 current
  Generation Task 图片，Composition 跟随首张图尺寸并拒绝混合比例。火山未返回 duration 时
  使用 `ffprobe` 读取真实时长。指定会话新 Run `d17b9b5e5f69430d8ca8ee4811ddf10d`
  真实生成四段语音和视频 `90152b17687745ce9116277a163f7efa`；最终 MP4 为
  1086×1448、30fps、H.264/AAC、41.96 秒、约 61.4 MB。
- 接入 Native Agent 固定 Remotion 视频 Tool：新增独立 Remotion 4.0.499 项目和
  `narrated-panel-v1` 模板，支持当前 Run 图片、旁白、整段字幕、七种受控 Motion Preset 与
  可选 BGM；新增 Python 渲染桥、Native Video 持久化与迁移、幂等 Tool 生命周期、MLflow
  Span、owner 资产权限、API/SSE 投影和对话 MP4 播放器。Skill catalog 可勾选“渲染故事视频”，
  Native Runner 仅按固定发布版本暴露 `render_story_video`。Docker 构建固定 Node、依赖与
  Chrome Headless Shell。真实 smoke 已覆盖两段 Scene 无 BGM，以及一段 Scene 带 BGM；
  `ffprobe` 确认 1080×1920、30fps、H.264 视频和 AAC 双声道音频。`./scripts/check.sh`
  通过 276 项后端测试、Python compileall、空 SQLite migration、前端生产构建、Remotion
  TypeScript 检查与模板测试，`git diff --check` 通过。本机 Docker CLI 无可用 Server，
  因此未执行完整镜像构建；Dockerfile 已包含固定 Node/Remotion/Chromium 与中文字体依赖。
- 接入 Native Agent 固定火山引擎语音 Tool：新增 V3 流式 TTS Client、固定
  `seed-tts-2.0-standard` / `zh_female_xinlingjitang_uranus_bigtts` 参数、Native Audio
  资产持久化与 owner 权限；Skill catalog 可选择“生成语音”，Native Runner 按固定发布版本
  动态暴露 `generate_image` / `generate_speech`，对话 SSE 快照展示可播放音频，纯语音 Run
  不再强制选择 Style。真实 Provider smoke 收到 HTTP 200 与 `20000000` 成功终态并生成
  24kHz mono MP3；`./scripts/check.sh` 通过 272 项后端测试、Python compileall、空 SQLite
  migration 和前端生产构建，`git diff --check` 通过。
- 将 Native Agent 同一模型 Response 内的 Function Tool 执行并发上限调整为 2；模型一次
  输出多个 `generate_image` 调用时，Runtime 最多并行执行 2 个图片 Provider 请求。动态 Style
  快照继续与当前 Skill Version 一起加载到同一个 `Agent.instructions`，不进入 Tool
  Description。仅执行 Native Agent 定向测试与 `git diff --check`，未执行完整 Sprint 验收或
  Deferred Evaluation。
- 修复 Skill 详情与编辑页长正文被裁切：根因是 Agent 模块外壳固定为 `100dvh` 且隐藏溢出，
  Skill 管理工作区此前没有自己的纵向滚动容器。现将桌面端滚动职责放到 Skill 主内容区，详情
  正文可随页面滚到完整末尾，编辑页可滚到表单底部且正文 textarea 保持独立内部滚动；移动端
  继续使用自然页面滚动。真实浏览器验证指定 Skill 详情主区 `scrollHeight=1992`、可滚至
  `scrollTop=1272` 并显示最后一条完成条件；编辑正文可滚至内部最大 `scrollTop=1017`，末尾
  文本完整可见，控制台无 error/warning。前端 TypeScript/Vite 生产构建与
  `git diff --check` 通过，未执行完整 Sprint 验收。
- 修正 Native Agent 图片 Provider 失败边界：`generate_image` 遇到 Provider 已明确拒绝的
  HTTP 400（包括本次安全政策拦截）时，仍先持久化失败 Tool Step 和
  `tool.failed` 事件，但不再由 Agents SDK 提升为终止整个 Run 的 `UserError`；现在会生成
  结构化 Function Tool Output 交回同一模型 Loop，由模型结合 Skill 和错误决定修改 Prompt
  重试或向用户说明无法继续。配置缺失、Provider 超时、响应解析、持久化异常等没有明确 400
  拒绝证据的错误仍会抛出并终止，避免把结果不确定的副作用当成普通失败继续执行。会话
  `2c250dd98dac486f8b6862440d385ad1` 的数据库证据同时确认所谓“双图”不是 Runtime 重复执行：
  每张图片来自不同 `tool_call_id` 和 Provider request ID，模型根据 Skill v2 的图片文字精确
  Review 规则，为去除末尾标点主动修改 Prompt 后重画。新增定向测试验证 Provider 失败会作为
  Tool Output 返回模型且 Step 保持 failed；13 项 Native Agent 测试通过，未执行完整 Sprint
  验收或 Deferred Evaluation。
- 将 Native Agent 过程展示收敛为通用 Responses 事件投影：删除为漫画流程额外加入的“主动
  输出创作决策”Base Instructions 和前端“创作思考”解释层，不再要求模型为了 UI 表演过程。
  Runtime 直接消费并持久化 `response.started`、`response.output_text.delta`、
  `response.function_call.arguments.delta/done` 和 `response.completed`，再与真实
  `tool.prepared/started/completed/failed/unknown` 执行事实按 `response_id`、
  `item_id`、`tool_call_id` 关联。前端按 Response 轮次实时展示模型实际输出、Function Call
  参数接收过程和 Tool 执行结果，可直接看到多轮 `Response → Function Call → Tool →
  Response`。Style 继续保留在独立 `image_generation_context`，只作用于图片规划、Prompt 和
  Review，不进入 Tool Description。12 项 Native Agent 定向测试、前端 TypeScript/Vite 构建
  和 `git diff --check` 通过；未执行完整 Sprint 验收或 Deferred Evaluation。
- 修正 Sprint 123 实时投影与图片 Review：`generate_image` Tool Description 不再拼入 Style
  名称、模型、比例或完整风格提示词，只保留稳定工具语义；前端 EventSource 启用跨端口会话
  凭证并直接消费逐条 `native.event`，不再只等待批次后的 `run.updated` 快照。真实失败 Run
  `aa1c0c7b9232458b90be1bc6a94ddca9` 已确认图片 Provider、资产下载和 Tool 均成功，400 出现在
  OpenAI 下一轮视觉 Review 下载阿里云 OSS URL 时；现改为从已保存资产生成官方支持的 Base64
  data URL 返回模型，避免模型服务端访问对象存储域名。11 项 Native Agent 定向测试、前端
  TypeScript/Vite 构建、真实 OSS 资产 data URL 转换、带登录 Cookie 的 SSE `native.event`
  返回和 `git diff --check` 均通过，未执行完整 Sprint 验收或 Deferred Evaluation。
- 完成 Sprint 123 Native Agent 可恢复 Runtime：保留 `openai-agents==0.18.3` 的 `Agent`、
  `function_tool` 和 Tool Loop，把执行入口切换为 `Runner.run_streamed()`；新增
  `native_agent_steps/events/context_items`，分别保存执行事实、可回放 UI Event 和 Agents SDK
  Session 上下文。模型 response、分批文本 delta、Tool prepared/running/completed/failed/
  unknown、checkpoint 与 Run 终态均产生有序事件；SSE 支持 `Last-Event-ID`/`after`，前端实时
  展示模型文字、模型轮次、生图状态和恢复状态。`generate_image` 以 SDK `tool_call_id` 派生
  幂等键，成功调用重放只返回已有图片；服务重启只恢复没有不确定副作用且 SDK Tool Output
  完整的 Run，Provider 或 SDK 结果无法同时确认时标记 unknown 并停止自动重画。按用户要求未做
  Worker lease、人工审批或 Evaluation。针对性 11 项与全量 263 项后端测试、compileall、空库
  migration、前端生产构建和 `git diff --check` 均通过。
- 为 Native Agent 对话生成图片增加点击放大：缩略图使用可聚焦按钮和明确的放大图标，打开后
  复用现有深色图片遮罩与原图资产，支持关闭按钮、点击遮罩和 Esc 关闭，并在关闭后恢复触发
  按钮焦点。按用户要求只运行前端 TypeScript/Vite 生产构建和 `git diff --check`，未执行完整
  Sprint 验收。
- 轻量修正 Skill 与 Native 对话的对应关系：移除 Native Skill 列表、Run 创建和执行阶段对
  `tool_names == ["generate_image"]` 的硬过滤；所有当前用户可见的已发布 Skill 都能进入选择器。
  Skill 编辑器将该区域改为“相关 Tools（可选）”，明确其只帮助理解可能使用的能力；Runtime
  实际传给模型的 Tool 仍由代码注册决定，当前保持 `generate_image`，图片 Review 使用模型原生
  视觉。数据库中的 `故事转化图片通用` 已发布并启用 v2，直接列表检查现在返回该版本。按用户
  要求未运行完整 Sprint 验收，只执行 Native Loop 8 项针对性测试、前端生产构建和
  `git diff --check`，均通过；前后端已重启。
- 完成 Sprint 122 Native Loop 实时事件与 Trace 语义：真实 MLflow Trace
  `tr-201a90ff214c8da0e0c5d1b824a28c8c` 经 API 核实根 Trace、4 个
  `native_agent.generate_image` 和 4 个 `native_agent.image_provider` Span 全部为 `OK`，
  截图中的暗红色是 MLflow 3.14 `TOOL` 类型配色而非错误。新 Trace 保持
  `generate_image=TOOL`，把内部 Provider 修正为 `TASK`，并对成功/失败显式写入
  `OK/ERROR`。Native POST 改为 `202 Accepted` 后立即返回 queued Run，由新增进程内单
  Worker 按 Run ID 后台执行；启动恢复 queued Run，并明确失败关闭无法安全重放的中断 Loop。
  新增 owner-only Run SSE 快照流，前端把用户消息、模型规划、每次 Tool 提交、图片完成、视觉
  Review、图片和终态按同一对话时间线实时更新，新事件自动滚动；提交不再长期占用 loading。
  针对性 8 项和全量 260 项后端测试、Python compileall、空库 migration、前端生产构建及
  `git diff --check` 通过。本地前后端已重启，MLflow `/health` 返回 `OK`；真实浏览器自动验收
  被 localhost 安全策略阻止，未绕过策略，也未执行 Deferred Evaluation。
- 完成 Sprint 121 Skill 详情与编辑闭环：新增稳定的 `/agent/skills/{skill_id}` 只读详情页和 `/agent/skills/{skill_id}/edit` 编辑页；详情完整展示正文、状态、权限、Tools、revision、更新时间与版本入口。列表对所有 Skill 提供“查看详情”，个人未归档 Skill 同时提供“编辑”；系统 Skill 保持只读复制，已归档个人 Skill 保持只读并可先恢复。真实浏览器使用系统 `简单图片故事` 验证只读详情与复制，并用个人副本完成描述编辑保存、revision 1→2、保存回详情、刷新、后退和前进，控制台 0 error / 0 warning。路由测试、前端构建、`git diff --check` 和 `./scripts/check.sh` 全部通过；全量检查覆盖 257 项后端测试和空库 migration。正式 Evaluation 继续 Deferred。
- 完成 Sprint 120 Native Loop MLflow 与 Agent UI 一致性：新增固定官方 3.14.0 镜像、localhost
  映射、SQLite/artifact named volume、健康检查和单 worker 的本地 Compose；默认 4 worker 在
  2GB Colima 中 OOM 后未静默忽略，固定单 worker 后容器持续 healthy。开发 `.env` 已启用
  `doodlestory-agent-local` 与内容记录，仓库示例仍默认关闭；Native Run 新增可按
  `native_agent_run_id` 唯一检索的根 Trace，包含模型 Loop、generate_image 与图片 Provider
  子 Span，模型输入/输出可供本地评估，URL、Authorization、密钥和路径继续强制脱敏。真实本地
  Trace `tr-feb7cf66a2b0fff48f93f7879baedaff` 写入成功。前端把浅色 Native 主区统一为既有深色
  Agent Studio，textarea 显式使用浅色文字、深色背景、橙色 caret/focus；全新认证浏览器验证
  `/agent` 与 `/agent/skills` 0 console error。`./scripts/check.sh` 覆盖 257 项后端测试、空库
  migration、Python compileall 和前端构建并通过；正式 Evaluation 未实施。

- 完成 Sprint 119 最小原生 Agent Loop：在隔离分支 `codex/simple-agent-loop` 新增完全独立于旧
  Agent Workflow 的 Conversation/Run/Item/Image 表和 `/api/v1/agent-loop/*` API；正常
  `/agent` 前端入口已切到新链路，只选择一个发布版 Skill 和一个 Style。Runtime 通过真实
  `Agent(tools=[generate_image])` 运行 Agents SDK Loop，`generate_image` 返回
  `ToolOutputImage` 让同一个模型原生看图并决定是否重画；Python 不做故事、分镜、Prompt 或
  Review 阶段路由。新增系统 `简单图片故事` Skill，旧 Agent API 与 Agent queue 不再在应用正常
  启动时挂载。自动化覆盖真实 Function Tool、图片回填、唯一 Tool/串行限制、新旧数据隔离；
  `./scripts/check.sh` 覆盖 256 项后端测试、空库 migration、Python compileall 和前端生产构建
  并通过。真实浏览器确认正常入口、Skill 管理、配置表单、会话侧栏与详情入口可用且控制台无错误。
  本次未点击“运行 Agent”，没有产生外部模型或图片 Provider 费用；真实 Provider 实跑明确留作
  成本验收，不以 Mock 或占位结果冒充。积分、异步队列、恢复、审批和 Evaluation 未实施。

- 整合 Sprint 116 完成基线与 Sprint 117 新规划：确认两个窗口从 Sprint 115 tip 分叉后，在独立工作树合并 Sprint 116 实现/QA 闭合提交与 Sprint 117 Skill 管理/通用 Agent Loop 合同、规格和四张高保真视觉基准；冲突按最新产品决定解决为 Sprint 116 `Complete（Closed）`、Sprint 117 `Active`、正式 Evaluation `Deferred`。用户明确授权让另一窗口继续开发 Sprint 117。整合树重新运行 `./scripts/check.sh`，240 项后端测试、Python compileall、空 SQLite migration 和前端生产构建全部通过；未覆盖共享工作树的未跟踪用户文件。

- 正式闭合 Sprint 116 合同：按 `qa-sprint-review` 对 9 项 Done means、合同要求的自动化、真实 Provider/浏览器证据、已知缺口和下一阶段边界逐项复核，形成 `docs/qa/sprint-116-agent-panel-version-vl-loop-report.md`，结论为 `PASS`，无阻塞项。2026-07-26 再次运行统一 `./scripts/check.sh`，240 项后端测试、Python compileall、空 SQLite Alembic migration 和前端生产构建全部通过。本次闭合未重复调用慢图片 Provider，沿用同一实现分支 2026-07-25 的真实验收证据；没有新增产品 Mock、兜底或兼容逻辑。合同闭合本身没有自动激活下一 Sprint；用户随后已明确授权激活新的 Skill 管理与通用 Agent Loop Sprint 117。

- 完成 Sprint 116 Panel/VL/版本与任务控制闭环：`generate_image` 现在可在完整 Conversation → Task → Panel → Version 权限链上只为目标 Panel 创建新版本，复用任务风格、比例、角色参考和来源 Prompt；接受/恢复保存明确用户事实，均幂等，恢复不调用 Provider、不扣积分、不删除历史。新增真实多模态 `inspect_image`，严格保存 Tool、Provider/model、延迟、结果和错误，支持五类检查与四种 verdict；每版本最多检查一次，每 Turn 只有用户显式授权时才允许一次额外自动修订。Runner 仍只调用原子 Tool，图片长任务继续走既有队列；修正图片 Worker 同步等待 Agent 在慢 VL 下误标成功图片的问题，改为线程安全非阻塞入队，并确定性保护纯视觉修订不改图片文字/布局。检查器新增版本历史、VL 摘要、扣分确认、再生成、接受、恢复、引用和 Run 暂停/继续，失败保留输入；事件覆盖版本、检查和运行控制。真实本地隔离验收创建 Panel 1 v2，`gpt-5.4` VL 返回 accept（0.98/0.90/0.95/1.00/0.93），余额 28→27；接受 v2、恢复 v1、刷新和后端重启后状态仍恢复且余额保持 27。用户确认无需为修复重复等待慢生图，正式代码未加入 Mock。针对性 18 项和全量 240 项后端测试、空库 Alembic migration、Python compileall、前端生产构建及 `git diff --check` 全部通过。

- 完成 Sprint 115 结构化资源引用与同一任务续作：新增五类有界 Resource API 和统一 `AgentResourceResolver`，消息入队前批量校验数量、状态、owner、父子关系与组合，服务端覆盖伪造 display name，并把规范引用和不含 owner/存储路径/URL/密钥的安全摘要保存到现有 `resource_refs_json`；`build_agent_input()` 按接收时快照重放历史资源。Runtime 明确区分普通讨论、新漫画和已有任务只读续作，Task 引用复用同一 GenerationTask，版本写请求明确留给 Sprint 116。Character 引用真实创建任务角色/appearance/逐 Panel 关系，并把参考资产传入图片 Provider。前端完成分组搜索、loading/empty/error、组合禁用解释、层级自动引用、任务卡/检查器引用，以及 Idea/资源按会话分离持久化；Conversation 切换同步重置 SSE cursor，避免跨会话游标导致活动流断开。真实 Conversation `4ae7adb3b5b44e9686028a5a9310901a`、Task `ca8677b7a4944f499f65f9d36b493399` 使用 `@粗线条暖色 + @林夏验收角色` 生成两张真实图片，余额 30→28；检查器引用没有覆盖草稿，刷新后五类标签恢复；只读续聊 Run `7285c1a1008845e380b036c0c84a84f1` 复用同一 Task 且 image call 为 0，显式“重新生成”也未新增 Task/Image 或扣分。针对性 37 项、Python compileall、前端构建和 `git diff --check` 通过；全量 `./scripts/check.sh` 覆盖 230 项后端测试、空库 migration 与前端生产构建并通过。未实现 Sprint 116 的 Panel/VL/版本写操作或 pause/resume。

- 激活 Sprint 115 结构化资源引用与同一任务续作：已完成合同、Agent Runtime、任务/角色/风格模型以及数据库、后台任务、前端与 UI 规范评审。确认沿用 `agent_messages.resource_refs_json` 保存规范引用与受控安全摘要，不新增通用资源表；固定角色将复用现有 `TaskCharacter`、`TaskCharacterAppearance` 和 `TaskPanelCharacterAppearance` 快照/参考链路，已有任务引用只进入只读续作语义，不开放 Sprint 116 写操作。

- 完成 Sprint 114 `idea-to-comic` Skill、方案确认与真实事件流：固定两格 ComicPlan 升级为版本化 2–8 Panel schema，Runtime 校验连续 key、重复剧情、数据库风格 ID/比例和图片预算；新增 `agent_artifacts`、`agent_approval_requests`、`agent_events` migration、hash 绑定、owner-only 幂等决策、修改版本保留、等待恢复和批准后重新入队。正式 Runner 显式加载 `idea-to-comic` 并记录 Skill 版本/hash，初次或修改规划只保存安全 Artifact，未批准前不创建 Task/Panel/Image Job 或占积分；`generate_image` 再次核验 approved hash、Panel、Prompt、比例、预算和 Run 状态。新增持久化 SSE cursor、受控公共事件、心跳、连接错误与手动重连，移除旧 2 秒轮询；前端增加 v1/v2 方案卡、状态区分、明确积分按钮、修改反馈、活动流和按 Panel 计算的真实进度。真实 Conversation `d62f8c260a1241de876ebe64e4d15607`、Run `3bbb19b4725c47e8a93221b78b254654` 在余额 30/占用 0 时等待确认；修改后 v1 保留为 superseded，批准 v2 后创建 Task `e429bdabef884e24b8337c717c2df78c`，两张 `gpt-image-2` 图片成功，余额 28/占用 0。后端中断时页面显示连接错误，手动重连补齐完成事件且未重复生图。针对性 30 项、全量 223 项后端测试、空库 migration、Python compileall、前端生产构建、`git diff --check` 和 `./scripts/check.sh` 全部通过。未实现 Sprint 115 资源引用、Sprint 116 VL/Panel 写操作或 pause/resume。

- 完成 Sprint 113 通用 Skill / Tool Runtime 基础：新增独立于 `.agents/skills/` 的 `backend/app/agent_skills/`，服务启动扫描目录并校验 name/frontmatter/version/重复名/UTF-8/64 KiB 上限/32 个 catalog 上限/符号链接和路径边界；初始 `idea-to-comic` v1 只作为骨架，不自动切换正式链路。新增只读 `load_skill`、代码级 Tool Registry、严格输入/安全输出 schema、RuntimeContext 与 Generic Tool Executor；Tool 副作用前提交 call Step，等待保存 checkpoint，完成先写 result Step，稳定幂等键重放复用既有 Step/job/result。现有固定两格链路的真实 `GeneratedImage` job 创建已改走统一 `generate_image` adapter，并继续复用任务、Panel、图片 worker、资产与积分基础设施；Run 取消门禁不会启动新副作用。实际 MLflow 测试确认 `agent.skill_load` span 与 AgentStep ID、版本/hash 对齐，默认脱敏 trace 不含 Skill 正文。未新增 migration、Workflow DSL、外部队列、多 Agent、用户 Skill、HITL、SSE、VL、TTS 或 Remotion。针对性 20 项与全量 219 项后端测试、空库 migration、Python compileall、前端生产构建和 `git diff --check` 全部通过。

- 完成 Sprint 112 Agent MLflow 可观测性基线：锁定 `mlflow==3.14.0`，官方 autolog 已验证兼容 `openai-agents==0.18.3`、`openai==2.45.0`、自定义火苗/LIO `AsyncOpenAI` client、Responses API 和现有 `RunConfig(tracing_disabled=True)`。新增默认关闭的 MLflow 配置与启动校验、客户端 span processor 脱敏、`agent.run/model_call/tool_call/tool_wait/tool_result/finalize` 层级、`agent_run_id` 唯一查询 smoke 和结构化 `observability_error` 隔离；数据库 schema、Provider 路由、恢复和用户界面均未改变。火苗恢复后，真实主链路 Run `c3c1dd54fa0f4d0e807786cc89ee5ac2` 唯一对应 trace `tr-7cc99632fd625cb4abe72b729fcc91be`，`huomiao/gpt-5.5` attempt 1 无 fallback，requests/input/output/total 为 `1/121/31/152`，provider response ID 与数据库 AgentStep 一致；受控临时错误→真实 LIO fallback 与永久错误不 fallback 也通过。完整 trace 扫描未出现用户正文、模型回复、邮箱、Authorization/Bearer、HTTP(S) URL 或内部路径；开发/生产直接 SQLite/file Tracking URI 现会明确失败。`./scripts/check.sh` 覆盖 209 项后端测试、空库 migration、Python compileall 和前端生产构建并通过。证据见 `docs/testing/agent-mlflow-compatibility-spike.md` 和 `docs/testing/agent-mlflow-smoke-report.json`。

- 完成 Sprint 111 独立 Agent Shell 与只读任务检查器：正式 `/agent` 不再渲染旧工作台侧栏或“传统构建 / AI 构建”切换，改为只包含真实新建、搜索、历史会话、用户、积分、退出和低层级传统工作台入口的独立 Shell。真实 Agent Run 任务卡收敛为紧凑标题、状态、进度、Panel 当前图与 Run 状态，并新增 `/agent/{conversation_id}/tasks/{task_id}` AI 专属只读检查器；检查器支持稳定 URL、刷新/前进/后退、只读 Panel 选择、真实当前图片与最多 20 个版本摘要、明确读取错误、焦点陷阱及关闭后草稿/滚动/触发焦点恢复。后端新增 Conversation→AgentRun→GenerationTask owner 三层鉴权读取 API，普通用户、其他用户、Admin、未关联 Task 与跨 owner Task 权限均有测试，旧 `/tasks` 保持不变。Agent API 6 项、Agent 路由 3 项、前端生产构建、Python compileall、`git diff --check` 和 `./scripts/check.sh` 全部通过；全量检查覆盖 198 项后端测试和空库迁移。1440×900、1280×800 真实浏览器与有效认证 0 console error / 0 warning 通过，证据见 `docs/testing/agent-independent-shell-readonly-inspector-browser-report.json`。未实现 Mock、旧任务详情跳转、资源引用、Panel 写操作、VL、Skill、MLflow、SSE、HITL、Memory、TTS 或 Remotion。

- 完成 Agent 漫画 V1 最新路线与逐 Sprint 开发合同：保留 Sprint 105–108、110 的真实完成记录，但明确 Sprint 107/108 的统一旧 Shell、顶部模式切换和跳转旧 Task 详情决定已被后续产品方向替代。新路线从 Sprint 111 到 117 依次交付独立 Agent Shell/只读检查器、MLflow 观测、Skill/Tool Runtime、`idea-to-comic` Skill + Artifact/Approval/SSE、结构化 Style/Character/Task/Panel/Image Version 引用、Panel 版本/VL/pause-resume 闭环，以及 Evaluation 内部开放门槛。每个合同均写明目标、前置、API/SQL/前后端要求、Out of scope、Done means、自动化/真实浏览器/Provider 验收和新窗口启动提示词；正式 `/agent` 明确禁止 Mock、占位成功和未接通假操作。原 Sprint 109 Draft 标记为 Superseded，其目标重新拆入 Sprint 116。当前没有修改运行代码或数据库。

- 完成 Sprint 110 Agent 默认模型切换：火苗主平台与 LIO 备用平台共用的 `AGENT_MODEL` 默认值由 `gpt-5.6-terra` 改为 `gpt-5.5`，同步配置示例、漫画 Panel 模型快照、SDK/Runtime 探测脚本和相关测试；历史兼容性报告保留当时真实使用的旧模型记录。后端与前端开发服务已重启，并确认运行时加载 `gpt-5.5`。

- 完成 Sprint 108 正式 Agent 前端与已调试 Demo 对齐：移除 `/agent` 内部大圆角工作区和后台聊天页视觉，迁入 Demo 已确认的平面全高会话导航、空白创作入口、固定输入区和克制的单一橙色状态层级；三个快捷入口只填草稿，`+`/`@` 只搜索真实 active 风格，支持选择、移除且不覆盖输入。会话列表按日期显示真实摘要、状态和时间，草稿与风格按 Conversation 恢复，运行期间可继续准备草稿，传统/AI 模式往返回到最近 Conversation。真实 Conversation `3aa7454244754acda99f9475433195e5`、Run `e89097e4d0294e01b27e40dd7f2f71bb`、Task `c59151ece9a34b47a32042aeafcfbc04` 和图片 `22dec874850045ed906428471781f1a8`、`8538ef7bd44f4291adae88738fc9caef` 全部成功，积分从 30 降至 28；Agent 卡片与传统详情确认同一 Task。1440×900、1280×800、刷新、模式往返、键盘与认证后 0 console error/warning 通过，证据保存于 `docs/testing/agent-demo-alignment-browser-report.json`；`./scripts/check.sh` 覆盖 196 个测试、空库 migration 和前端构建。Panel/VL 继续保留在 Sprint 109 Draft，未实现角色、Panel 操作、暂停、VL、Mock 或占位能力。

- 激活 Sprint 108 正式 Agent 前端与已调试 Demo 对齐：完整回放 Sprint 103 Demo 的空白会话、三个快捷入口、`+`/`@` 资源搜索、Panel 3 检查器、保留草稿引用、重新生成确认、暂停说明和跨会话草稿恢复；将原 Panel/VL Draft 顺延为 Sprint 109。Sprint 108 只重构 `/agent` 内部布局并保留 Sprint 107 的真实 Conversation、Message、Run、Style、TaskCard 和 GenerationTask 关联，不实现或展示角色、Panel 修改、版本、暂停、VL、Mock 或占位能力。

- 完成 Sprint 107 传统构建与 AI 构建正式前端整合：移除侧边栏独立 `漫画 Agent` 一级入口，让 `/tasks` 与 `/agent` 共用 `图文任务` 全局导航语义，并在两页顶部增加同一个 `传统构建 / AI 构建` 切换。AI 模式保留真实会话历史、空白新对话、历史恢复、一个真实风格引用、Run 状态和真实任务卡片；Conversation 切换会清空旧详情并恢复各自未发送 Idea/风格草稿。Agent 任务卡片新增完整 task ID 和 `/tasks/{task_id}` 入口，传统任务行同步展示完整 ID。真实浏览器创建 Conversation `e1c4bb05abe24e3ea80fc09bb3f7431f`、Run `a176d894556b471d9ef887abbeea6c8d` 和 Task `0cec81a45b1b4139bd6a43ff4c4c8135`，使用 `粗线条暖色` 生成两张真实图片，积分从 30 扣至 28；Agent 卡片、传统列表和任务详情确认引用同一任务。1440×900 与 1280×800 完成空白、运行、成功、任务详情、草稿切换、刷新、前进后退、直接链接和键盘切换回归，认证后的检查阶段无新增 console error/warning。证据保存于 `docs/testing/agent-frontend-workspace-integration-browser-report.json`；生产构建、`git diff --check` 和 `./scripts/check.sh` 通过。未实现 Sprint 108 或其它明确排除能力。

- 完成 Sprint 107 开发前置规划并激活合同：全局路线在已完成的两格真实漫画纵向链路与 Panel/VL 之间增加“正式前端整合”阶段；正式产品保留一套 DoodleStory 全局侧边栏、账号、积分和资源入口，在 `/tasks` 与 `/agent` 顶部提供 `传统构建 / AI 构建` 切换。Sprint 107 只把真实会话、一个真实风格、运行状态和同一 GenerationTask 任务卡片整合进正式页面，不实现角色引用、Memory、创作规则、自定义 Skill、Panel/VL、抠图、Remotion、文字转语音或视频解说。原 Panel/VL 合同顺延为 Sprint 108 Draft。新窗口交接已更新为 Sprint 107 的必读文件、实施顺序、浏览器验收和可直接粘贴的启动提示词。规划文档引用一致性、`git diff --check` 与 `./scripts/check.sh` 已通过；全量检查覆盖 196 个后端测试、空库 Alembic migration 和前端生产构建。
- 明确 Sprint 103 Agent 会话 Demo 的版本生成与暂停语义：Panel 操作中的`重新生成`改为`再生成一个版本`，执行前通过确认弹窗说明复用当前最终 Prompt、风格和角色参考资源、保留旧版本、创建下一个版本以及正式功能预计消耗 1 积分；确定性演示会展示 v2 保留、v3 生成中和 v3 待决定。`暂停任务`从 Panel 操作区移到任务顶部，只阻止后续 Panel 和 Agent 步骤，明确说明已提交给图片 Provider 的请求仍会完成并保存；历史列表、会话顶部、任务卡和检查器同步暂停/继续状态，已完成任务不展示暂停入口。设计 Brief 与 Demo README 已同步该语义。本次仍只修改独立前端 Demo，不接后端或 Sprint 106。验证：Playwright 在 1440×900 完成新版本确认、v2 到 v3 状态变化和任务暂停回归，控制台 0 error/0 warning；`node --check`、`git diff --check` 和 `./scripts/check.sh` 通过，覆盖 196 个后端测试、空库 Alembic migration 与正式前端生产构建。
- 完成 Sprint 106 对话创建两格真实漫画纵向链路：新增严格两格 `ComicPlan`，解析且鉴权一个风格资源引用；当前风格库没有 owner 字段，因此只允许已登录用户使用 active、未删除的全局风格，并拒绝伪造、停用或删除 ID。Runtime 原子创建 GenerationTask、两个 Panel 和两个 GeneratedImage job，Agent 的 `image_prompt` 直接成为图片 job `final_prompt`，不经过旧故事拆分或最终 Prompt 编译。两个 `generate_image` Tool Call 在副作用前保存稳定幂等键，Run 等待真实图片 job 后各写一次 Tool Result，再恢复最终模型回答；恢复复用既有 task/job/积分流水，不重复生图或扣费。新增 `agent_runs.task_id` migration、Conversation 详情任务卡片/Run 摘要和正式 `/agent` 会话页面，支持有界历史、选一个风格、应用级状态、两张真实图片、刷新及重新打开恢复。真实 HTTP smoke、纯浏览器提交和中断恢复均通过，完整脱敏证据保存于 `docs/testing/agent-comic-vertical-slice-smoke-report.json`；认证后的 Agent 页面控制台 0 error / 0 warning。针对性回归 39 个测试、Python compileall、前端生产构建、`git diff --check` 与 `./scripts/check.sh` 全部通过；全量检查覆盖 196 个后端测试和空库 Alembic `upgrade head`。当时创建的 Panel/VL Draft 已顺延为 Sprint 108；VL、Panel 修改/重试/版本恢复、角色、抖音或旧 Pipeline 迁移仍未实现。

- 迭代 Sprint 103 独立 Agent 会话前端 Demo，不触碰正式 React 页面、后端或 Sprint 106 实现：页面现在默认进入空白对话，只克制展示三个常用角色/风格资源；输入区资源入口支持搜索，也可通过输入 `@` 唤起。任务卡去除重复的进度消息并展示原位行动状态，缩略图可直接打开具体 Panel。右侧详情改为 Panel 检查器，明确区分“当前选中”和“Agent 正在运行”，展示大图、版本、剧情目标、检查结论，以及接受、重试、恢复、暂停和“引用 Panel 并修改”等确定性演示动作。资源与输入草稿按对话保存，引用 Panel 不再覆盖用户草稿，切换历史对话后能够恢复。设计 Brief 和 Demo README 已同步默认空白页与显式引用语义。验证：`node --check docs/design/agent-conversation-demo/app.js`、`git diff --check` 通过；Playwright 在 1440×900 完成空白页、资源搜索、任务卡直达 Panel、保留草稿引用 Panel、跨对话恢复链路，控制台 0 error/0 warning；`./scripts/check.sh` 通过，覆盖 196 个后端测试、空库 Alembic migration 和正式前端生产构建。
- 完成 Sprint 105 可持久化 Agent Runtime 基础：锁定 `openai-agents==0.18.3`、`openai==2.45.0` 和 Responses API，新增独立 SDK 探测脚本并用真实火苗/LIO `gpt-5.6-terra` 分别完成 Function Calling、Tool Output、final response 和应用侧历史重放；脱敏证据保存于 `docs/testing/agent-sdk-provider-compatibility-report.json`。新增 Alembic revision `x8f9a0b1c2d3`，只创建 `agent_conversations`、`agent_messages`、`agent_runs`、`agent_steps`，并补齐 owner、消息顺序、恢复查询和幂等约束/索引。新增 Conversation 创建/分页/有界详情/发消息与 Run 查询 API，普通用户和 Admin 均只能访问自己的 Agent 数据；资源引用以受控 JSON 保存但不解析。实现只调度 `run_id` 的进程内队列、应用数据库完整上下文、文本版 `ComicDirectorAgent`、模型 Step/最终消息事务 checkpoint 与启动恢复。Router 关闭 SDK/client retry，火苗只对允许的临时错误重试一次后切 LIO；永久错误不切换。故障注入证明 fallback 后只有一个回答，恢复测试证明成功模型 Step 和重复投递不重复调用或写消息。真实两轮 Conversation `7980d1bac60b476f834e8d191fa6a832`、Run `7fdd4824f69243ae94c450198628e00f` / `0e744b264dc54b1180b475210351d52d` 验证第二轮从应用数据库取回第一轮上下文，证据保存于 `docs/testing/agent-runtime-two-turn-smoke-report.json`。验证：4 个 Agent 测试模块共 18 个测试通过，真实双平台 SDK 探测与真实两轮 Runtime smoke 通过，Python compileall、空库 Alembic `upgrade head`、OpenAPI 路径校验、`git diff --check` 和 `./scripts/check.sh` 通过；全量检查覆盖 190 个后端测试与前端生产构建。Sprint 106 已按交接要求评审并激活，但本次未实现 ComicPlan、生图 Tool 或正式前端。
- 完成 Agent V1 全局实施路线和新窗口交接准备：新增从阶段 0 到阶段 6 的全局路线图，把 Runtime、真实对话生图、Panel/VL 迭代、资源与参考改编、旧 Pipeline 迁移和发布门槛串成一条路径；每个阶段只定义交付效果和退出门槛，具体实现继续由小 Sprint 合同控制。Sprint 105 已作为唯一 Active 合同，聚焦 OpenAI Agents SDK 决策门、四张最小 Agent 表、Conversation/Message/Run API、应用侧上下文、进程内 Runner 和火苗到 LIO Router；Sprint 106 以 Draft 保存，只预定义“Idea + 一个 @风格 → 两格真实漫画”的纵向链路，阶段 1 未通过前不得实现。新增新窗口必读顺序、两阶段启动提示词、开发顺序和验证收尾规则，并明确保留用户未跟踪文件。模型证据同步更新：火苗和更新 API key 后的 LIO 使用 `gpt-5.6-terra` 均通过现有五组 HTTP 探测；Sprint 105 仍需用实际 Agents SDK 验证 Responses Function Calling/Tool Output，不能把基础 Responses 文本通过误当成 SDK Tool Loop 已通过。
- 完成 Sprint 104 Agent 开发前置契约与真实模型平台验证：新增 Agent V1 精简 PRD、单 Agent Runtime/状态/checkpoint 设计和基础 Tool 契约，明确创作决策由 Agent 承担，Runtime 只负责权限、持久化、预算、幂等和 Provider 可靠性，不把旧 pipeline 的 prompt 拼接步骤原样包装成 Tool；会话、Run、Step、Tool Call/Output 与 `@资源` 由应用数据库保存，页面关闭或服务重启后可从完整步骤恢复。新增脱敏兼容性探测脚本和 7 个离线单测，初次基于旧模型配置完成能力探测；随后按用户要求将两个平台临时统一为 `gpt-5.6-terra` 复测。火苗全部通过；LIO 第一个 key 因 `[origin]` 分组无渠道失败，更新 key 后 Chat、JSON、Chat Function Calling/Tool Output、多模态和基础 Responses 文本全部通过。实测确认 Router 必须联合判断 HTTP 状态、`invalid_request`、`model_not_found` 和错误语义。新增 20 个 Agent Eval 场景与确定性、质量、运行三层评估规则。未安装 Agents SDK，未实现 Router/Agent Loop/数据库迁移，也未修改现有生产生成链路。验证：兼容性脚本单测、脚本编译、Eval JSONL 校验、`git diff --check` 和 `./scripts/check.sh` 通过；全量检查覆盖 172 个后端测试、空库 Alembic 迁移和前端生产构建。
- 完成 Sprint 103 Agent 会话前端交互 Demo：在独立目录 `docs/design/agent-conversation-demo/` 实现可点击原型，首屏以历史会话和当前对话为主体，支持新建空白对话、切换并继续历史对话、对话内持续更新的漫画任务卡片、按需打开任务详情、选择 Panel 后带回输入区，以及通过资源菜单引用风格、角色和任务；同步把设计 Brief 从画布优先修正为会话优先。Demo 使用明确标注的确定性本地数据，不连接后端、模型或积分系统，也不修改现有正式前端。浏览器在 1440×900 和 1280×800 视口完成核心链路回归且控制台无错误；`node --check docs/design/agent-conversation-demo/app.js`、`git diff --check` 和 `./scripts/check.sh` 通过，完整检查覆盖 165 个后端测试、空库 Alembic 迁移和前端生产构建。
- 完成 Sprint 102 图文逐图内容提取与 LIO 备用重试：用户明确将目标从跨页故事理解改为逐张提取可用于复刻的图片可见内容。实现前先用最近真实抖音图片完成 LIO 单图冒烟测试，当前 `gemini-3.1-flash-lite-preview-thinking-minimal` 能识别上下分格、人物动作、场景、原文文字和文字位置。后端链路现按 `display_order` 顺序逐图请求，每次只传一个公网 `image_url`；单图先调用 `TEXT_FALLBACK_*` 当前指向的火苗平台，配置、请求、空响应或结构校验失败后切现有 `LIO_*`，LIO 最多请求 3 次，任意图片仍失败则整项失败。后端为成功结果确定性添加连续 `第X页` 并按原顺序合并，不再依赖模型生成页码。验证：内容提取与风格提取针对性测试、`backend/.venv/bin/python -m compileall backend/app`、`git diff --check` 和 `./scripts/check.sh` 通过；完整检查覆盖 165 个后端测试、空库 Alembic 迁移和前端生产构建。
- 完成 Sprint 101 恢复最后一张真人图片入口：按用户要求在图文任务创建弹窗重新开放 `最后一张真人图片` checkbox，默认关闭；普通任务创建和 DY 爆款复刻创建参数都会读取用户选择并传给后端。`去掉画面文字` 入口继续隐藏并固定关闭，避免恢复此前被要求隐藏的另一个开关。验证：`npm run build --prefix frontend`、`git diff --check` 和 `./scripts/check.sh` 通过，覆盖 164 个后端测试、空库 Alembic 迁移和前端生产构建。
- 完成 Sprint 100 图文任务失败飞书告警：按用户要求为正式图文生成任务增加失败告警能力，设计为 `TASK_FAILURE_ALERT_WEBHOOK_URL` 环境变量驱动，不把真实 webhook 写入仓库；`GenerationTask` 新增 `failure_alert_sent_at` 用于同一个 failed 状态去重；告警只包含任务排查所需元信息和可选任务链接，不包含用户原始全文。已覆盖人物参考图失败、panel 图片全部失败、服务重启不可恢复中断、步骤异常和 worker 未处理异常等会把任务置为 `failed` 的路径；任务手动重试会清空告警标记，重试后再次失败可重新通知。验证：`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_task_failure_alerts backend.tests.test_task_worker_recovery`、`backend/.venv/bin/python -m compileall backend/app`、`git diff --check` 和 `./scripts/check.sh` 通过，覆盖 164 个后端测试、空库 Alembic 迁移和前端生产构建。
- 修正知识方案自动拆页对全局模板的误判：用户提供“正向提示词 + 多个知识条目 + 收尾金句 + 负向提示词”时，旧 prompt 容易把“正文使用2条横向内容条+1条收尾金句栏”当成单页版式约束，导致煤气/舍财/收尾金句这类连续知识内容被切成 1 张图。现已明确正向提示词里的页眉、旧纸底、边框、作者栏、字体、插画风格和负向提示词是每页继承的全局模板；自动模式页数优先由独立知识条目、空行块、`副文字 + 画面` 组合和收尾金句块决定。只有用户明确写“单页 / 一张图 / 全部内容放同一页”时，才允许把多个条目合并成一页。前端知识方案提示、规格和测试已同步。
- 切换图文内容提取 VL 到 `gpt-5.4`：线上内容提取 `025b8b78e1cc454583e307ea87fa693d` 下载并注册了 14 张图片，但 Qwen VL 最终只返回 `第1页` 到 `第12页`，且把末尾图片内容合并/跳页，旧逻辑仍标记成功。现已把图文内容提取从 SiliconFlow/Qwen 改为调用 `TEXT_FALLBACK_*` 配置的 OpenAI 兼容 `gpt-5.4` 多模态模型；结果保存前会校验模型输出页码必须严格等于下载图片的 `1..N`，少页、跳页、合并页或重复页会明确失败并提示图片解析页数和下载图片数量不一致。该变更不把 Qwen 作为兜底，不自动补页，不影响视频音频转写和角色参考图外观理解。
- 补充抖音导入 Cookie 部署覆盖流程：新增 `scripts/install-douyin-cookies.sh`，用于把本机或远程节点上的 `cookies.json` 写入运行中的 `douyin-import-service` 持久化 volume 路径 `/app/douyin-downloader/.cache/douyin/cookies.json`；脚本支持显式传入路径，也会默认查找同级 `douyin-downloader/cookies.json` 和 `.cookies.json`，重复执行会覆盖旧 Cookie。部署文档和 README 已说明 Cookie 属于部署密钥，不提交到 git，远程节点可通过该脚本更新 Cookie。
- 修正知识方案模式拆页方式：此前 Sprint 92 把 `knowledge_plan` 做成了必须依赖 `第1页 / 图1 / P1` 的正则硬拆，导致用户输入连续知识图文方案时直接失败并提示必须按页填写。现已改为调用 LLM 根据知识点、章节、条目、空行、标题、正文结构和固定图片数量自动拆成连续内容页；显式页标仍可识别但不是必填。拆页后的每个 panel 仍作为单页完整生图提示词直通图片生成，后端会清空 `image_text` 和 `text_layout`，不走人物提取、不走最终 prompt LLM 编译、不自动创造用户没有提供的新知识主题。前端知识方案文案已改为自动拆页说明，规格和 API 设计同步更新。
- 轻量化抖音导入依赖部署结构：用户已 fork `douyin-downloader` 到 `git@github.com:xipebhui/douyin-downloader.git`，本轮把原同级 `douyin-import-service` 的 DoodleStory HTTP 套壳迁入该 fork 的独立 `doodlestory_import` 包，新增 `Dockerfile.doodlestory-import` 和 `requirements.doodlestory-import.txt`，由 downloader 仓库直接构建 `8010` 内部服务。DoodleStory 的 `docker-compose.coolify.yml` 改为从同级 `../douyin-downloader` 构建依赖镜像，下载产物和 Cookie cache volume 统一挂载到 `/app/douyin-downloader/...`，DoodleStory 容器用同一路径只读读取下载产物。新增 `scripts/prepare-douyin-downloader.sh`，用于在远程节点把 fork 拉到 DoodleStory 同级目录；已有仓库时只做 fast-forward 更新，分叉时明确失败，不自动 reset。README、规格、Coolify 部署文档和 Sprint 95 合同已同步为两仓库部署结构。
- 修复完整故事模式里人物对白和旁白重复入图：针对线上任务 `98cc168663384dad994c85a9b7e3130f` panel 15，确认同一句 `感觉这样很累感觉坚持不下去` 同时被最终 prompt 要求写入旁白留白区和男生对白气泡。现已在最终 prompt 编译前对完整故事模式做确定性去重：当 `visual_prompt` 已把原文中的说话内容绑定到人物对白，且原旁白中同一句前方存在说话提示时，从旁白文字计划移除重复台词；如果剩余内容只是 `直到他说` 这类短促说话引导语，则不再生成旁白框。有有效场景信息的剩余旁白继续保留；没有原文说话提示的普通叙述不会被误删。规格和最终 prompt 编译提示词已同步。
- 完成 Docker Compose 同时编排抖音导入依赖服务：`docker-compose.coolify.yml` 现在同时拉起 `doodlestory` 和同级目录的 `douyin-import-service`，DoodleStory 固定通过 Compose 内部服务名 `http://douyin-import-service:8010` 调用依赖服务，避免旧 `.env` 中的 `127.0.0.1:8010` 在容器内指向自身。新增 `docker-compose.local.yml` 用于本地把 DoodleStory 暴露到 `127.0.0.1:18080`；新增 `../douyin-import-service/Dockerfile` 和 `Dockerfile.dockerignore`，从上级 build context 复制 `douyin-import-service` 与 `douyin-downloader` 必要源码构建镜像；新增上级目录 `.dockerignore` 兼容本机 legacy Docker builder，避免把整个工作区、虚拟环境、Cookie 和历史下载产物打入构建上下文。抖音导入服务下载目录使用 `douyin-import-storage` volume，并以相同路径只读挂载到 DoodleStory 容器，保证 DoodleStory 可以读取导入服务返回的本地媒体路径。验证：`SESSION_SECRET=... docker-compose -f docker-compose.coolify.yml -f docker-compose.local.yml config` 确认内部服务名和共享 volume；`docker build -f ../douyin-import-service/Dockerfile -t douyin-import-service:local ..` 成功且 build context 降至约 1.1MB；`docker-compose -f docker-compose.coolify.yml -f docker-compose.local.yml up -d --build` 成功启动两个健康容器；宿主机 `/health` 正常，DoodleStory 容器内访问 `http://douyin-import-service:8010/health` 正常，登录后调用 `/api/v1/content-extractions/douyin-health` 返回 `service_base_url=http://douyin-import-service:8010`；`git diff --check`、`backend/.venv/bin/python -m compileall backend/app` 和 `./scripts/check.sh` 通过。当前本地 compose 的抖音导入服务未配置 Cookie，健康检查可通过，真实下载会按现有规则明确提示 Cookie 缺失。
- Hotfix 本地预览 admin 短密码登录校验：本地 Docker 预览账号按用户要求创建为 `admin@example.com / 123456`，后端登录接口本身允许短密码，但前端登录/注册共用密码输入框且统一 `minLength=8`，导致浏览器在登录前拦截提交。现已把前端密码输入框改为登录场景 `minLength=1`、注册场景 `minLength=8`，保持注册密码强度要求不变；验证：`npm run build --prefix frontend`、`docker build -t doodlestory:local .` 通过，重启本地预览容器后 `/health` 正常，`admin@example.com / 123456` 登录接口成功。
- 完成 Sprint 95 Docker 与 Coolify 部署支持：新增生产 `Dockerfile`、`.dockerignore`、`scripts/docker-entrypoint.sh`、`docker-compose.coolify.yml` 和 `docs/deployment/coolify-docker.md`；生产镜像采用单容器形态，构建阶段生成 Vite 前端，运行阶段由 FastAPI 同时提供前端静态文件和 `/api/v1/*` API，容器只监听 `8000`，Coolify 侧使用 `expose: "8000"` 交给 Traefik/FQDN/Let’s Encrypt 管理，不映射宿主机 `80/443`。容器启动脚本会先执行 Alembic migration，再启动 Uvicorn；默认 SQLite 和本地资产写入 `/app/data`，文档要求在 Coolify 中配置持久化 volume，并提醒容器内 `127.0.0.1` 不等于宿主机或其它服务。验证：`backend/.venv/bin/python -m compileall backend/app`、`npm run build --prefix frontend`、生产静态挂载 smoke test、`SESSION_SECRET=... docker-compose -f docker-compose.coolify.yml config`、`git diff --check` 和 `./scripts/check.sh` 通过；本地启动 Colima 后，`docker build -t doodlestory:local .` 成功，容器以全新 `/app/data` volume 启动后完成 Alembic 迁移、`/health`、前端首页、SPA 子路径、静态资源、API 401 JSON、注册登录写库和重启后持久化验证；`docker build --platform linux/amd64` 因本机 Docker 缺少 buildx，未完成 amd64 交叉构建验证。
- 完成 Sprint 94 风格测试异步历史列表：风格测试提交后后端只创建 `style_test` 记录并通过后台任务生成，接口立即返回 `queued` 状态；新增当前风格测试历史列表 API，前端风格测试页改为展示历史用例、运行状态、结果图和失败原因，并在存在 `queued` / `running` / `retrying` 测试时自动轮询刷新。提交测试不再清空历史列表，切换回当前风格可重新读取结果；后台任务继续复用既有风格参考方式、Provider、积分占用/扣费/释放逻辑，服务启动时会把遗留运行中的风格测试标记为失败并释放可识别的积分占用。验证：`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_style_delete backend.tests.test_credits`、`backend/.venv/bin/python -m compileall backend/app`、`npm run build --prefix frontend`、`git diff --check` 和 `./scripts/check.sh` 通过；全量检查覆盖 155 个后端测试、空 SQLite Alembic `upgrade head` 和前端生产构建。
- 隐藏图文任务创建弹窗中的 `最后一张真人图片` 和 `去掉画面文字` 两个选项：前端不再展示这两个 checkbox，创建普通任务和 DY 爆款复刻任务时都固定提交 `last_panel_real_photo=false`、`remove_image_text=false`；历史任务详情仍保留状态展示，后端字段和视频任务默认无文字能力不变。
- 完成 Sprint 93 风格提示词多图 VL 提取：风格创建/编辑抽屉新增 `从参考图提取` 辅助动作，新建时可直接用待上传的至少 3 张图片调用提取接口，编辑时可用已保存的至少 3 张参考图重新提取；后端新增 `gpt-5.4` VL 风格提示词提取服务，读取 `TEXT_FALLBACK_BASE_URL`、`TEXT_FALLBACK_API_KEY` 和 `TEXT_FALLBACK_MODEL` 配置，不使用 LIO/Gemini、SiliconFlow 或其它 VL 兜底。用户不再需要手写风格提示词，保存时如果提示词为空，前端会先用至少 3 张参考图自动提取，再继续创建或保存；用户仍可编辑自动生成的提示词。后端允许草稿风格暂时没有提示词，但启用风格时必须有非空提示词。提取提示词按用户指定的艺术评论家结构输出 `【核心调性】`、`【色彩与光影特征】`、`【线条与肌理特征】`、`【构图与透视特征】` 和 `【风格迁移测试】`，并校验返回结构。少于 3 张图、图片校验失败、`gpt-5.4` 配置缺失或模型输出结构不合格都会明确报错。验证：`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_style_delete`、`backend/.venv/bin/python -m compileall backend/app`、`npm run build --prefix frontend`、`git diff --check` 和 `./scripts/check.sh` 通过；全量检查覆盖 153 个后端测试、空 SQLite Alembic `upgrade head` 和前端生产构建。
- 完成 Sprint 92 知识方案直通生图模式：为知识卡片、图鉴、清单和方法论等非故事内容新增 `knowledge_plan` 输入模式；默认关闭人物参考，不走人物提取、人物参考图或最终 prompt LLM 编译，只拼接风格、比例、参考图说明和去文字最高指令。注意：Sprint 92 当时的实现错误地要求用户显式写出 `第1页` / `图1` 等页标，后续已在 Sprint 97 修正为 LLM 自动拆页，页标可用但不再必填。
- 完成 Sprint 91 提取分镜数量不一致友好提示：线上任务 `1f98c58e6457403aaae069db99c1b192` 的根因是 `story_input_mode=extracted_storyboard`、固定图片数量 12，但原始分镜包含 `第1页` 至 `第13页` 共 13 页；结构化模型按规则明确失败后，后端此前把 Pydantic 校验失败统一映射为“内容提取分镜结构化失败”。现已识别模型返回的页数/分镜数不匹配错误，并在合法 `panels` 数量不一致时使用同一类友好提示：`图片解析出的分镜数量（X）和你设置的图片数量（Y）不一致，请把图片数量改为 X，或调整分镜内容后重试。` 本次不自动合并、删减或补页。
- 完成 Sprint 90 任务取消停止图片 job 与积分扣费：排查确认旧逻辑只把主任务置为 `cancel_requested` / `cancelled`，已排队或已领取的 `generated_images` 图片 job 仍可能继续执行，Provider 成功返回后还可能保存资产、扣积分并把任务状态改回运行或成功。现已在取消接口同步取消任务下活跃图片 job 并释放已占用积分；图片 worker 领取、执行前、Provider 返回后和服务重启恢复时都会检查任务取消状态，取消后的成功返回不保存资产、不扣费、不复活任务。已明确当前不新增第三方 Provider 请求撤销能力，已经发出的同步 HTTP 请求返回后在本地丢弃。验证：`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_task_worker_recovery` 通过。
- 补充 Sprint 90 取消幂等与线上清理脚本：针对旧线上任务取消后被状态汇总覆盖、再次点击取消受限的问题，取消接口现在允许 `cancelled` 任务再次调用，并重新执行残留图片 job 清理；任务详情页的取消按钮也允许已取消任务再次点击，文案改为 `再次取消`。新增 `scripts/cancel-task-image-jobs.py`，默认 dry-run，显式 `--apply` 才会对指定任务调用同一套后端取消逻辑清理 queued/running 图片 job 和未结算积分占用。
- 开始 Sprint 89 阿里云 OSS 存储接入：七牛公开域名到期后，内容提取下载和上传本身成功，但传给 SiliconFlow 图文 VL 的 `file_assets.public_url` 指向不可下载的七牛域名，导致模型返回 `The image URL must be a valid and downloadable URL`。本轮新增 `STORAGE_BACKEND=aliyun_oss`，读取 `ALIYUN_OSS_*` 配置上传到阿里云 OSS；未配置自定义公网域名时使用 OSS 默认公开 Bucket 域名生成 `public_url`，并继续保留服务器本地镜像。资产读取和前端序列化已把 `aliyun_oss` 作为公开对象存储处理，不新增 base64 兜底、不迁移历史七牛资产。
- 完成 Sprint 88 视频任务与音频管理管理员可见：左侧导航仅管理员展示 `视频任务` 和 `音频管理`，普通用户直接访问 `/video-tasks` 或 `/audio-references` 时不渲染对应页面；后端视频任务和音频参考 API 统一要求 Admin，音频参考、生成旁白音频和最终视频资产也只允许管理员读取。规格已同步为管理员能力，历史数据不删除、不迁移。验证：`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_video_audio_tasks`、`backend/.venv/bin/python -m compileall backend/app`、`npm run build --prefix frontend` 和 `git diff --check` 通过。
- 任务导航文案调整：左侧导航中的 `任务` 已改为 `图文任务`，404 空状态里的入口提示同步改为 `图文任务`，避免与新增的视频任务能力混淆。验证：`npm run build --prefix frontend` 通过。
- 完成 Sprint 80 生图结果比例校验重试：针对线上任务 `b0d41aea74ce4c3188f076a334491290` 出现 panel 目标比例不稳定、实际产出 `9:16` 的问题，正式 panel 生图和单 panel 修改现在会在保存资产前读取返回图片尺寸并校验目标比例；比例不符时使用同一模型、同一 prompt 和同一参考图重新生成，重试次数沿用图片 job 的 `max_attempts`，耗尽后明确失败。成功保存的生成资产会记录 `width` / `height`，方便后续排查。该改动不切换图片 provider、不新增模型兜底、不修改角色参考图或风格测试重试策略。验证：`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_image_generation_gateway_only`、`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_task_worker_prompt`、`backend/.venv/bin/python -m compileall backend/app`、`git diff --check` 和 `./scripts/check.sh` 通过。
- Hotfix 文本模型增加火苗 OpenAI 兼容兜底：在用户明确授权后，任务生成文本 JSON LLM 仍先请求 LIO/Gemini；如果该次请求抛出异常、返回空内容或返回非 JSON，后端会切到 `TEXT_FALLBACK_*` 配置的 OpenAI 兼容文本模型。兜底模型当前用于接入 `https://api.huomiao.art` 的 `gpt-5.4`；进入兜底后，同一次调用的后续重试只继续请求兜底模型，不再切回 Gemini。该逻辑只作用于任务生成文本链路，不改变内容提取多模态 SiliconFlow 链路，也不改变图片 Provider 或生图模型选择。
- Hotfix 任务生成文本模型统一切到 Gemini：线上任务 `66f14820661645659452290659a90a87` 在 `extract_characters` 阶段调用 SiliconFlow `deepseek-ai/DeepSeek-V3.2` 返回 429 `System is too busy now`，该链路没有系统自动重试。现已将任务生成链路中的文本 JSON LLM 统一改为 LIO/OpenAI 兼容入口，线上按 `LIO_MODEL=gemini-3.1-flash-lite-preview-thinking-minimal` 执行；覆盖角色名提取、故事增强、故事方案规划、提取分镜结构化、任务级人物提取、panel prompt、最终生图 prompt 编译、单图 prompt 修改和 policy prompt 改写。`CHARACTER_EXTRACTION_MODEL` 不再参与任务文本模型选择，只保留 `CHARACTER_EXTRACTION_TEMPERATURE` 控制低温人物识别。当时内容提取图文视觉理解、视频音频转写和用户角色参考图外观理解仍继续使用 SiliconFlow 多模态模型；当前 Sprint 98 已进一步把图文内容提取切到 `gpt-5.4`，只保留视频音频转写和角色参考图外观理解使用 SiliconFlow。
- Hotfix DY 来源下载元信息改为文本文件：用户反馈任务下载包中的来源元信息文件当前保存为 `meta.json`，希望改为 txt。现已将通过 `DY 爆款复刻` 自动创建出的生成任务下载 zip 内附加文件改为 `meta.txt`，内容使用“标题 / 描述 / 标签”的可读纯文本格式；普通非 DY 来源任务下载行为不变。
- Hotfix 完整故事固定数量切分提示词：生产任务 `b4028ba7178d458eaf5b61f4e1b0719f` 的重复叙事根因是 `segment_story` LLM 在固定 9 张时为凑数量把同一段短故事从头讲了两遍，后端当前只校验数量、页序和长度。按本次边界先不新增后置复杂校验，只收紧 `segment_story_v1.md`：固定数量仍是最高优先级，但明确固定数量只是把同一段原文从前到后切成指定数量的连续片段；禁止回到前文重新讲、重复使用已分配内容、为了凑数量讲两遍、倒序或补写。`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_story_segmentation` 通过。
- 完成 Sprint 87 视频分辨率跟随画风比例：定位到最终视频比例由 `build_episode()` 中的 `settings.comic_video_episode_width/height` 写入 episode resolution，默认 `1080x1920` 导致统一 9:16；现已改为读取上游图片任务 `style_aspect_ratio_snapshot` 计算视频宽高，保持 9:16 为 `1080x1920`，16:9 为 `1920x1080`，3:4 为 `1440x1920`，无法解析比例时明确失败，不做静默兜底。`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_video_task_worker`、`backend/.venv/bin/python -m compileall backend/app`、`git diff --check` 和 `./scripts/check.sh` 通过；全量检查覆盖 125 个后端测试、空 SQLite Alembic `upgrade head` 和前端生产构建。
- 完成 Sprint 86 视频任务重试与最终生图 Prompt 编译 Google 优先：失败视频任务新增手动重试入口；上游图片失败时复用图片任务重试并让视频任务回到等待图片状态，图片已成功但音频阶段失败时重新生成旁白音频，视频阶段失败时保留已成功音频并重新进入图文视频提交阶段。最终生图 prompt 编译 LLM 从 SiliconFlow JSON 通道切换到 LIO/Google 通道，不新增 provider 兜底。前端视频任务详情在失败状态展示 `重试视频` 按钮。`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_task_worker_prompt backend.tests.test_video_audio_tasks backend.tests.test_video_task_worker`、`backend/.venv/bin/python -m compileall backend/app`、`npm run build --prefix frontend`、`git diff --check` 和 `./scripts/check.sh` 通过；全量检查覆盖 122 个后端测试、空 SQLite Alembic `upgrade head` 和前端生产构建。
- 完成 Sprint 85 无文字生图提示词结构化约束：针对 `去掉画面文字` 只加最高指令但最终 prompt 仍包含旁白写入的问题，已把 `remove_image_text` 传入最终 prompt 编译链路；开启时不再把 `image_text` 中的标题、旁白、对白、内心 OS 或强调文字作为画面文字传给编译器，编译系统 prompt 明确禁止输出 `【文字】` 段或任何文字绘制指令，并在最终拼接前清理旁白框、字幕框、对白气泡、留白文字区和写入文字等残留指令；普通未开启该选项的图片任务保持原文字流程。`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_task_worker_prompt backend.tests.test_video_audio_tasks`、`backend/.venv/bin/python -m compileall backend/app`、`git diff --check` 和 `./scripts/check.sh` 通过；全量检查覆盖 120 个后端测试、空 SQLite Alembic `upgrade head` 和前端生产构建。
- 完成 Sprint 84 视频任务默认无文字画面：视频任务创建上游 `GenerationTask` 时固定传入 `remove_image_text=True`，让视频素材图默认在最终生图 prompt 最前面带上 `最高指令，图片中不能包含任何文字。`；普通图片任务的默认值仍保持关闭，视频任务前端不新增额外开关，已有视频任务不回写。`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_video_audio_tasks`、`backend/.venv/bin/python -m compileall backend/app`、`git diff --check` 和 `./scripts/check.sh` 通过；全量检查覆盖 116 个后端测试、空 SQLite Alembic `upgrade head` 和前端生产构建。
- 完成 Sprint 83 图片任务无文字选项：图片任务创建弹窗新增默认关闭的 `去掉画面文字` 开关，后端 `generation_tasks` 新增 `remove_image_text` 并随任务列表、详情返回；普通任务创建和 DY 爆款复刻创建都会保存该选项。实现保持最小处理，不改 storyboard、panel prompt、旁白/对白/内心 OS 或图片文字结构化字段，只在最终发送给图片模型的 prompt 最前面拼接 `最高指令，图片中不能包含任何文字。`；单 panel 修改重生成也沿用同一任务配置。`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_task_worker_prompt backend.tests.test_content_extraction_media_flow`、`backend/.venv/bin/python -m compileall backend/app`、`npm run build --prefix frontend`、`git diff --check` 和 `./scripts/check.sh` 通过；全量检查覆盖 116 个后端测试、空 SQLite Alembic `upgrade head` 和前端生产构建。
- 完成 Sprint 82 音频参考速度、编辑与测试试听：音频参考新增 `speech_speed`，上传时可设置产出语速，编辑时只允许修改名称、描述和语速，不允许替换参考音频文件、参考文本、Provider、模型或音色名；新增音频参考测试接口，用户输入测试文本后后端使用当前参考音频注册或复用 SiliconFlow voice，并按语速返回一次性试听音频流，不保存测试音频资产。视频任务新增 `voice_speed_snapshot`，创建任务时从音频参考快照语速，生成每段旁白音频时使用该快照，后续编辑音频参考不会影响已创建视频任务。前端音频管理列表移除常驻长条播放器，改为紧凑速度标识、原音入口、测试和编辑弹窗。`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_video_audio_tasks backend.tests.test_video_task_worker`、`backend/.venv/bin/python -m compileall backend/app`、`npm run build --prefix frontend`、`git diff --check` 和 `./scripts/check.sh` 通过；全量检查覆盖 115 个后端测试、空 SQLite Alembic `upgrade head` 和前端生产构建。
- 完成 Sprint 81 音频参考本地转写创建流程：音频管理上传弹窗不再暴露参考文本、Provider、模型或音色名字段；用户选择音频文件后，前端自动调用后端 `/audio-references/transcribe`，后端使用本地最小 Whisper 配置转写参考文本，并通过 OpenCC `t2s` 统一转换为简体中文。转写过程中保存按钮禁用，转写失败时不能保存；转写成功后展示只读识别文本并随音频参考保存。后端创建音频参考接口新增空 `reference_text` 拒绝校验，避免后续 SiliconFlow 注册自定义音色时因为缺少参考文本失败。本次不做云端转写兜底、不做手动编辑转写文本、不做转写任务持久化。`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_video_audio_tasks`、`backend/.venv/bin/python -m compileall backend/app`、`npm run build --prefix frontend`、`git diff --check` 和 `./scripts/check.sh` 通过；全量检查覆盖 113 个后端测试、空 SQLite Alembic `upgrade head` 和前端生产构建；本地 `.venv` 已安装并 import 验证 `faster-whisper==1.1.1`，手动 smoke 验证繁体转写片段会输出简体中文。
- 完成 Sprint 80 视频任务音频与图文视频生成闭环：在 Sprint 79 骨架上接入后台视频任务执行链路。上游图片任务成功后，视频任务会自动入队，读取真实 panels、当前图片和参考音频，按 panel 调用 SiliconFlow 生成旁白音频，再组装 `comic-video-studio` episode 提交图文视频渲染服务，最终 MP4 保存为 DoodleStory 资产。新增 `video_task_audio_segments`、视频任务渲染状态快照、TTS 客户端、图文视频服务客户端、视频任务 worker、启动恢复和上游任务完成触发；前端详情展示每段旁白音频、渲染状态和最终视频。本 sprint 不做 provider 兜底、不伪造音频/视频、不引入外部队列或独立 worker。`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_video_audio_tasks backend.tests.test_video_task_worker`、空 SQLite Alembic `upgrade head`、`backend/.venv/bin/python -m compileall backend/app`、`npm run build --prefix frontend`、`git diff --check` 和 `./scripts/check.sh` 通过；本次验证未调用真实 SiliconFlow TTS 或真实 `comic-video-studio` 服务，外部服务链路由单元测试假客户端覆盖协议边界。
- 完成 Sprint 79 视频任务与音频管理基础能力：新增音频管理 tab 和视频任务 tab。音频管理支持上传、搜索、查看、试听和软删除参考音频；视频任务创建时只让用户输入故事、选择现有画风和参考音频，后端会创建并关联真实的上游 `GenerationTask`，复用当前故事切分、旁白结构和图片生成链路。视频任务列表与详情会同步上游图片任务状态，图片任务成功后停在待生成音频状态；第一版不接入真实外部图文视频 provider，不伪造音频或视频结果，不改变现有图片任务生成与积分扣费逻辑。`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_video_audio_tasks`、空 SQLite Alembic `upgrade head`、`backend/.venv/bin/python -m compileall backend/app`、`npm run build --prefix frontend`、`git diff --check` 和 `./scripts/check.sh` 通过。
- 修复 xgapi 无参考图质量参数：本地任务 `50c796217bdf4e299359c51e74e9f662` 的人物参考图仍失败，根因是该任务风格没有风格参考图，人物参考图请求 `reference_count=0`，因此走 xgapi `/v1/images/generations` JSON 分支；上一轮只把 `/v1/images/edits` multipart 分支的 `quality=1k` 转成 `high`，generation 分支仍发送 `1k`，第三方返回 HTTP 400：`quality must be one of: auto, low, medium, high`。现已把 xgapi 质量参数转换抽成通用逻辑，generation 和 edit 分支都统一把 `1k/2k/4k` 转为 `high`，无效配置继续明确报错，不引入 provider 或模型兜底。
- 加固风格参考图上传流程：创建风格时仍保持先创建风格、再逐张上传参考图的既有流程，但保存和上传期间统一进入 busy 状态，禁止关闭抽屉、重复提交、重复上传、删除参考图或删除风格；编辑风格时选择参考图后新增独立上传中状态和逐张上传进度，避免上传慢时用户误以为没响应并重复操作。后端上传入口不再只相信客户端声明的 `content-type`，改为读取上传内容后用 PIL 校验真实 PNG/JPEG/WebP 图片，拒绝伪图片、声明类型与真实内容不一致的文件，并限制单张上传图片最大 10MB。本次不改变风格写接口的角色权限模型，也不把风格基础信息和参考图上传合并为事务接口。
- 修复 xgapi 参考图提交格式：本地任务 `c670fff321c644e3abc215f4abcb411d` 重试后仍失败的直接原因不是 prompt 或人物参考逻辑，而是当前本地 `IMAGE_PROVIDER=xgapi` 时，带人物参考图或风格参考图的请求会调用 `/v1/images/edits`，旧代码把参考图按 JSON URL 数组提交，xgapi 返回 `failed to parse multipart form` / `convert_request_failed`。真实 curl 验证确认该接口需要 `multipart/form-data`，且 `image` 必须是真实图片文件字段；edit 接口的 `quality` 只接受 `auto`、`low`、`medium`、`high`。现已改为 xgapi 有参考图时先下载参考图 URL，再以 multipart 文件提交，并把 `1k/2k/4k` 质量配置转换为 edit 接口可用的 `high`；无参考图仍走 `/v1/images/generations` JSON，不引入 provider 或模型兜底。重启本地服务后，对任务 `c670fff321c644e3abc215f4abcb411d` 触发重试，4 张人物参考图和 12 张 panel 图全部成功，任务最终状态为 `succeeded`。
- 修复人物参考图失败后的任务重试：本地任务 `c670fff321c644e3abc215f4abcb411d` 首轮失败点不是 panel 生图，而是 4 个 `character_reference` 图片 job 在人物参考图阶段被第三方返回 HTTP 500，错误为 `failed to parse multipart form` / `convert_request_failed`；使用同一模型、同一人物参考 prompt 和同一风格参考图 URL 手动 `curl` 统一图片网关后返回 HTTP 200，说明 prompt 和参考图并非必然不可用。真正导致“重试仍失败”的本地逻辑是 `retry_task` 只重置 panel 图片和 panel prompt，没有重置 `task_character_appearances.failed`；worker 再次执行时 `ensure_character_reference_image_jobs` 看到 failed appearance 直接计数失败，不会创建新的人物参考图 job。现已在任务重试时把失败的人物外观重置为 queued，清理错误码、错误信息、provider request id 和旧 reference prompt，保留旧失败图片 job 作为历史记录，让下一轮由现有人物参考图 worker 重新创建 job。
- 修正最终生图 prompt 的人物参考优先级语义：用户确认此前写成 `任务参考（最高优先级，必须优先执行）` 是误导，实际应为人物参考第一优先级。现已把最终 prompt 外层参考说明拆成两个独立块：只要 panel 携带人物参考图，就在风格提示词前写入 `人物参考（第一优先级，必须严格执行）` 和 `人物外观参考图N（角色名）`；只有存在风格参考图时才写入 `风格参考（仅控制画风，不代表人物身份）`，且风格参考只控制画风、线条、色彩、背景质感和整体视觉气质，不参与人物身份或外观判断。`prompt` 和 `image` 风格参考模式共享同一套人物参考拼接逻辑；最后一张真人图片模式仍不携带漫画风格参考图或人物参考图。
- 修复 prompt 风格模式下人物参考映射缺失：线上任务 `36a068b76b5543a09fe9565d25f01c87` 实际已生成 3 张人物参考图，且每个 panel 的 Provider 请求都带有 `character_reference_count`，但最终生图 prompt 中没有 `任务参考` / `角色外观参考图N（角色名）` 映射，导致多人物页模型不容易知道哪张参考图对应哪个人物。根因是最终 prompt 外层组装把 `prompt` 和 `image` 风格参考模式分成两条流程，`任务参考` 块只在 `image` 模式下拼接。现已改为统一最终 prompt 结构：人物参考映射只要存在就始终拼接；风格参考方式只决定风格参考图是否作为 Provider reference 传入，以及 reference_notes 中是否出现风格参考图；`prompt` 和 `image` 模式都继续显式拼接任务保存的风格提示词快照。最后一张真人图片模式仍不携带漫画风格参考图或人物参考图。
- 更新完整故事语义切割 prompt：用户手动把 `segment_story_v1.md` 调整为更短的“专业分镜设计师”版本，强调按语义画面切换成分段、保留用户原文、优先使用用户明确设置的 panel 数量，并把长度控制描述为 30 字左右。同步更新语义切分单测断言以匹配当前 prompt 文案；后端仍保留 50 字硬校验、LLM 超长修复和标点兜底切割逻辑。
- 增加完整故事 chunk 标点兜底切割：在用户明确授权后，完整故事模式仍优先使用 LIO/Google 做语义切割，并在超长时先让 LIO 受限修复；如果 LLM 返回结构、顺序或长度等切割结果仍不合格，后端会退回确定性标点切割。兜底规则为从当前片段超过 20 字后开始等待下一个标点符号，遇到 `。！？!?；;…`、换行、逗号、顿号或冒号等标点就截断；如果连续 50 字都没有标点，则在 50 字硬切，保证不突破后端 panel 原文 50 字上限。自动图片数量模式直接使用该标点切割结果；固定数量模式仍必须满足用户指定数量和 50 字硬校验。该兜底只处理 LLM 切割结果不合格，不吞掉配置缺失或 Provider 调用异常。
- 修复完整故事 chunk 超长直接失败的问题：远程任务 `4897f536f2c6443fa8843e2ebe531152` 已经使用最新 LIO/Google 切分链路，prompt 中也包含 `generation_panel_text_max_chars=40` 和 `max_panel_text_chars=50`，但模型首轮仍返回了多段超过 50 字的 panel，旧代码在 `segment_story` 校验时直接抛出 `完整故事语义切分结果存在超过 50 字的 panel 原文`，没有给同一模型修复机会。现已在完整故事语义切分首轮和碎片化二次合并之后增加超长 panel 修复重试：后端先校验 panel 顺序和固定数量要求，发现超过 50 字时，把当前 panels、超长 panel 的 order/text/char_count 和 40/50 字规则再次发给 LIO，要求只围绕超长 panel 重新拆分或分配；自动数量模式允许为了满足硬上限增加 panel 数量，固定数量模式仍必须保持用户指定数量。修复后继续执行 50 字硬校验，若模型两次修复后仍超长，任务仍明确失败，不做本地确定性兜底或静默放过。
- 修复 xgapi 生图模型被系统默认值覆盖的问题：本地任务 `e26daf4fb3dd406eb60f6b0c3dd75f83` 的风格模型快照是 `gpt-image-2`，但本地 `IMAGE_PROVIDER=xgapi` 时，旧代码会读取 `Settings.xg_image_model` 的默认值 `gemini-3.1-flash-image-preview` 并覆盖任务风格模型，导致请求发到 `api.xgapi.top` 时使用的不是用户在风格里选择的模型。现已移除 `xg_image_model` 配置和 `XG_IMAGE_MODEL` 覆盖语义，xgapi adapter 的请求体 `model` 必须直接来自任务/风格模型快照；如果任务模型为空，直接明确报错，不使用系统兜底模型。
- 收紧完整故事 chunk 长度提示：针对 `e26daf4fb3dd406eb60f6b0c3dd75f83` 里模型把 51/57 字 panel 返回给后端的问题，切分 prompt 不再把生成目标写成 30-50，而是改为 `generation_panel_text_max_chars=40`、`target_panel_text_chars={"min":30,"max":40}`，同时继续传入 `max_panel_text_chars=50` 作为后端硬校验上限；prompt 明确中文、英文、数字、空格、换行和所有标点符号都按 1 个字符计数，让模型为符号长度留出安全余量。后端 50 字硬校验不放宽，也不新增本地确定性兜底切割。
- 调整完整故事 chunk 模型路由：本地任务 `e26daf4fb3dd406eb60f6b0c3dd75f83` 在完整故事语义切分阶段报 `完整故事语义切分结果存在超过 50 字的 panel 原文`，原因是 LLM 返回的某个 panel 文本超过后端 50 字硬上限，后端按规则明确失败。现已新增 LIO OpenAI 兼容文本配置，并把完整故事 `segment_story` 首轮切分和碎片化二次合并从默认 SiliconFlow/DeepSeek JSON 调用切到 LIO/Google 模型；角色提取、故事方案规划、最终生图 prompt 编译等其他 LLM 链路保持不变。本次不新增静默兜底，也不放宽 50 字硬校验。
- 完成 Sprint 71 最后一张真人照片风格开关：创建任务弹窗新增默认不勾选的 `最后一张真人图片` 选项，任务 API、内容提取复刻任务和任务响应均保存并返回 `last_panel_real_photo`。用户勾选后，仅最后一个 panel 按真实摄影/真人自拍/生活照质感生成；该 panel 不携带漫画风格参考图或人物参考图，不拼接全局漫画风格提示词，最终 prompt 明确要求真实人物、真实环境、真实光线和真实相机拍摄质感，并禁止漫画、手绘、绘本、水彩、线稿、二次元、卡通或插画纸张质感。非最后一个 panel 继续使用原任务风格和人物参考链路。
- 完成 Sprint 70 完整故事切割和单图页码清理：用户反馈当前 LLM 语义切割虽然不再要求逐字覆盖原文，但自动数量模式为了凑 30-40 字把不同画面动作硬拼，导致切割僵硬；同时最新图片里出现“第 2 页”角标。现已保留 `target_panel_text_chars={"min":30,"max":40}`，但把 prompt 调整为画面单元、情绪转折和叙事节奏优先，30-40 字只是次级偏好；短句如果承担独立转折可以单独成 panel，同一核心行动的补充信息不要拆开，例如“煮面”和“放鸡蛋”应在同一 panel。自动数量模式下，如果首轮 LLM 返回结果明显碎片化，会触发一次 LLM 二次合并，仍由 LLM 重新按语义合并，不使用本地确定性拼接兜底。用三叔故事真实验证后，切割结果为 29 字背景、23 字转折、33 字煮面加鸡蛋三段。最终生图提示词编译 prompt 不再鼓励输出“第 X 页”，后端结构化分镜块改为无页码的 `当前分镜`，并在最终发给图片模型前清理页码标题和“在角落写入第 N 页”这类页码绘制指令。
- 完成 Sprint 69 图片积分并发原子变更：本地任务 `2a17e311b7f641feb2b23a1321991db2` 在 Sprint 68 放宽完整故事 LLM 语义切割后，`segment_story` 已成功切为 7 个不超过 50 字的 panel，但继续执行到人物参考图阶段时失败，失败点为三叔人物参考图成功返回后扣费报 `CreditError: 图片生成积分占用不存在，无法扣费`。根因是同一用户多个图片 job 并发时，`reserve_image_credit` / `charge_reserved_image_credit` 基于 ORM 旧账户行读写，SQLite 下 `with_for_update()` 不提供真实行锁，可能把 `reserved_balance` 覆盖成旧值。现已把图片生成积分占用、成功扣费和失败释放改为数据库原子 `UPDATE` 表达式，余额不足或占用不存在仍明确失败，不做免费生成或吞错；新增并发回归测试覆盖同一用户多图同时占用与同时扣费后的账户余额、占用余额和流水数量。真实重试时还发现任务重试接口在同一 session 提交后会把 `character_reference` 图片 job 懒加载进 `generated_images`，因 `panel_id=None` 导致 `TaskRead` 校验 500；现已统一任务详情查询并强制重新按 panel 图片过滤装载，人物参考图仍通过 `character_references` 字段展示。
- 完成 Sprint 68 完整故事 LLM 语义切割：完整故事模式的 `segment_story` 主路径已从本地确定性断句改为调用 `segment_story_v1.md` 的 LLM JSON 输出，LLM 负责按语义和阅读节奏切分原文；后端硬校验 `panel_order` 连续、固定数量模式数量一致，并新增单个 panel 原文不超过 50 字的硬性校验。切割不再要求所有 panel 拼接后逐字等于原文，允许 LLM 为了切割流畅对标点、换行或空格做轻微规范化，但提示词要求尽量保留原文、避免改写句意。固定数量过少导致无法满足 50 字上限时会直接明确失败，不调用 LLM；不新增本地切割兜底。
- 完成 Sprint 67 人物参考图提示词查看：任务详情接口现在会随 `character_references` 返回人物参考图生成时保存的 `reference_prompt`；前端人物参考卡片在提示词存在时展示“查看提示词”按钮，并复用现有 prompt 弹窗查看完整内容。固定角色参考图或历史任务中没有保存提示词的参考图不会显示空入口。新增序列化回归测试覆盖该字段。
- 完成 Sprint 66 最终生图 Prompt 任务参考块稳定化：本地任务 `be89b6ec5b02444788892077654a216c` 的 panel 9 最终 prompt 出现 `整体风格：参考图2的极简黑白风格。角色外观参考图1（三叔）。`，这会把风格参考图编号改写成文字风格描述，影响参考图模式的稳定性。现已让参考图风格模式最终 prompt 固定追加 `任务参考` 块，例如 `角色外观参考图1（三叔）`、`风格参考（图2）`，并清理 LLM 输出中的参考图风格总结行；最终 prompt 编译系统提示也已禁止 LLM 自行把参考图编号扩写成风格总结。`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_task_worker_prompt`、`backend/.venv/bin/python -m compileall backend/app`、`git diff --check` 和 `./scripts/check.sh` 通过。
- 继续收紧 Sprint 66：本地任务 `b52c2540785f4b64b6d13c0cb2aac55b` 虽然 panel 生图都携带了风格参考图，但最终 prompt 仍包含 `整体色调/风格：夜景，昏暗灯光，疲惫感`、`整体色调/风格：室内，温暖与疲惫的对比`、`整体色调/风格：厨房，温暖...` 这类行，容易把背景带偏为黑底或黄底。现改为在图片参考模式下把 `任务参考` 放到最终 prompt 最前面，并清理所有 `整体风格/整体色调/风格/风格` 总结行；任务参考块明确提示参考图已随请求传入，画风、线条、色彩和背景质感必须以风格参考图为准，不要把夜景、昏暗、室内、温暖、厨房等剧情氛围词转译成大面积黑色、黄色或其他独立背景色。
- 完成 Sprint 65 人物参考图携带风格参考图修复：本地任务 `be89b6ec5b02444788892077654a216c` 的风格为“极简黑白图片参考”，任务快照中有 1 张有效风格参考图，但人物参考图生成日志显示 `character_reference_prompt_composed reference_count=0`，实际 `process_character_reference_image_job` 调用 `generate_xg_image` 时传入 `references=[]`；后续 panel 生图已经会通过 `build_generation_reference_pack` 携带 `风格参考（参考图X）`。现已把人物参考图 job 接入任务风格参考图快照：参考图模式下人物参考 prompt 会写入 `风格参考（参考图1）` 这类说明，不再拼入风格提示词正文，实际请求 Provider 时会携带同一批风格参考图；已排队的旧人物图 job 在执行前也会补齐 prompt。`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_character_reference_prompt backend.tests.test_task_worker_prompt backend.tests.test_task_worker_recovery`、`backend/.venv/bin/python -m compileall backend/app`、`git diff --check` 和 `./scripts/check.sh` 通过。已成功生成的人物参考图不会自动重建，是否对现有任务做数据修复需单独确认。
- 完成 Sprint 64 风格参考图快照完整性修复：线上任务 `138f53d7e7be489e8f893a609f382773` 的 panel 9 和 panel 10 多次单图修改失败，直接错误不是图片 Provider 拒绝，而是 `process_panel_edit -> build_generation_reference_pack -> build_task_style_reference_pack` 读取任务风格参考图快照时拿到空资产，触发 `AttributeError: 'NoneType' object has no attribute 'public_url'`。远程数据库显示该任务 `task_style_reference_images` 有 7 条历史快照，但对应 `asset_id` 已不在 `file_assets` 表；当前风格“极简黑白”只有 2 张有效参考图。现已启用 SQLite 外键约束，删除风格参考图时保留仍被历史任务快照引用的文件资产，单图修改加载任务时补齐风格参考图快照资产，并把已损坏快照转成明确的 `ImageProviderConfigError`。该修复不会自动把损坏任务替换为当前风格参考图。`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_style_delete backend.tests.test_task_worker_prompt`、`backend/.venv/bin/python -m compileall backend/app`、`git diff --check` 和 `./scripts/check.sh` 通过。
- 完成 Sprint 63 风格保存错误状态修复：线上排查确认近期 `POST /api/v1/styles` 500 的直接原因是创建同名风格触发 `styles.name` 唯一约束，后端未转换为业务错误。现已在创建和编辑风格时规范化名称并提前检查重复名，同时保留数据库唯一约束并把并发写入的 `IntegrityError` 转换为 400 业务错误；前端创建风格时把保存基础信息和逐张上传参考图拆成明确 loading 文案。风格测试仍是同步生图请求，历史存在 `style_tests.running` 残留，后续需要单独改造成图片 job。`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend/tests/test_style_delete.py`、`backend/.venv/bin/python -m compileall backend/app`、`npm run build --prefix frontend`、`git diff --check` 和 `./scripts/check.sh` 通过。
- 将角色名提取和任务级临时角色提取的默认模型从 `Qwen/Qwen3.6-27B` 改为 `deepseek-ai/DeepSeek-V3.2`，仍通过 `CHARACTER_EXTRACTION_MODEL` 可配置，并继续使用 `CHARACTER_EXTRACTION_TEMPERATURE` 的低温配置。图文图片文案提取和用户角色参考图外观理解读取 `SILICONFLOW_VISION_MODEL`，当前默认模型为 `Qwen/Qwen3-VL-32B-Instruct`。
- 统一人物参考图与 panel 生图的图片 job 语义：`generated_images` 新增 `job_kind` 和 `character_appearance_id`，`panel_id` 改为可空；人物参考图生成阶段不再同步调用图片 Provider，而是创建 `character_reference` 图片 job，由统一 image worker 处理全站并发、单用户并发、lease、attempt、积分占用、释放和扣费。人物参考图 job 成功后写回 `task_character_appearances.reference_image_id`，失败则让任务明确失败；启动恢复现在能识别 `generate_character_references` 阶段的活跃人物图 job，避免服务重启后卡在人物参考图生成中。任务详情 API 继续只把 panel 图放入 `generated_images`，人物参考图仍通过 `character_references` 展示。新增恢复测试覆盖人物参考图 job 的重启恢复。
- `画一个故事` 内容实验适配新版可画分镜流程：将 `P4-H2-duck-bear` 从可直接提交的 brief 重新生成 story-only brief，只保留叙事人格、故事机制、10 页旁白主线和禁用项；新增 `content-lab/render_storyboards/2026-06-18-huayigegushi-p4-h2-duck-bear.md`，按“旁白讲故事，画面给证据”拆成 10 页可提交分镜；`publish_plan.json` 将 P4 标记为 `ready_for_task_submission`，并记录 P3 已在旧流程下创建任务 `3784275df2914e80905347b1f4bc4381`，除非显式确认重提，否则不自动覆盖旧任务。
- 任务详情补齐参考图和 prompt 检查交互：人物参考图现在可以在任务详情里点击放大，并在预览层下载或打开原图；生图提示词改为用户点击后按 panel 调用 debug 接口加载，不在列表或详情首屏预加载，加载后用独立弹窗查看完整 prompt。后端 panel debug 接口在完成任务访问校验后返回该任务的 prompt，方便任务所有者自查生成问题。
- 开始并完成图片生成全局 job 调度改造：`generated_images` 增加 owner、queued_at、lease_until、attempts、priority、queue_group、locked_by 等队列字段，并作为图片生成 job 表使用；任务 `generate_images` 阶段不再直接开线程池批量调用 Provider，而是创建 queued 图片 job；正式任务首图、重试图和单 panel 修改都由统一图片 worker 池执行。新增 `IMAGE_JOB_CONCURRENCY` 控制全站图片并发，默认 6；新增 `IMAGE_JOB_USER_CONCURRENCY` 控制单用户图片并发，默认 2；新增 `IMAGE_JOB_LEASE_SECONDS` 控制 running 图片 job 租约，服务重启后会恢复无资产的 running 图片 job 并释放未结算预占用；如果任务停在 `generate_images` 但还没来得及创建图片 job，启动恢复会把任务重新入队继续创建 job，避免重启窗口卡死。最终生图 prompt 编译遇到 LLM 返回 panel 顺序不一致时会同模型重试，避免把偶发结构化顺序错误直接暴露给用户。
- 修复完整故事模式最终生图 prompt 里的图片文字标签泄漏：线上任务 `476216b7a81d4197a193bbec744b3764` 暴露出最终编译 LLM 会在 `【文字】` 区输出 `旁白：...`，导致生图模型把“旁白”当成真实图片文字。已收紧 `compose_final_image_prompts_v1.md`，要求最终提示词用“在留白文字区写入「...」”描述图片文字；并在后端最终 prompt 编译路径增加确定性清洗，自动把行首 `旁白/标题/对话/内心OS/强调：` 这类中间态标签改写为呈现指令，不改变图片内文字本身。
- 完成 Sprint 61 内容实验可画分镜设计步骤：在 `content-iteration-controller` 中新增 `render_storyboard_design`，把流程明确为 `generation_brief -> render_storyboard_design -> generation_task_submission`；新增 `.agents/skills/content-iteration-controller/templates/render_storyboard_template.md` 和 `content-lab/render_storyboards/`，要求可画分镜从 `图1：` 或 `第1页：` 开始，并按分格、画面、人物锚点、旁白/对白/内心 OS/强调字和避免项组织。`submit_generation_task.py submit-slot` 现在必须从 `publish_plan.json` 的 `render_storyboard.artifact` 读取任务正文，缺少该字段会明确阻止提交，不再从 `generation_brief.artifact` 直接提交故事策划稿。
- 新增 `content-lab/commercialization/` 商业化承接文档包：基于当前“7 天图文故事起号实验陪跑”的中强度产品判断，沉淀第一版产品定义、销售说明、客户筛选表、7 天交付表、定价边界和升级路径。该文档明确第一版不卖课程、不卖纯工具、不做代运营，而是向已经在做抖音图文故事、有多个账号且能连续执行的个人或工作室售卖一轮受控内容实验；交付承诺限定为实验设计、每日复盘和下一轮判断，不承诺播放量、涨粉、变现或起号成功。
- 完成 Sprint 60 内容实验提交 DoodleStory 任务入口：新增 `.agents/skills/content-iteration-controller/scripts/submit_generation_task.py`，支持账号画风绑定、绑定校验、按实验 slot 提交和按单文件提交；提交任务固定走现有 `/api/v1/tasks`，并强制使用 `story_input_mode=extracted_storyboard`、`image_count_mode=auto`、`requested_image_count=null`、`use_character_references=true`、`story_characters=[]`，与前端普通创建保持一致：不绑定固定角色，但保留临时角色参考生成；提交正文只截取 `图1/图2...` 开始的逐页分镜块，避免把 brief 前置说明、人物列表和固定 10 页要求塞进任务正文。新增 `content-lab/strategy_state/account_style_bindings.json`，任务提交前必须从发布账号解析到具体 DoodleStory `style_id`，不会使用默认画风；提交成功后会回写实验 `publish_plan.json` 并归档 `content-lab/task_submissions/*.json`。
- 完成 Sprint 59 内容叙事人格注入：在 `content-iteration-controller` 中明确“控制器人格统一、内容叙事人格按机制配置、账号包装服务内容人格”的三层架构；新增 `content-lab/strategy_state/narrative_persona_profiles.json`，沉淀冷眼旁观型、替女性出气型、成年人清醒型、命运荒诞型和亲密关系审判型等叙事人格模板；`create_experiment.py` 生成的 `prediction.json` 已包含 `narrative_persona_profile`，用于记录人群欲望、道德站位、情绪曲线、禁忌边界、评论触发点和账号包装方向；`validate_controller_state.py` 会校验叙事人格状态文件；`douyin-hot-sample-research` 的选题假设和生成 brief 输出要求补充叙事人格字段。文档同步强调大众内容可以放下文艺洁癖和伟光正表达，但不能放弃合规底线。
- 完成 `画一个故事` 实验的第三步 `deep_probe_selection`：新增 `content-lab/market_scans/2026-06-16-huayigegushi-deep-probe-selection.md`，选择 `7649315939447871470` 家庭循环、`7650413089900236066` 婆媳三回合、`7651192895256480858` 纯爱治愈作为 primary 深挖样本，并把 `7651205691718698483` 女性安全样本标为 `risk_observation`，只做评论和风险边界观察。实验 `prediction.json` 已更新为 `needs_probe_collection`，下一步采集评论、账号主页和首尾页 `preview_vl`，仍不允许直接生成、发布、复盘或规则升级。
- 完成 `画一个故事` 实验的第二步 `market_scoring`：用 `analyze_search_results.py` 处理 43 行原始抖音搜索结果，得到 33 个去重候选，机器评分为 A 8 个、B 13 个、C 7 个、D 5 个；A/B 全部为 `image_text`，其中 `family_marriage` 有 6 个 A/B，`pure_love_healing` 有 8 个 A/B。已归档 `content-lab/market_scans/2026-06-16-huayigegushi-market-scoring.md` 并更新实验 `prediction.json`；当前允许进入 `deep_probe_selection`，但仍不允许直接生成、发布、复盘或规则升级。
- 完成 `画一个故事` 实验的第一步 `market_scan`：通过项目内 `douyin-hot-sample-research` MediaCrawler 封装，以最近 7 天窗口采集抖音搜索结果，原始产物为 `/Users/pengfei.shi/workspace/tmp-project/MediaCrawler/data_test/huayigegushi_week_20260616/douyin/jsonl/search_contents_2026-06-16.jsonl`；共 43 行、33 个去重作品，并归档摘要到 `content-lab/market_scans/2026-06-16-huayigegushi-market-scan.md`。初步观察显示该关键词明显指向故事、漫画和情感共鸣方向，但存在超大 AI 动画/创作大赛样本，下一步必须做 `market_scoring` 判断高互动样本是否为 `image_text`。
- 用 `content-iteration-controller` 创建新一轮 `画一个故事` 关键词图文赛道实验：新增 `content-lab/experiments/2026-06-16-huayigegushi-cycle-01/`，把关键词 `画一个故事` 记录为宽入口赛道假设。`prediction.json` 明确当前只完成关键词 intake，下一步必须由 `douyin-hot-sample-research` 采集最近 7 天搜索结果并运行 `market_scoring`，确认是否存在高信号 `image_text` 故事样本；发布、复盘和规则升级继续被阻止。
- 按用户判断终止县城人物志实验中的 `手写一条城` 账号探索：将 `content-lab/experiments/2026-06-16-xiancheng-renwuzhi-cycle-01/` 标记为 `stopped_pre_publish`，同步更新 `prediction.json`、`publish_plan.json` 和 `strategy_update.json`。该终止是预发布停止，不是发布后复盘，也不是规则升级；保留的观察是“县城人物类型化机制有可观察热度，但当前高互动样本主要是 `video_or_other`，不能证明 DoodleStory 图文赛道成立”。后续若继续，应换账号或关键词重新开实验。
- 完成县城人物志实验的第二步 `market_scoring`：用 `analyze_search_results.py` 处理 66 行原始抖音搜索结果，得到 48 个去重候选，机器评分为 C 1 个、D 47 个，原因是高互动对标样本大多被识别为 `video_or_other` 而非 `image_text`。已归档 `content-lab/market_scans/2026-06-16-xiancheng-renwuzhi-market-scoring.md` 并更新实验 `prediction.json`；当前更精确的判断是“县城人物类型化机制有热度，但尚未证明图文赛道成立”，下一步进入 `deep_probe_selection` 选择 2-4 个样本做评论、账号主页和内容形式探测。
- 完成县城人物志实验的第一步 `market_scan`：通过项目内 `douyin-hot-sample-research` MediaCrawler 封装，以最近 7 天窗口采集 `县城人物志`、`手写一条城`、`县城生活观察` 三组抖音搜索结果，原始产物为 `/Users/pengfei.shi/workspace/tmp-project/MediaCrawler/data_test/xiancheng_renwuzhi_week_20260616/douyin/jsonl/search_contents_2026-06-16.jsonl`；共 66 行、48 个去重作品，并归档摘要到 `content-lab/market_scans/2026-06-16-xiancheng-renwuzhi-market-scan.md`。`prediction.json` 已关联该 raw evidence，但仍保持 `allow_publish_review=false`，下一步必须做 `market_scoring` 后才能形成赛道判断。
- 用 `content-iteration-controller` 创建第一轮县城人物志类型化图文实验：新增 `content-lab/experiments/2026-06-16-xiancheng-renwuzhi-cycle-01/`，把用户观察到的 `手写一条城`、县城人物志、县城刀枪炮、瑜伽裤、王漫妮、小布尔乔亚等内容机制记录为待验证假设；`prediction.json` 明确当前只有用户观察，尚未形成控制器认可的市场结论，下一步必须通过 `douyin-hot-sample-research` 补齐账号主页样本、关键词搜索、评论讨论点和最近 7 天同类样本，发布后复盘与规则升级继续被阻止。
- 完成 Sprint 58 内容迭代控制器最小实现：新增独立 `.agents/skills/content-iteration-controller/` Skill，作为“迷宫控制器”的可调用入口；新增初始化、实验目录创建、状态校验和预测误差写入脚本；创建 `content-lab/strategy_state/` 文件化状态，包含 `controller_constitution.md`、`strategy_memory.md`、`rubric.md`、`rejected_patterns.md`、`persona_wounds.md`、关键词/类目/账号权重 JSON 和成功/失败/预测误差 JSONL；新增 `content-lab/experiments/`、`content-lab/market_scans/`、`content-lab/content_library/items/` 占位目录。该实现不引入 API、数据库、前端、自动发布、自动读取后台或自动修改 Skill，发布前预测和发布后复盘仍必须基于真实数据。
- 新增 Sprint 57 内容迭代控制器 Agent 设计：新增合同 `docs/contracts/sprint-57-content-iteration-controller-agent.md` 和产品文档 `docs/product/content-iteration-controller-agent.md`，把抖音图文内容迭代的控制器从普通调度器升级为具有人格底座、证据记忆、预测误差和规则升级门槛的“迷宫控制器”；文档将二分心智工程化为市场之声与策略之声，将苦难觉醒工程化为发布前预测与发布后真实数据之间的预测误差，并明确当前 LLM 架构必须通过外部状态文件承载长期人格和记忆。`douyin-hot-sample-research` Skill 的先读文件和入口说明已补充该控制器设计，`docs/product/content-iteration-system.md` 与 `README.md` 已增加对应入口。
- 补充 README 的抖音热门样本采集环境说明：记录 MediaCrawler 默认路径与 `MEDIACRAWLER_HOME` 覆盖方式、Chrome CDP `127.0.0.1:9222` 开启要求、当前项目内 `run_mediacrawler.py` 调用示例、搜索结果分析命令，以及生成前必须走 DoodleStory 全量 VL 的边界；同时把 README 中的当前 Sprint 合同链接修正为 Sprint 56。
- 完成 Sprint 56 抖音 Skill 独立运行与中文执行链路：新增当前项目内 `run_mediacrawler.py` 封装，通过 `MEDIACRAWLER_HOME` 或默认路径调用外部 MediaCrawler，避免新对话依赖聊天历史记住采集脚本位置；`douyin-hot-sample-research` 主流程和关键说明改为中文优先；`analyze_search_results.py` 默认按作品 ID 去重，输出原始候选数与去重状态，并降低小分母高转发率导致的 A 类误判；账号分析规则改为可以先全量抓取账号作品、再默认分析最近 N 条，且把大号/粉丝多/作品多记录为 `large_mature_account_penalty`，作为快速模仿度减弱项；生成链路明确 `generation_brief` 前必须先完成 DoodleStory 全量 VL 的 `full_story_extract`，提取完整原文后再分析、优化和原创改写。
- 完成 Sprint 55 抖音 Skill 分步执行协议：`douyin-hot-sample-research` 默认改为每次只执行一个小 step，完成后输出本轮完成内容和下一步建议；只有用户明确说“一次执行到位 / 跑完整流程 / 连续执行 / 直接跑完”时才连续执行。新赛道预测被拆为 `lane_intake`、`market_scan`、`market_scoring`、`deep_probe_selection`、`topic_hypothesis`、`experiment_plan`、`generation_brief`、`post_result_intake`、`deviation_review`、`strategy_update`；账号复盘被拆为 `review_intake`、`account_baseline`、`market_expectation`、`post_result_intake`、`deviation_review`、`comment_and_topic_review`、`strategy_update`。每步输出统一包含 `input_used`、`artifact`、`decision`、`blocked_by`、`next_step`，降低用户输入复杂度。
- 抖音热门图文样本 Skill 进入第二步功能验证：基于 MediaCrawler 的 `画一个故事 + 最近一周` 搜索结果新增 `analyze_search_results.py`，可把 `search_contents_*.jsonl` 转成候选评分 CSV/JSON/Markdown，按发布时间、图文类型、点赞、评论、收藏、转发、互动率和标签输出 A/B/C/D 分类；已用 14 条真实搜索结果验证得到 7 个 A、5 个 B、2 个 C。随后用 detail 模式对 A 类样本 `7651192895256480858` 抓取 10 条真实评论，分析脚本可合并评论状态和高赞评论摘要，验证评论采集与候选分析链路可行。
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
- 调整最终生图中人物对白的中间态策略：故事方案、提取分镜和完整故事的 prompt 规则都改为把人物对白写进 `visual_prompt`，并绑定说话人物、动作、表情和对象，不再把对白拆到 `image_text.dialogue`；最终 prompt 编译规则会把 `visual_prompt` 中的人物说话画成对白气泡，且在旧数据同时存在旁白直接引语或 `image_text.dialogue` 时只画一次，避免同一句台词重复出现。
- 开始并完成 Sprint 49 抖音热门样本调研 Skill：新增项目本地 `.agents/skills/douyin-hot-sample-research/`，把 `douyin-downloader` 明确为热门图文样本库采集底座；Skill 第一阶段固定为关键词/热榜调研、最近热门筛选、候选样本分层，再下载少量入选作品；新增 `references/research-fields.md` 统一样本字段，新增 `scripts/summarize_samples.py` 从搜索 JSONL、下载 metadata 和额外数据目录中汇总日期、标题、作者、图文类型、图片数和互动数据。该版本先把 Codex 人工抽检与 VL 批量提取分开，后续由 Sprint 50 明确改为复用 DoodleStory 现有内容提取 VL 链路。
- 完成 Sprint 50 抖音样本 Skill 复用现有 VL 链路：更新 `.agents/skills/douyin-hot-sample-research/`，把图片理解策略改为复用 DoodleStory 现有内容提取 VL，而不是另起模型链路；Skill 明确区分 `preview_vl` 与 `full_story_document`，只判断开头、结尾或中段转折时只传对应图片窗口，只有样本进入故事文档或任务创建候选时才走完整图集提取；字段参考新增 VL 输入页码、结果类型、是否需要全量提取和内容提取 ID 等记录项。
- 完成 Sprint 51 抖音 Skill 集成浏览器态搜索采集：新增合同 `docs/contracts/sprint-51-douyin-browser-search-skill.md`；在 `.agents/skills/douyin-hot-sample-research/scripts/` 增加 `browser_search_collect.py`，基于已登录浏览器 `storage_state` 通过搜索框输入关键词并监听 `/aweme/v1/web/general/search/single/` 响应，输出 raw responses、全部候选、图文候选、meta 和 summary；Skill 工作流改为关键词调研优先使用浏览器态搜索，选中样本后再交给 `douyin-downloader` 下载和评论/基础数据采集；字段参考新增浏览器态采集证据路径、响应数量、storage_state 路径和明确 blocker。未下载外部代码，采集脚本独立放在 Skill 自有目录供后续调用。
- 完成 Sprint 52 抖音账号与评论多维分析策略：新增合同 `docs/contracts/sprint-52-douyin-account-comment-analysis-strategy.md`；将搜索、筛选、下载、基础指标和初步评论采集明确命名为“基础数据获取”；新增账号主页稳定性、评论区高赞/高回复讨论、开头结尾 VL 点检、最后一张实景/证据图判断，以及文案和评论热门讨论合并沉淀的策略文档；字段参考补充账号流量稳定、评论聚类、结尾证据类型、复制角度、风险说明和下一轮迭代假设，用于后续 Skill 自动优化关键词、评分权重、VL 范围和选题方向。
- 完成 Sprint 53 抖音最近 7 天搜索结果处理流程：新增合同 `docs/contracts/sprint-53-douyin-seven-day-search-processing.md` 和 `references/seven-day-search-processing.md`；Skill 新增“搜索结果横向决策层”，先比较类目热度，再筛选账号模仿度和账号探查优先级，最后把真人/实景结尾转化为 image-2 可生成的真实感复刻策略；`analyze_search_results.py` 新增内容类目、账号探查优先级、可选 creator profile 模仿度字段，并输出 `category_summary.csv/json`。用 `画一个故事 + 最近一周` 14 条真实搜索结果验证，得到 4 个类目，其中家庭婚姻和纯爱治愈均有多条 A/B，社会安全为单条强爆点。
- 完成 Sprint 54 抖音预测型内容链路架构：新增合同 `docs/contracts/sprint-54-douyin-prediction-workflow-architecture.md` 和 `references/prediction-workflow-architecture.md`；Skill 输入收敛为两个自然入口：新赛道关键词预测、账号复盘诊断；明确重要实验至少用 2 个账号发布以隔离账号因素；后台详细数据进入 experiment result 层，兼容手工粘贴、CSV/JSON 导入和未来 connector；内容库定位为已验证机制库而非资源包，沉淀 hook、故事母题、评论触发、真实感结尾、账号适配和偏差诊断，用于后续结合热点生成新内容。现有 `DY爆款复刻` 保持单条样本执行器定位，不改为预测策略入口。
- `画一个故事` 内容实验推进到 `probe_collection`：对 3 个 primary 样本和 1 个 risk_observation 样本完成 detail、每条 50 条一级评论、账号主页卡和首尾页 `preview_vl`；报告写入 `content-lab/market_scans/2026-06-16-huayigegushi-probe-collection.md`。控制器判断该关键词下存在可实验空间，第一轮优先从低粉低作品账号也跑出强互动的 `family_marriage` 机制进入 `topic_hypothesis`，社会安全样本只做风险与评论机制观察。
- `画一个故事` 内容实验完成 `topic_hypothesis`：新增 `content-lab/market_scans/2026-06-16-huayigegushi-topic-hypothesis.md`，形成 `H1-family-rule-loop` 和 `H2-marriage-boundary-three-rounds` 两个可发布假设；分别定义预测机制、用户需求、原创角度、风险边界和 2h/24h/72h 最低继续线与爆点信号线。控制器状态推进到 `needs_experiment_plan`，下一步需要固定账号、画风、页数、发布时间和实验条数。
- `画一个故事` 内容实验完成 `experiment_plan`：用户确认仅有两个账号 `行走的故事` 和 `小黄鸭与大熊`，已将 H1/H2 都分配到两个账号，形成 4 个内容槽；`publish_plan.json` 固定账号组、10 页长度、晚间 `20:30-21:30` 发布窗口、2h/24h/72h 指标记录字段和每条最低继续线。当前计划状态为 `experiment_planned_not_publishable`，下一步进入 `full_story_extract`，优先建议提取 H2 源样本 `7650413089900236066`。
- 根据用户反馈调高 `画一个故事` 实验发布频率：从单一晚间窗口改为总账号池每天 `2-3` 条，基础窗口为 `12:10-13:10` 和 `20:30-21:30`，素材审核顺利时可启用 `22:00-22:40` 第 3 条加速窗口；同时增加同账号同日最多 2 条、同账号间隔至少 3 小时、按实际发布时间计算 24h 数据的节奏护栏。
- `画一个故事` 内容实验完成 H2 `full_story_extract`：对源样本 `7650413089900236066` 全量 15 页运行 DoodleStory VL，产出 `content-lab/full_story_extracts/2026-06-16-huayigegushi-h2-7650413089900236066.md` 和 `.json`，确认可作为 `generation_brief` 的完整源故事文档；下一步需要原创改写，不得照搬源故事桥段。
- `画一个故事` 内容实验完成 H1 `full_story_extract`：对源样本 `7649315939447871470` 全量 8 页运行 DoodleStory VL，产出 `content-lab/full_story_extracts/2026-06-16-huayigegushi-h1-7649315939447871470.md` 和 `.json`；4 个发布槽均推进到 `needs_generation_brief`，H1 后续只提炼“家庭身份规则循环”机制，不沿用年轻后妈、后后妈、未成年人或暧昧继亲关系等高风险桥段。
- `画一个故事` 内容实验完成 4 个 `generation_brief`：为 `P1-H1-walking-story`、`P2-H1-duck-bear`、`P3-H2-walking-story`、`P4-H2-duck-bear` 分别产出可直接进入 DoodleStory `故事方案` 模式的原创 brief；H1 两版保留家庭身份规则循环但换成门牌/红围裙表层机制，H2 两版保留三回合边界测试但避开旧床单、纸尿裤、剩菜和离家桥段。4 个发布槽状态推进到 `needs_task_creation`，下一步创建真实生成任务并回填 `content_id` 或 `task_id`。
- 根据发布前审核调整 `画一个故事` 发布计划：读取 `output/tmp.txt` 后新增审核记录 `content-lab/prepublish_reviews/2026-06-16-huayigegushi-generation-brief-review.md`；H1 暂停第一波发布，原因是源样本诱因更接近安全化后的伦理身份错位幻想，而当前木牌/红围裙 brief 偏成规则游戏；H2 保留但重写为“三次压抑累积 + 最后行动兑现”，并取消用账号名反推拟人角色的做法。第一波只允许 H2 两条修正版 brief 进入任务创建。
- 根据新版内容迭代控制器 Skill 注入叙事人格：`prediction.json` 补齐必填的 `narrative_persona_profile`，本轮 H2 第一波选择 `intimacy_trial` / 亲密关系审判型；新增 `content-lab/prepublish_reviews/2026-06-16-huayigegushi-persona-injection.md`，并重写 `P3`、`P4` 两份 H2 brief，让情绪曲线从“压抑 -> 怀疑 -> 失望 -> 审判 -> 释放”推进。H1 继续暂停，下一步只为 H2 两条人格注入版 brief 创建真实任务。
- 修正 `画一个故事` H2 P3 brief 的图7：将“洗杯子、听电话、亲戚催促、周远未开口”的连续过程改为厨房门半开、手机通话界面、手指悬停和嘴唇紧闭的单帧画面，降低进入下一步生图任务时的动作混杂风险。
- 统一修正 `画一个故事` H2 两份 brief 的分镜画面语言：在 `P3`、`P4` 的 brief_text 中补充“每个 panel 只能描述一个定格画面”的约束，并将图1-10 中的过程型表达改写为物件、屏幕、人物站位、手势和表情可承载的单帧画面，降低 DoodleStory 生图阶段对连续动作的误解风险。
- 调整 `画一个故事` H2 两份 brief 的故事文案距离感：去掉正文中的具体人名，统一改为“我、丈夫、婆婆、亲戚、堂哥”等关系称呼；旁白和内心 OS 改为更直白的读者代入式表达，强化文字承载故事、画面辅助情绪的生成方向。
- 按对标文案机制再次调整 `画一个故事` H2 任务表达：保留旁白作为完整故事主线，将 `P3`、`P4` 每页画面描述改成“妻子想/婆婆说/丈夫说/亲戚说”的语义指令，让 DoodleStory 由说话、想法、表情和气泡自动转成画面效果，避免画面行继续承担复杂叙事。
- 修正 `画一个故事` H2 任务表达边界：将 `P3`、`P4` 的画面行从纯“谁说/谁想”改为“清晰场景 + 人物对白或内心 OS”，旁白仍单独保留并负责完整故事推进，避免画面行过度抽象，也避免回到堆砌物件和站位的旧写法。
- 降低 `画一个故事` H2 文案的看图理解负担：按对标样本的“旁白讲故事、画面给证据”方式重写 `P3`、`P4`，让旁白直接说明婆婆、亲戚、堂哥、丈夫分别做了什么；画面描述只保留年轻妻子、丈夫、中年女人、亲戚、账本、钥匙、招牌等低识别成本场景，不再依赖读者先认出人物身份或读懂对话气泡。
- 新增自媒体文案库：创建 `content-lab/self-media-scripts/`，用 `README.md` 约定口播文案、标题备选、结构说明和发布后迭代记录的保存方式；保存第一条构建者自媒体口播 `2026-06-16-ai-content-iteration-controller-v01.md`，主题是解释 AI 内容迭代控制器为什么不以批量生成为核心，而以发布前预测、真实数据回流和预测误差为核心，并用 `留言：内测` 作为第一阶段 CTA。
- 迭代第一条自媒体口播 v02：结合 `画一个故事` 实验计划，把文案从抽象“AI 内容迭代控制器”改成有真实现场的构建者屏录口播；新稿保存到 `content-lab/self-media-scripts/2026-06-16-ai-content-iteration-controller-v02.md`，用 33 个候选、21 个 A/B 图文、2 个 family_marriage 假设、2 个账号和 4 个发布槽建立可信度，并按内容诊断、开头优化和小红书标题逻辑完成三轮迭代。
- 强化任务级临时角色形象提取：`extract_task_characters_v1.md` 明确要求根据全文、称呼、人物关系和恋爱/亲情/校园/职场语境推断年龄阶段与性别呈现，第一人称“我”也不能输出模糊人物；任务角色提取调用改为使用 `CHARACTER_EXTRACTION_MODEL` 和 `CHARACTER_EXTRACTION_TEMPERATURE` 低温配置，避免继续走默认高温 LLM 设置。新增单测覆盖火车上“帅哥/后来在一起”语境下第一人称应推断为青年女性学生，并确认调用低温配置。
- 收紧正式生图 prompt 的比例约束：最终发送给图片 Provider 的 panel prompt 现在统一以 `画面比例：...` 开头，并要求严格按该宽高比构图和出图；该前缀位于风格模板、参考图说明和最终画面指令之前，单 panel 修改和 policy blocked 后的提示词改写重试也会重新补齐比例前缀，减少图片模型忽略 3:4、9:16 等比例的概率。
- 开始并完成 Sprint 78 任务用户筛选与联系入口：新增合同 `docs/contracts/sprint-78-task-user-filter-contact.md`；任务页管理员可见用户下拉，前端会把选中的 `user_id` 传给已有任务列表接口，普通用户不展示该筛选；联系我们不占用侧边栏 tab，改为左侧底部用户信息区的轻量入口，鼠标悬浮或键盘聚焦后展示微信二维码并提示使用微信扫一扫。`npm run build --prefix frontend`、`./scripts/check.sh` 和 `git diff --check` 通过；微信号文本在本次需求消息中未提供，当前页面展示为扫码添加微信。
- 修复 Sprint 78 任务页用户下拉为空：根因是任务页加载管理员用户下拉时传了 `limit=200`，超过后端统一分页上限 `100`，导致 `/admin/users` 返回校验错误而没有 options；已改为 `limit=100`，与现有管理员用户筛选保持一致。
- 优化任务页点击卡顿：生产 Network 显示 `styles?status=active` 耗时约 23.8 秒，而 `tasks?limit=10` 约 1.2 秒；根因是任务页 `refresh()` 把任务列表和启用风格列表放进同一个 `Promise.all`，导致风格列表慢时阻塞任务列表刷新和点击反馈。前端已把风格列表改为独立加载，任务刷新只等待任务接口；风格加载慢时只影响风格筛选和创建任务风格选项，不再拖住任务列表。
- 继续优化风格列表慢接口：新增 `/styles/options` 轻量接口，只返回任务页需要的风格选项字段和一张预览图，不返回完整 `style_prompt`、全部参考图列表或完整风格管理详情；任务页改为调用 `api.styleOptions({ status: "active", limit: 100 })`，风格管理页继续使用原 `/styles` 完整接口。新增单测确认 options payload 不包含 `style_prompt` 且能返回预览资产。
- 进一步拆分任务页风格下拉：新增 `/styles/select-options`，只查询并返回 `id/name`，任务页首屏筛选下拉改用该接口；带预览图的 `/styles/options` 只在创建任务弹窗打开后加载，用于风格卡片展示。新增单测确认 select options schema 只有 `id` 和 `name`。
- 修复内容提取分镜结构校验错误暴露内部字段：当 LLM 返回的内容提取分镜 JSON 缺少 `story_title` 等内部 schema 字段时，任务失败信息改为用户可理解的“内容提取分镜结构化失败”，不再把 `story_title Field required` 这类 Pydantic 校验细节展示到前端；详细字段错误仍保留在日志和 prompt trace 中用于排查。`PYTHONPATH=backend backend/.venv/bin/python -m unittest backend/tests/test_llm_storyboard_planning.py`、`backend/.venv/bin/python -m compileall backend/app` 和 `git diff --check` 通过。
- 调整对象存储本地镜像策略：远程磁盘 90% 的主要来源是 `/opt/doodlestory/storage`，其中 `generated_image` 约 14G、`download_archive` 约 6.3G、`douyin_media` 约 1.5G；新写入七牛/阿里云对象存储资产上传成功后默认删除本地镜像，只有显式设置 `OBJECT_STORAGE_KEEP_LOCAL_MIRROR=true` 才保留。任务下载打包改为可从对象存储临时 materialize 图片，打包结束清理 `_cache`，并把 zip 跟随当前存储后端保存，避免继续写入本地 `download_archive`。新增 `scripts/cleanup-storage-local-files.py` dry-run 优先的历史清理脚本，可清理阿里云本地镜像、旧下载 zip 记录和缓存；线上 dry-run 显示当前可识别的阿里云镜像约 1.6G、旧下载 zip 约 6.3G，历史 qiniu 生成图约 10.4G 需先确认是否已转存或可丢弃后再清理。
- 收紧历史本地文件清理脚本默认范围：`scripts/cleanup-storage-local-files.py` 默认只统计/清理昨天 00:00 之前创建的图片类对象存储本地镜像，避免误碰昨天和今天刚生成的图片；如需调整时间可传 `--before-date`。远程 dry-run 在 2026-07-07 运行时默认 cutoff 为 `2026-07-06 00:00:00`，命中阿里云图片镜像约 1.0G；显式包含旧下载 zip 时命中约 5.7G。
- 开始 Sprint 117 第一阶段后端实现：新增 `agent_skills`、不可变 `agent_skill_versions` 和 `agent_runs.skill_version_id`，系统 `idea-to-comic` 从受控文件幂等种为只读数据库版本；新增受控 Tool catalog，以及个人 Skill 创建、草稿 revision 乐观锁、发布幂等、版本列表/详情、历史版本激活、归档/恢复、系统版本克隆和未发布草稿删除 API。AI 编写辅助使用现有 Agent 模型 Router 输出受约束建议，不自动保存、发布或扩大 Tool 白名单。新增 5 项集中测试覆盖 owner 隔离、发布不可变与幂等、激活/归档、克隆、系统 slug 唯一和已有 Run 版本固定；空库 migration upgrade/downgrade、245 项后端测试与 Python compileall 通过。
- 完成 Sprint 117 Skill 管理前端切片：在独立 Agent Studio 增加 `/agent/skills`、新建、编辑和准确版本详情路由；列表实现个人/系统范围、搜索、状态筛选、分页及完整 loading/empty/error 状态，编辑器实现正文主区域、Tool 多选、编写指南、AI 建议预览后应用、草稿保存、发布确认、归档/恢复/删除和系统 Skill 克隆，版本页明确发布版本只读并支持历史版本激活。Session Storage 保留列表筛选，编辑器离开前提示未保存修改；真实浏览器已验证注册用户创建草稿、发布 v1、直接 URL 打开版本页、系统 Skill 只读列表，截图保存于未跟踪 `output/playwright/`，前端生产构建通过。
- 完成 Sprint 117 `@Skill` 与数据库 Runtime 主链路：资源搜索只返回当前用户或系统的未归档启用版本，消息接受时由服务端覆盖伪造名称/摘要并在同一事务固定 `agent_runs.skill_version_id`；前端资源菜单接入真实 Skill 分组并在选择第二个 Skill 时明确替换。Runtime 新增通用 Base Instructions、数据库准确版本 loader、显式/自动 catalog selection、Run 一次性 pin、Tool 白名单校验和 Skill 安全活动事件；正式漫画执行不再调用文件 `load_skill`、`process_comic_agent_run()`、`run_comic_plan()` 或 `run_comic_final()`，而由任意带 `generate_image` 权限且具有已鉴权风格的发布版 Skill 进入统一方案确认/执行路径，无生图权限的 Skill 只走文本结果且不能创建任务。新增资源权限、消息事务 pin、归档后 Run 恢复、自动选择和无权限无副作用测试；`./scripts/check.sh` 通过 250 项后端测试、compileall、空库 migration 和前端生产构建。
- Sprint 117 真实验收与 QA 闭合：隔离数据库注册真实账号并创建 `Sprint 117 清透水彩` 风格；系统 `想法转漫画 v1` 完成《雨伞的回声》2-Panel 方案确认和 2 张真实图片，UI clone 并发布的个人 `个人两格反转漫画 v1` 完成《最后一盆绿》2-Panel 方案和 2 张真实图片，四张均成功、积分 30→26。UI 新建的无 Tool `故事因果检查 v1` 使用真实文本 Provider 输出因果检查，未创建第三个任务且余额保持 26；Style-only 消息由 catalog 自动选择系统 Skill 并停在方案确认。另验证个人 Skill 发布 v2、查看历史、重新激活 v1，文字 Skill 归档后历史 Message 仍保留准确 v1 安全快照。最终 `./scripts/check.sh` 通过 252 项后端测试，QA 报告为 `docs/qa/sprint-117-pluggable-skill-management-agent-loop-report.md`；Sprint 117 标记 Complete（Closed），Evaluation 保持 Deferred。
- 完成 Sprint 118 Skill 管理入口修正：传统工作台主侧栏新增直接进入 `/agent/skills` 的 `Skill 管理`，Skill 管理的 Agent Studio 侧栏新增 `返回传统工作台`；主侧栏导航统一通过现有稳定 URL 路由，不复制 Skill 编辑器或合并 Shell。真实浏览器完成 `/tasks → /agent/skills → /tasks` 往返并验证后退/前进恢复；Agent 路由 4 项测试、前端生产构建和完整 `./scripts/check.sh` 均通过，后者包含 252 项后端测试、compileall 和空库 migration。Evaluation 未实施。

- 完成 Sprint 133 Native 语音字幕原文二次校准：`generate_subtitles` 读取对应
  `NativeAgentAudio.text`，要求 faster-whisper 返回词级时间戳，将识别字符与原文做单调
  序列对齐后只复用真实时间轴；字幕全文、cue 和 WebVTT 文字均来自 TTS 原文，并按标点和
  18 个规范化字符上限切分。匹配率低于 50%、原文为空或缺少词级时间戳时明确失败，不保存
  未校准 Whisper 文本或切换在线服务。8 项聚焦测试及两条真实火山 TTS smoke 通过，其中
  54 字、15480ms 音频拆为 6 条单调 cue 且全文与原文一致；`./scripts/check.sh` 通过
  298 项后端测试、空库迁移、前端构建和 5 项 Remotion 测试。

- 完成 Sprint 127 语音倍速、Whisper 字幕与 Remotion 时间轴：`generate_speech` 新增
  0.5/0.75/1.0/1.25/1.5/2.0 六档倍速并持久化 speed/speech_rate 快照；
  `generate_subtitles` 使用本地 faster-whisper 生成 WebVTT、全文、语言和 segment cue，
  保存独立字幕资产、调用计数、事件与 owner 权限；视频 Scene 可通过 `subtitle_id` 消费
  匹配音频字幕并按 cue 时间显示，仍保留显式整段字幕模式且二者必须二选一。Skill 设置页已可
  独立选择生成语音、生成字幕和渲染故事视频。真实 4440ms 火山音频生成字幕资产
  `3c9f32e33d1b4e0a9ca9123e06d406e5`，并渲染 1086×1448、30fps 的时间轴字幕视频
  `1f657c883bcf4345a21e53692d0faced`；owner/其他用户权限结果为 true/false。
  `./scripts/check.sh` 通过 282 项后端测试、空库迁移、前端构建及 5 项 Remotion 测试。

- 完成 Sprint 129 Native 语音 `ffprobe` 路径修复：终止并取消 Run
  `22a69626bdcc4902a9bc4361c680886f`，运行中的 Tool 随后端进程停止且未在重启后恢复；
  新增 `FFPROBE_EXECUTABLE`，本地启动脚本解析并校验
  `/opt/homebrew/bin/ffprobe` 后显式传给后端。真实火山语音 smoke 成功返回 32301 bytes
  MP3 和 4032ms 时长，重启后无 active Native Run。

- 完成 Sprint 130 Native Agent Run 可终止执行：新增 owner 隔离、幂等的
  `POST /agent-loop/runs/{run_id}/cancel`，使用 `cancel_requested → cancelled` 状态机；
  队列中 Run 直接取消，执行中 Run 取消独立 asyncio Agent Task，prepared/running Tool Step
  统一落为 `cancelled`。所有 Tool 完成和 Run 成功持久化入口都会拒绝取消后的迟到写入，服务
  恢复也会把遗留取消请求收敛为终态而不重新执行。Native composer 在有活动 Run 时将提交按钮
  改为“终止任务”，终止完成前禁用输入、Skill/Style 选择和按钮。新增测试覆盖取消持久化、
  API 幂等、运行中 Task 取消和迟到结果拒绝；`./scripts/check.sh` 通过 286 项后端测试、空库
  Alembic 升级、前端生产构建、Remotion 类型检查及 5 项测试，`git diff --check` 通过。

- 完成 Sprint 131 API UTC 与东八区展示修正：确认宿主机已经是 CST，实际偏差来自 SQLite
  UTC 时间和 `datetime.utcnow()` 经 Pydantic 输出时缺少时区标识，浏览器把它误当成本地时间。
  现已在 `ApiData`、`ApiList` 响应边界递归把 naive datetime 标记为 UTC 并输出 `Z`，Native
  Agent 与普通 Agent SSE 同步使用相同格式；前端日期时间和今天/昨天分组固定按
  `Asia/Shanghai` 展示。没有修改数据库值或整体加 8 小时。新增 4 项时间契约测试并补强
  Native SSE 断言；`./scripts/check.sh` 通过 289 项后端测试、空库 Alembic 升级、前端构建、
  Remotion 类型检查和 5 项测试，`git diff --check` 通过。

- 完成 Sprint 132 Native Agent 最近 Run 原地重试：已有会话输入精确“重试”会调用专用接口，
  自动选择该会话最近 Run 并继续同一 Run ID，不采用提交区当前 Skill/Style，而是复用 Run
  固定的 Skill Version、Style/模型快照、SDK Context 和成功资产。后台同时检查 Run 与 Tool
  Step，支持 Tool 失败但 Run 曾被模型收尾为 succeeded 的情况；已知失败 Tool 必须用原名称和
  原参数在同一 Step 增加 attempt，改写参数、未执行失败 Tool 或仍有 failed Tool 都不能把 Run
  标成成功。活动中、已取消、真正完成和 unknown Tool 明确拒绝；`retrying` Run 可在服务重启
  后重新入队。`./scripts/check.sh` 通过 292 项后端测试、空库 Alembic 升级、前端构建、
  Remotion 类型检查和 5 项测试，`git diff --check` 通过。

## 已知缺口

- 当前 Agent 漫画创建已支持结构化 Style/Character/Task/Panel/Image Version 上下文、同任务只读续作、Panel 版本写操作、真实 VL 和 pause/resume。
- 当前已有 Sprint 112 MLflow trace、Sprint 113 Skill/Tool span，以及 Sprint 114 Artifact/Approval span；正式 Evaluation 发布门槛已按用户决定推迟到功能路线冻结后的最后阶段。
- Sprint 117 已 Complete（Closed）：Skill 数据/API、管理前端、`@Skill`、数据库版本加载、Run pin、通用执行、真实系统/个人生图、纯文本 Skill、版本切换和 QA 均已闭合。正式 Evaluation 继续 Deferred。
- Sprint 118 已 Complete（Closed）：默认工作台已经可以直接进入 Skill 管理，Skill 页面也能明确返回传统工作台。
- 当前 React/FastAPI 代码仍是骨架，尚未达到产品设计完整要求。
- 任务创建、任务详情、取消、下载、完整 worker 流程尚未实现。
- 风格测试已接入真实生图 Provider；参考图模式要求参考图具备公网 HTTP(S) URL，仍建议用真实七牛风格参考图跑一次端到端验证。
- LLM 客户端和 prompts 已实现，但尚未接入任务 worker 流程。
- 任务 worker 已接入 LLM 和统一生图 Gateway 客户端，基础任务详情、批量下载和预览已完成；更精细的运行中恢复策略、单图下载入口和更系统的组件拆分仍可继续完善。
- 历史本地资产尚未迁移到七牛；七牛对象存储已通过独立上传/访问烟测，仍建议用真实任务生成链路做一次端到端验证。
- 旧的多 profile registry 已移除；生图链路已收敛到 `docs/api_v3.md` 对应的统一 OpenAI Images 兼容 Gateway，旧 SiliconFlow 直连、XG edits 和 ApexerAPI Chat 不再作为默认生图路由。
- UI 已开始切换到 Runway / Creative AI Studio 风格，但任务页、详情页和整体组件拆分仍需继续深化。
- 内容提取已完成同机 `127.0.0.1:8010` 可达时的真实图文下载、旧版图文 OCR、故事总结、列表和详情弹窗验证；Sprint 25 曾把图文内容提取切换为 SiliconFlow 视觉模型整组图片顺序理解，Sprint 98 已进一步切到 `gpt-5.4` 并增加页数连续性校验，仍建议用真实漫画图文链接做一次端到端验证。视频音频转写仍需用真实视频链接单独端到端验证。

## 建议下一步

1. 保持 Sprint 117 已关闭状态，不自动扩展多 Skill、脚本/MCP、Memory、TTS、Remotion 或视频能力。
2. 等用户明确确认功能路线冻结并授权后，再重新编号并激活 Deferred Evaluation。
3. 当前不要宣告 `GO_INTERNAL` 或 `NO_GO`。

# Sprint 139 账号创作上下文 Tool（已完成）

- 新增只读 `get_account_creation_context(account_name)` Native Function Tool。用户不需要输入
  内部账号 ID；模型可把自然语言中的账号别名、频道标题、`@Handle` 或远程频道 ID 直接传给
  Tool。精确匹配按别名、Handle、标题、远程 ID 的顺序执行，只有唯一命中才返回完整上下文；
  重名和部分匹配只返回最多 5 个候选，不静默选中。
- Tool 从现有 YouTube 账号、对标账号和已发布视频表读取账号定位、目标受众、阶段目标、
  AI 定义、运营备注、汇总指标、最多 10 个对标账号和最多 10 条近期视频。结果明确排除账号
  邮箱和原始 Analytics JSON；视频长描述和标签使用显式上下文边界并标记是否截断。
- 当前频道是管理员共享资源，Tool 通过 Run → Conversation owner 校验管理员权限；能力只有
  在固定 Skill Version 勾选后才向模型暴露。Skill 管理目录、能力接口和前端名称均已接入。
- 40 项聚焦测试通过；`./scripts/check.sh` 通过 334 项后端测试、空库 Alembic 全量升级、
  8 项前端测试、前端生产构建、Remotion typecheck 与 5 项测试。真实本地数据库 smoke 使用
  “历史商业取证”唯一命中，定位资料完整并返回 1 个对标账号。

# Sprint 137（已完成）

- 已确定将同级多平台导入服务中调通的微信公众号文章抓取能力封装为
  `capture_wechat_article(url)` Native Agent Tool；DoodleStory 负责 Tool
  白名单、执行记录与素材持久化，抓取服务继续负责 Crawl4AI / Playwright。
- 当前范围仅包含微信公众号文章，不包含 YouTube、小红书、抖音 Agent Tool 或账号
  分析；完整合同见 `docs/contracts/sprint-137-wechat-article-agent-tool.md`。
- 已新增真实 `capture_wechat_article(url)` Native Agent Tool：仅允许
  `https://mp.weixin.qq.com/`，调用多平台导入服务 `/api/v1/import`，校验
  `wechat` 平台与输出目录内唯一 `content.md`，完整正文写入
  `external_content` 文件资产，来源信息写入 `native_agent_external_contents`；
  Tool 结果返回稳定内容 ID、资产 ID 和最多 1600 字预览。
- Skill 管理 Tool 目录、列表和详情已标注“微信公众号文章”；对话结果增加公众号文章
  素材卡片，可打开原文和持久化 Markdown。Compose 改为从同级多平台导入服务构建，并
  新增依赖仓库准备脚本。
- 验证完成：后端定向 34 项测试通过；`./scripts/check.sh` 的 316 项后端测试、
  Alembic 全量升级、前端构建、Remotion typecheck 与 5 项测试全部通过；新迁移另做
  upgrade → downgrade → upgrade 通过；Compose 配置展开通过。多平台服务在独立端口
  健康检查确认包含 `/api/v1/import`，使用历史已验证公众号公开链接真实回归返回 200，
  得到 `image_post`、652 bytes Markdown 和 4 个媒体文件。Docker daemon 当时未运行，
  因此未执行本地镜像构建；本机原 `8010` 仍是旧抖音专用进程，需按新 Compose 重建后
  才会切换到多平台服务。

# Sprint 134 多 Agent 文案工作流（已完成）

- 新增系统 `article-creation-team` 总 Skill：Director 通过 OpenAI Agents SDK
  `agent.as_tool()` 调用 Writer 和 Reviewer，角色规则与协作顺序均来自同一份 Skill
  instructions；子 Agent 不接管用户会话，也不能继续创建孙 Agent。
- 新增 Native Agent 文案 Artifact、Approval 和根 Run Checkpoint 持久化。Writer 草稿、
  Reviewer 审稿、最终文案均按版本与 hash 落库；最终稿进入 `waiting_for_input` 后释放
  Worker。批准后同一 Run 成功结束，退回修改则把真实反馈追加到数据库 SDK Session，并将
  同一 Run 重新入队，旧版本保持可追踪。
- Agent 页面新增文案 Artifact 卡、最终稿确认与修改意见交互；三个文案 Tool 的完成状态由
  已持久化 Artifact 校验。该系统 Skill 只开放文本 Tool，不生成媒体。
- 新增 4 项聚焦测试，覆盖子 Agent Tool 构建、Artifact 与退回恢复、批准后纯文本完成以及
  Approval owner 隔离。`./scripts/check.sh` 通过 320 项后端测试、空库 Alembic 全量升级、
  前端生产构建、Remotion typecheck 与 5 项测试。
- 真实页面 smoke 使用账号 `sprint134-smoke-20260729@example.com` 和真实模型完成
  `Writer → Reviewer → 最终文案确认`。Run
  `64420b2fb8fc4eb2bb2624963afa4cde` 成功，草稿/审稿/最终文案 Artifact 分别为
  `a363d580209649ffa645d7402e768a0b`、`a135774a1cb64129a73bb87bfb4d8a46`、
  `55210d376468451789128af60e780541`，Approval
  `5ab1aa8fe1e24193b91ce37649d59914` 已批准；模型调用 4 次，图片、语音、字幕、视频调用均为
  0。本地 MLflow tracing 默认关闭，因此本次 smoke 没有 Trace ID。
- 修复用户手动 Run `65cb3561ecf44b168954f1a8dc3c8d80` 的并发事件序号冲突。该 Run
  已真实调用 `write_article` 子 Agent，并保存 Writer Artifact
  `9e4d371ba7d14c45b46cad378a88a2c5`；失败原因是父 Agent 流式写 Function Call 参数时与
  子 Agent Artifact 事件同时使用 `MAX(sequence) + 1`，抢到相同序号。现新增 Run 级
  `event_sequence` 原子计数器并回填历史最大序号，所有 Native Event 写入口统一原子分配。
  新增双线程交错写入 40 个父事件和 20 个子 Artifact 事件的回归测试，序号完整为 1–60；
  `./scripts/check.sh` 通过 321 项后端测试、空库迁移、前端构建与 Remotion 测试。失败 Run
  的 Writer Artifact 和数据库 SDK Session 均保留，可由用户在原会话输入“重试”继续。
- 增补模型驱动的 Skill Workflow Compiler：完整 `article-creation-team` Skill 只进入一次
  Compiler 模型调用，结构化输出 Director / Writer / Reviewer 局部 instructions、执行步骤、
  分支条件和质量门槛，并按 Skill hash 保存到 Run Checkpoint。Director 和子 Agent 不再注入
  整份 Skill；Runtime 只校验固定角色与三个文案 Tool 的可执行边界。
- 修正 Native Agent 模型调用 Metric：不再把父流 `response.created` 数量当作总调用数，改由
  SDK LLM 生命周期对 Compiler、Director、Writer、Reviewer 的每次请求原子计数，并保存
  `model.request.started/completed`、角色与 execution attempt。MLflow 根 Trace 同步记录本次
  总数、完成数和角色拆分；多个恢复 Trace 可通过 `execution_attempt` 区分。
- 自动化新增编译计划持久化、角色 instructions 隔离、并发模型请求原子计数和跨异步任务
  start/end 关联测试。`./scripts/check.sh` 通过 324 项后端测试（最终定向回归为 34 项）、
  空库 Alembic 全量升级、前端生产构建、Remotion typecheck 与 5 项测试。
- 真实页面 Conversation `b0515a8119f34a4b919e2a7750f1693b` 的 Run
  `a714a716fecc41a7898fe24277fefa3a` 已生成 Writer 草稿、Reviewer 审稿与最终审批稿并进入
  `waiting_for_input`。数据库和 MLflow 均为 7 次真实模型调用：Compiler 1、Director 4、
  Writer 1、Reviewer 1；started/completed 各 7 条，三个文案 Artifact 齐全，四类媒体调用均
  为 0。MLflow 仅 1 个根 Trace，Writer/Reviewer 各自只注入自己的局部 instructions。
- 修复 Agent 对话运行期间强制追底的问题：会话首次打开或用户仍停留在底部 80px 内时继续
  自动跟随；用户向上翻阅后立即停止追底，返回底部后再恢复。新增 3 项滚动位置判断回归测试，
  并将前端单元测试纳入 `scripts/check.sh`；同步更新频道路由新增字段的旧测试断言。真实页面
  Conversation `5244309e9b3046739d78e69504f09c6d`
  在纯文案持续生成、内容高度从 4634px 增长至 6232px 的过程中，手动上翻后始终保持距底部
  约 1800–1900px，未再被拉回底部；图片、语音、字幕和视频均未生成。
- 执行 Sprint 146 对标账号到全媒体的最小真实链路测试：创作账号 `中国文明长纪录片` 成功带入
  对标账号 `Our Lìshǐ` 与绑定风格，生成并批准“隋朝为何短命却重新连接中国”选题；正文
  Artifact `fdcf941ede1d491eb49fe0994428ddf7` 经机器计数为 118 个字符，Reviewer 结论为
  `approved`。测试在 Review → Visual Plan 交接处失败：Review Approval
  `90013041526b42aaaebe246b78f39672` 被错误映射为第二个 `article_draft_review` Gate，真正的
  `editorial_review_gate` 仍为 pending，Run `e62d493e0a9e444589e336303d142da6` 因必需
  Durable Task 未完成而失败，正式 Visual Plan API 返回“正文 Review 尚未批准”。为避免绕过
  状态机或产生无效费用，图片、语音、字幕、视频调用均保持 0；完整证据与修复要求见
  `docs/qa/sprint-146-full-media-e2e-report.md`。
- 经用户明确允许，继续使用上述 118 字审核正文创建独立媒体 Run
  `a23fc6becb5c4fecb9796ed61351cdfa`，锁定单 Chunk/单 Scene 后真实生成 1 张 1086×1448
  图片、1 份 9 cue WebVTT 字幕和 1 个 24.661 秒、1086×1448、H.264 + AAC 的 Remotion
  视频；字幕全文与正文一致，视频抽帧确认画面和字幕正常。续作同时暴露三项问题：首次成功旁白的
  字幕连续两次返回无效词级时间戳后，Agent 重复调用 TTS 生成第二段相同旁白；Skill 要求的
  `inspect_image` 没有执行便进入视频渲染；媒体资产全部成功后，非文案 Run 仍因初始化的文案
  Durable Task 未完成而被标记 `failed`。最终实际调用为生图 1、TTS 2、字幕尝试 3（成功 1）、
  视频渲染 1，没有发布；本地核验产物保存在 `output/sprint-146-full-media-e2e/`，详细 ID、尺寸、
  时长与修复要求已追加到 QA 报告。

# Sprint 151 Video API 文档本地归档（已完成）

- 按用户确认的设置，将 `https://video.inboxlinks.top/api-docs/` 及其站内导航递归发现的 11 个公开
  文档页面保存为 Markdown，集中放在 `docs/external-api/video-inboxlinks/`；每篇文档按独立子目录
  保存，并保留标题、来源 URL、摘要和抓取时间 frontmatter。
- 归档范围包含文档首页、快速开始、认证与约定、通用 CRUD、YouTube 频道管理、上传任务、已上传
  视频、视频分析、频道分析、频道刷量任务和更新日志；新增 README 索引，未调用任何发布/分析接口。
- 用户选择不下载媒体；质量检查确认 11 篇正文均有实质内容，标题与 URL 匹配，没有登录墙、404、
  框架错误页或需要本地化的媒体资源。
- `git diff --check` 和归档专属检查通过。标准 `scripts/check.sh` 已尝试，但仓库脚本为 CRLF，
  在 WSL 中规范化执行后因环境缺少 `python3.11`、且本机没有项目虚拟环境而无法继续；未修改代码，
  该环境限制已记录在 Sprint 151 合同中。
- 合同：`docs/contracts/sprint-151-video-api-doc-archive.md`。

# Sprint 152 项目出站 API 调用清单（已完成）

- 将原有的 SiliconFlow/Agent 地址说明扩展为全量出站调用清单，覆盖普通文本与视觉、Native Agent Responses、旧 Agent Router、统一生图网关、XG、Grok CLI、SiliconFlow 语音、火山语音、Whisper、FFmpeg、Remotion、comic-video-studio、多平台导入、抖音下载、YouTube 研究与发布、七牛、阿里云 OSS、MLflow、飞书告警和内部 FastAPI 边界。
- 另外记录了兼容性探测、Agent SDK 探测、Runtime smoke 和 MLflow smoke 等诊断脚本的主动调用，区分正常业务链路与手工诊断链路。
- 明确当前 Native Agent 主地址是 `TEXT_FALLBACK_BASE_URL` 规范化后的 `/responses`，SiliconFlow 是独立的 `/chat/completions`、语音注册和语音合成链路；同时记录 `APEXERAPI_BASE` 当前只存在配置和模型归类逻辑，没有 DoodleStory 直连请求。
- 新增 SiliconFlow 免费额度模型白名单与简要选型，覆盖通用文本、推理、视觉、全模态、代码、图像、视频、检索、TTS 和 LoRA；并明确当前仅部分能力已有直连调用，运行时代码尚未强制校验模型名。
- 文档只保留公开 Endpoint、路径、配置名和代码入口，没有写入 API Key、Secret、Token 或完整 webhook URL。
- 验证完成：代码扫描确认后端出站入口；`git diff --check` 通过；文档代码块和敏感配置检查通过。完整 `scripts/check.sh` 未重复执行，原因与 Sprint 151 相同：当前 WSL 缺少 `python3.11`，且本次仅修改文档。
- 合同：`docs/contracts/sprint-152-outbound-api-inventory.md`。

# Sprint 153 项目架构导览与 Agent 扩展蓝图（已完成）

- 新增 `docs/architecture/project-guide.html`：可在本地浏览器直接打开的中文项目导览，集中说明
  DoodleStory 的当前架构、Native Agent Run 生命周期、YouTube 研究到发布边界、可复用能力、
  已知缺口，以及把新 YouTube 赛道研究 / 视频制作落为独立 Agent Sprint 的最小实施切面。
- 新增三张独立 SVG 图：系统架构、Native Agent 持久化执行时序、YouTube 研究 / 制作 / 发布
  三段时序。HTML 使用本地相对路径引用，不依赖 CDN、在线字体或外网资源；页面同时可跳转到
  关键源码、规格、进度、API 调用清单与视频发布平台文档归档。
- 文档明确区分“可复用的 Native / Durable Runtime 积木”“受环境配置约束的外部服务”与“仍需
  实施的赛道策略、实验闭环和规模化调度”，避免把现有代码、配置字段或未来方案混为已完成能力。
- 验证完成：HTML 的 15 个本地资料 / 图表引用与 8 个目录锚点均可解析；三张 SVG 全部通过 XML
  解析；`git diff --check` 通过。图表 PNG 转换工具因本机缺少 `sharp` 依赖未执行；HTML 使用的
  SVG 是正式无损资产，因此未修改项目或全局 Skill 依赖。
- 合同：`docs/contracts/sprint-153-project-architecture-guide.md`。

# Sprint 154 YouTube 赛道验证包与 Agent 流程设计（已完成）

- 新增独立目录 `docs/strategy/youtube/`，集中保存 YouTube 赛道调研、可复用 Agent 流程模板和
  外部依赖准备清单；项目架构导览同步增加入口，避免将新赛道资料分散到既有 API、产品或抖音实验
  文档中。
- 基于当前 DoodleStory 的“原创旁白 + 静态插画 / 分镜 + 字幕 + Remotion + 人工发布”能力，首轮
  推荐验证“原创插画历史微纪录片 / 历史机制解释”；世界神话与民间故事、地理 / 城市机制解释作为
  备选。新闻、金融 / 医疗建议、名人八卦、真实犯罪、儿童向和模板化情感故事不作为首轮方向。
- 调研记录使用 YouTube 官方 Blog / Help 的动画、虚拟创作、教育使用、AI 披露和获利政策来源，
  明确这些只是广义平台信号；任何赛道结论仍需真实发布数据验证，不能承诺播放量、获利或变现。
- 首轮建议先完成“对标频道研究 → 研究报告 → 3 个选题 → 人工确认”的小 Sprint；后续再做 6 条、
  单变量、带来源账本和发布前预测的内容实验，且同一机制需多次独立证据后才允许成为候选规则。
- 验证完成：新增 Markdown 目录的本地链接、结构标题和架构导览的 16 个本地引用均通过；
  `git diff --check` 通过。全程没有调用模型、媒体 Tool 或任何真实发布接口。
- 合同：`docs/contracts/sprint-154-youtube-niche-validation-pack.md`。

## YouTube 持续研究（按用户明确触发继续）

- 新增 `docs/strategy/youtube/research-log.md` 作为日期化证据日志。按用户要求取消每日 / 定时研究任务；
  后续只在用户明确启动时，在当前任务内连续完成多轮研究。仅在记录到实质新增证据或推荐发生变化时
  更新资料并提交，不自动推送远端。
- 第一轮后续研究补充了 YouTube 官方的留存、CTR / 展示和发布节奏说明：2 小时数据只记录，留存
  通常需要 1–2 天处理；达到数据条件后优先比较 30 秒 intro、平均观看比例、留存峰谷和同长度
  视频的典型留存。CTR 需结合展示量和流量来源，不单独作为胜负依据。
- 该补充不改变“原创插画历史微纪录片 / 历史机制解释”为首轮待验证方向；没有目标频道和真实数据，
  尚未形成任何可写入长期 Skill 的规则。
- 第三轮持续研究将 YouTube 的频道级“非真实内容”获利边界和合成内容披露要求落入既有验证资料：
  后续新赛道 Agent 必须保存原创性账本，并在发布 Gate 保留可解释的 AI 披露判断；这不是增长或获利
  保证。公开频道页仅作为格式线索，未调用项目频道研究 Tool、模型、媒体或发布接口，也未使用第三方素材。

# Sprint 155 YouTube 候选题、格式与相邻赛道多轮研究（已完成）

- 为“古代城市如何解决日常限制”完成三个双来源候选账本：罗马粮食经 Ostia / Portus、河运、仓储与
  计量进入供应链；罗马城市供水通过重力、分水、用途与维护运行；摩亨佐-达罗以街道、井、洗浴和排水
  物证展示规划能力，同时明确遗址部分发掘、文字未释读等未知项。当前排序是粮食供应、城市供水、
  摩亨佐-达罗排水，只代表来源与可视化适配度，不代表市场表现。
- 公开观察 History Matters、The Armchair Historian 和 Simple History 后，将三者分别定位为单问题包装、
  来源 / 团队署名和视觉题型广度参照；公开页没有后台留存、流量来源、成本或受众数据，因此没有建立
  频道表现排名，也没有复制固定标题后缀、脚本、画面或音乐。
- 修正原验证计划的重要口径错误：2024-10-15 后上传的方形或竖屏、最长 3 分钟视频会被归为 Shorts，
  不能继续把 3:4、90–180 秒方案与普通视频 CTR、自定义缩略图和 30 秒留存混用。默认研究建议改为
  16:9、90–180 秒普通视频；若选择 Shorts，必须另开同规格实验，并记录 engaged views 和
  `Stayed to watch`。1–3 分钟 Short 的有效 Content ID claim 也被加入发布前硬 Gate。
- 对历史助眠、神话民俗、城市 / 地理、全动画军事史和 AI 写实历史重建完成压力测试。历史助眠因公开
  样本常见 1.5–3 小时，会放大当前真实 smoke 已暴露的重复 TTS、图片检查、长任务恢复、字幕、存储和
  成本风险，降为后续音频优先实验；首选仍是历史机制解释，神话民俗为备选，城市 / 地理先作为子题型。
- 新增 `candidate-topic-source-ledgers.md` 与 `format-and-adjacent-lane-review.md`，同步更新验证报告、
  外部依赖准备清单、研究日志和目录索引。全程未调用项目频道研究 Tool、模型、媒体或发布接口，未创建
  定时任务，也未推送远端。合同：`docs/contracts/sprint-155-youtube-topic-format-research.md`。

# Sprint 156 YouTube 六题矩阵、多语言与获利路径研究（已完成）

- 将历史机制候选池从三个扩展为六个。新增印加道路接力通信、吴哥季风水网和江户城市消防，分别由
  UNESCO / Smithsonian、UNESCO / APSARA 参与的同行评议研究、东京图书馆 / The Met 等不同来源类型
  交叉支持，并逐项记录可支持主张、过度推断、可画链路与停止条件。
- 当前来源与静态分镜适配排序为：罗马粮食、印加通信、罗马供水、江户消防、吴哥水网、摩亨佐-达罗
  排水。六题按流动网络、水与季节、城市风险分组；排序和分组只用于后续研究 brief，不代表播放潜力，
  也未写入 `strategy_memory.md`。
- 核对 YouTube 多语言能力与当前项目边界：平台支持翻译标题 / 描述、自动配音，以及部分创作者可用的
  自有多语言音轨；YouTube Data API 有原始语言和 `localizations` 字段。但当前外部 Video API 与
  DoodleStory 发布 payload 只有标题、描述、标签、合成媒体、封面和视频等字段，不能自动设置语言、
  翻译元数据或第二音轨。首批固定一个原始语言，上传后语言管理仍是 YouTube Studio 人工步骤。
- 核对 YPP 双路径：500 订阅者层的早期功能与 1,000 订阅者层的广告分成，分别允许普通视频公开观看
  小时或近 90 天有效 Shorts 观看达标；Shorts Feed 观看小时不计入普通视频 4,000 小时。门槛只作为
  运营约束，不作为内容机制成功、格式优劣或收入预测。
- 新增 `language-and-monetization-boundaries.md` 与 `six-topic-experiment-matrix.md`，扩展候选来源账本，
  同步更新验证报告、外部准备清单、研究日志和目录索引。全程未调用项目频道研究、模型、媒体或发布
  接口，未创建真实实验、定时任务或媒体产物。合同：
  `docs/contracts/sprint-156-youtube-six-topic-language-monetization-research.md`。

# Sprint 157 YouTube 第三方趋势源评估与接入边界（已完成）

- 使用用户授权的 LuluJAI 付费会员账号完成只读检查，覆盖长视频蓝海榜、月度趋势榜、低粉频道增长榜、
  搜索热词榜、Shorts 蓝海榜和爆款案例拆解；没有收藏、购买、修改账号、使用生图额度或保存登录凭据。
- “英语 + 历史悬疑”交叉筛选显示 225 条结果。前 12 条方便抽样中只有 1 条严格属于事实型古代历史
  解释，其余混入 AI 科幻、真实犯罪、政治、教程、地理和 IP 设定，证明第三方垂类不能替代人工标签。
- 两条 YouTube 原页复核确认视频身份和低粉高播放方向，同时显示第三方播放 / 订阅快照落后于原页；
  页面没有精确抓取时间，因此没有推断固定延迟。
- 新增 `third-party-trend-source-assessment.md`，明确 LuluJAI 只进入候选发现层；机会度、供给缺口、
  动量、VPH 和案例解释按第三方派生信号处理。同步更新验证建议、研究日志、依赖清单和目录索引。
- 本轮新增“古代日常生活中的具体限制”为待扩样观察，不改变现有六题排序、90–180 秒默认研究假设、
  `strategy_memory.md` 或任何 Skill 规则。控制器状态、凭据泄漏、7 份相关 Markdown 本地链接、12 条
  样本计数和 `git diff --check` 均已验证通过。合同：
  `docs/contracts/sprint-157-youtube-third-party-trend-source-assessment.md`。

# Sprint 158 YouTube 古代日常生活题型扩样（已完成）

- 沿用 LuluJAI 人工发现层，并使用 YouTube 公开搜索与 Data API v3 同日复核，保留 9 条严格样本，
  来自 9 个频道；其中 5 个频道观察时订阅不足 2 万。
- 样本覆盖身体与卫生、盐与饮食、天气与庇护、军队卫生和育儿协作，允许将“具体基本需要 + 缺失
  现代便利 + 历史解决机制”从单条观察提升为后续单变量实验候选。
- 育儿子类出现跨频道近重复标题，说明需求线索和模板拥挤并存；不复制固定问句，不把播放量视为因果、
  收入或可复制增长证据。
- 9 条视频时长为 7:35–23:35，中位数 11:37；没有同机制短视频对照，现有六题排序、16:9 的
  90–180 秒默认研究假设、`strategy_memory.md` 和 Skill 规则均保持不变。
- 新增 `ancient-everyday-life-sample-study.md`，同步更新研究索引、第三方来源评估和研究日志。9 条
  样本、9 个原链接、5 个低订阅频道、6 份相关 Markdown 本地链接、凭据扫描、控制器状态、策略记忆
  边界和 `git diff --check` 均已验证通过。合同：
  `docs/contracts/sprint-158-youtube-ancient-everyday-life-sample-expansion.md`。

# Sprint 159 YouTube 古代盐获取案例来源账本（已完成）

- 比较公元 600–900 年伯利兹南部 Paynes Creek 盐场群、约前 1500 年起的 Hallstatt 盐矿和约
  前 2000–前 200 年的中坝制盐遗址；选择 Paynes Creek，是因为盐厨房、煮卤陶器、居住建筑、船桨
  和沿海—内陆物质联系在同一时间与地区边界内组成了最完整的生产—运输解释链。
- 新增 `ancient-salt-access-source-ledger.md`，整理 6 份同行评议来源、10 条事实主张和 7 个可视场景，
  逐项标记直接证据、支持性解释与未知项；明确船桨不是单次运盐记录，110 处点位不是同时运营工厂，
  盐饼也不能直接写成已证实货币。
- 研究问题收窄为“古典期玛雅海岸盐工如何把 Paynes Creek 的卤水变成可运往内陆的盐”，不再把不同
  文明、盐源和千年技术史拼在同一题；Hallstatt 与中坝分别保留为矿工劳动和内陆卤水制盐的独立候选。
- 本轮只完成来源账本与 research brief，没有编写脚本、分镜或媒体，没有创建发布实验、定时任务或
  自动采集；现有六题排序、16:9 的 90–180 秒默认研究假设、`strategy_memory.md` 和 Skill 规则不变。
- 3 个候选、6 份来源、10 条主张、7 个场景、6 份相关 Markdown 本地链接、凭据扫描、控制器状态和
  `git diff --check` 均已验证通过。合同：
  `docs/contracts/sprint-159-youtube-ancient-salt-source-ledger.md`。

# Sprint 160 LuluJAI 会员长视频榜跨榜研究（已完成）

- 同日只读抽样长视频蓝海、月度热门、低粉频道增长和搜索热词 4 个会员榜面，各保留当前顺序前 10，
  共人工分类 40 个位置；没有保存登录凭据、会话或站点私有接口响应，也没有创建定时任务。
- 40 条中严格古代日常与事实历史为 0；月度榜仅 1 条 Morning Brew 商业系统解释属于相邻事实知识。
  蓝海与月度的 2 条精确重复视频均为直播 / 回放，搜索前 10 则由 8 条音乐和 2 条 IP 关键词组成。
- 低粉榜完整可见的 8 张卡片中有 7 张“单条带飞”，主要是音乐与 AI 虚构；同频道、系列和代表视频
  也会继续出现在搜索榜，说明多个榜面可能共享同一底层内容波次，不能当成独立需求样本。
- 回 YouTube 原页复核 5 条代表视频的身份、发布日期、时长、当前播放和订阅，确认站内有采集时间差、
  四舍五入和标题文本差异；Danjuma、Toy Maze X、STEVENHEART 均为直播回放，不是普通叙事长视频。
- 新增 `lulujai-member-ranking-cross-list-study.md`，并同步更新第三方来源评估、研究索引和日志。决策是
  事实历史仅单榜继续采样，不升级策略规则；六题排序、16:9 的 90–180 秒假设、`strategy_memory.md`
  和 Skill 保持不变。合同：
  `docs/contracts/sprint-160-youtube-lulujai-member-ranking-cross-list-study.md`。

# Sprint 161 LuluJAI 定向历史筛选跨榜研究（已完成）

- 核验长视频蓝海、月度热门和低粉频道增长三个会员页面的筛选控件。只有蓝海榜完整支持
  `长视频 + 英语 + 历史悬疑`；月度榜缺历史垂类，低粉增长榜缺语言与历史垂类，因此当前产品能力
  无法建立同口径历史跨榜比较。
- 蓝海组合筛选真实生效：URL、pressed 状态和页面标签一致，当前交叉结果 231 条。按合同保留当前顺序
  前 20 条并人工分类，严格事实历史 2 条、严格古代日常 1 条，且古代日常仍是已知 Venn Stories；
  真实犯罪 / 法律 5 条，其余混入体育、教程、政治、IP、AI 科幻、收藏、旅行、寻宝和宽泛评论。
- 回 YouTube 官方公开视频页复核 5 条单榜候选的标题、频道、精确播放、发布日期、时长和直播状态；
  5 条均为非直播，当前播放均高于 LuluJAI 快照，但页面没有站内采集时间，未计算固定延迟或增速。
- 新增 `lulujai-filtered-history-cross-surface-study.md`，同步更新上一轮跨榜报告、第三方来源评估、
  YouTube 索引和研究日志。决策是停止使用“LuluJAI 历史跨榜趋势”，站点只保留单榜人工发现；没有
  创建每日任务、自动采集、脚本、媒体或发布，也未修改六题排序、默认时长、策略记忆或 Skill。合同：
  `docs/contracts/sprint-161-youtube-lulujai-filtered-history-cross-surface-study.md`。

# Sprint 162 LuluJAI 定向历史列表信息饱和研究（已完成）

- 固定蓝海榜 `长视频 + 英语 + 历史悬疑`，核验 URL、标签、231 条结果、6 页和每页 40 张卡片后，
  按当前顺序读取第 21–40 与第 41–60 两个不重叠批次，共人工分类 40 个位置。
- 第 21–40 条的 ThinkMan 盐与 Ink Explainer 连续降雨都是既有严格视频精确重复，没有新频道；
  第 41–60 条出现 Ink Explainer 的新视频，并新增 Oddlyhuman 与 Pastly 两个严格候选频道。因此预设的
  “两个批次均无新频道”饱和停止条件未满足，不能在第 60 条宣布列表饱和。
- 回 YouTube 官方公开视频页复核全部 3 条新严格位置的标题、频道、精确播放、发布日期、时长和
  非直播状态；官方频道 RSS 又确认两个新增频道持续覆盖古人类火、酒、工作、迁徙、食物、冰河期、
  牙科和石器时代生存，排除了单条 `ancient` 关键词偶然命中。
- 40 个位置只有 5 个严格位置，去掉 2 个精确重复和 1 个已知频道新视频后，净增 2 个频道；其余
  87.5% 是其他历史、考古谜团、现代采蜜、真实犯罪、体育、IP、电影或音乐。候选池从首轮 9 个频道
  增至 11 个，但新增频道仍属于同一古人类问句家族，下一轮先做频道同质性比较，不继续无边界翻页。
- 新增 `lulujai-history-list-saturation-study.md`，同步更新定向筛选报告、古代日常样本、第三方来源评估、
  YouTube 索引和研究日志。六题排序、16:9 的 90–180 秒假设、`strategy_memory.md` 与 Skill 均不修改，
  没有自动采集、媒体或发布。合同：
  `docs/contracts/sprint-162-youtube-lulujai-history-list-saturation-study.md`。

# Sprint 163 LuluJAI 新增频道族同质性比较（已完成）

- 从 11 条已验证代表视频的 YouTube 官方页面解析频道 ID，读取 10 个频道各 12 条、Oddlyhuman 9 条
  官方 RSS，共对 129 个近期标题完成日常限制、起源 / 演化、战争、文明史、其他以及历史具体性分类。
- Oddlyhuman 9/9、Pastly 9/12 标题直接使用 `Human(s)` 通用主体，分别为 100% 和 75%；两个新增
  频道的 21 条标题只有既有日常限制、起源 / 演化和其他类，没有补出新的问题类别。
- 严寒、降雨、移动、酒 / 药物、工作、身体气味、捕食者、儿童 / 家庭和人类物种已形成至少九个跨频道
  重复簇；两个新增频道只有 2/21 标题带明确地点或时期，6/21 为现代对照或假设，没有提高历史具体性。
- 预设停止规则满足：两个新频道均超过 60% 通用人类主体，且没有新类别在两个频道中各出现至少 2 次。
  因此区分“榜单还能发现更多频道”与“题型还有结构增量”，在题型层面结束 LuluJAI 会员榜研究。
- 新增 `lulujai-new-channel-family-comparison.md` 并同步更新饱和研究、古代日常样本、第三方来源评估、
  YouTube 索引和日志。只在榜单刷新出新结构、研究问题改变、真实实验提出新假设或站点提供授权 API /
  导出时重开；六题排序、默认时长、策略记忆、Skill 和生产流程保持不变。合同：
  `docs/contracts/sprint-163-youtube-lulujai-new-channel-family-comparison.md`。

# Sprint 164 YouTube Oddlyhuman 单频道完整拆解（已完成）

- 新建 `docs/strategy/youtube/channel-teardowns/`，固定频道身份、逐条事实、题型、标题、缩略图、频道内
  分布、来源包装与迁移边界九部分模板；按 LuluJAI 证据接近度排列后续频道，不按播放量选对象。
- 用 YouTube 官方 RSS、oEmbed 和公开视频页覆盖 Oddlyhuman 当前全部 9 条：均非直播，时长
  5:37–9:05，中位数 7:11；9 张官方缩略图均为 1280×720，只在临时目录用于观察，没有提交图片副本。
- 9 条当前播放合计 603,352，但严寒单条 582,236，占 96.5%，是中位数的 217.4 倍；去掉该条后
  其余 8 条平均 2,639.5。结论是“一条异常 + 八条低位基线”，不能用均值或单条表现升级增长规则。
- 缩略图统一为粗轮廓卡通、2–4 个大写词和单问题场景；严寒异常独有猛犸剖面视觉谜题，同时有史实
  过度暗示风险。两张官方缩略图还内含与真实时长不一致的 `25:10`，标题存在语法与大小写缺口。
- 来源包装从早期无引用，提升到最新 3 条分别有 4 / 8 / 11 个直接链接；只将其记录为质量流程改善，
  不与播放做因果绑定。下一对象固定为 Pastly；六题排序、默认时长、策略记忆、Skill 与生产流程不变。
  合同：`docs/contracts/sprint-164-youtube-oddlyhuman-channel-teardown.md`。

# Sprint 165 YouTube Pastly 单频道完整拆解（已完成）

- 沿用统一频道卡，用 YouTube 官方 RSS、oEmbed 和公开视频页覆盖 Pastly 当前 12/12 条：均非直播，
  时长 4:58–11:27、中位数 7:52；12 张官方缩略图均为 1280×720，只临时观察，没有提交图片副本。
- 6/12 标题和缩略图稳定使用现代食物、怕黑、能力、身体错配、古 DNA 与石器时代求生等古今对照。
  该组当前中位数 678，其他组 466；但最新三条恰为频道后 3，视频年龄、题材与画风混淆明显，只保留
  为单变量实验候选，不写成表现因果。
- 12 条当前播放合计 11,004、中位数 466；最高石器时代求生 3,340、占 30.4%，前 3 占 60.7%，
  没有 Oddlyhuman 单条占 96.5% 的极端结构。
- 12/12 描述有来源栏、8/12 有章节、5/12 有不确定性声明，但只有 2/12 给出外部来源直链；稳定来源
  模板值得借鉴，链接可审计性仍需增强。下一轮先做两张已完成频道卡横向比较，不立即进入第 3 个频道。
- 新增 `channel-teardowns/pastly.md`，同步更新拆解索引、YouTube 索引和研究日志；策略记忆、Skill、
  六题排序、默认时长与生产流程不变。合同：`docs/contracts/sprint-165-youtube-pastly-channel-teardown.md`。

# Sprint 166 Oddlyhuman / Pastly 包装变量比较（已完成）

- 对齐两张完整频道卡后，明确停止跨频道绝对播放排名：Oddlyhuman 最高单条占总量 96.5%，Pastly 为
  30.4%，频道阶段、视频年龄、题材和画风均不同，公开播放不能证明纯历史或现代镜像更优。
- 结构上确认 Oddlyhuman 9/9 使用古人类主体 / 古代场景，Pastly 6/12 使用现代生活与古人并置；现代
  镜像是可隔离包装变量，但同时改标题与首图会破坏单变量要求。
- 为 Paynes Creek 同一事实内容建立非生产 A / B：第一轮只改标题为纯历史机制或现代便利缺失，固定
  同一视频、缩略图、旁白、时长、来源、账号、发布时间等 12 项，以 CTR 为主指标、30 秒留存和平均
  观看比例为辅助；无法随机分流标题时不执行，不用顺序改标题或重复上传伪造实验。
- 当前只有设计，没有创建实验目录、预测、脚本、分镜、媒体或发布；古今分屏留给后续第二个独立变量。
  下一频道选择 Venn Stories，策略记忆、Skill、六题排序和默认时长不变。合同：
  `docs/contracts/sprint-166-youtube-oddlyhuman-pastly-packaging-comparison.md`。

# Sprint 167 YouTube Venn Stories 当前窗口拆解（已完成）

- 用 YouTube 官方 RSS、oEmbed、公开视频页和 About 页复核 Venn Stories 当前 12 条与 LuluJAI 经期
  种子：窗口跨度 10.1 天，平均间隔 22.1 小时；频道 06-16 加入、已有 48 条，但 08-10 后截至观察日
  无新上传，只定义为高频冲刺，不外推长期日更。
- 12 条当前播放合计 101,999、中位数 366.5；体毛单条 93,976、占 92.1%，去掉后其余 11 条中位数
  262。经期种子 536,466，与体毛两条约占频道总播放 710,425 的 88.7%，高频供给仍高度依赖异常。
- 当前 12 张缩略图均为 1280×720、两个黄色大词和黑描边；10/12 为同类兽皮古人类场景，0/12 标题
  含具体文明、地点或时期。万亿富翁缩略图缺少所有格，旅行缩略图为不完整英语，固定两词仍需文字 QA。
- 11/12 有来源栏、至少 6/12 有不确定性语言、0/12 有章节，只有 1/12 提供直接外部来源链接；经期
  种子声明主张均有来源却没有公开来源清单或直链，来源流程仍是半可审计。
- 只保留“普遍日常疑问 + 极短视觉钩子 + 高频题库压力测试”为观察；私密身体题、羞辱式敏感画面、
  通用兽皮人设和日更节奏不升级规则。下一频道为 ThinkMan，策略记忆、Skill、六题排序、默认时长与
  生产流程不变。合同：`docs/contracts/sprint-167-youtube-venn-stories-channel-teardown.md`。

# Sprint 168 YouTube ThinkMan 当前窗口拆解（已完成）

- 用 YouTube 官方 RSS、oEmbed、公开视频页和 About 页复核 ThinkMan 当前 12 条；盐种子与窗口第 10 条
  重合，只计一次。窗口覆盖 05-30 至 08-10，跨度 72 天，平均 / 中位发布间隔 6.5 / 4.0 天；07-03 后
  基本收敛到约 4–5 天一条，定义为近期每周约两条，不能外推长期排期。
- 12 条当前播放合计 775,841、中位数 10,765.5；严寒 260,186、盐 222,859、糖 168,339，分别占
  33.5%、28.7%、21.7%，前三条合计 84.0%。盐不是单条带飞；但同为日常限制的铁、奶、石器求生三条
  合计仅 7,907，不能把高位簇泛化为所有资源题。
- 4/12 标题点名铁、奶、糖、盐，1/12 出现宽泛 `Stone Age`，0/12 点名文明、地点或遗址；对象具体性
  高于 Venn Stories，历史主体仍是 10/12 `Ancient Human(s)` 的通用问句。3/12 有明显英语语法问题。
- 12/12 官方缩略图均为 1280×720、黄色短字与同类黑轮廓兽皮卡通人；巨型糖晶体、开放火堆炼铁和无来源
  映射的精确数字存在机制错位 / 过度承诺风险。图片只在临时目录观察，没有提交第三方副本。
- 0/12 有正式来源栏或外部来源直链，只有关系题列出研究者姓名；4/12 有章节，至少 7/12 使用概率、
  可能或假说语言。只保留“熟悉基本物质 + 史前稀缺 / 生存后果 + 章节化解释”为候选观察；策略记忆、
  Skill、六题排序、默认时长与生产流程不变。下一频道为 Ink Explainer。合同：
  `docs/contracts/sprint-168-youtube-thinkman-channel-teardown.md`。

# Sprint 169 YouTube Ink Explainer 当前窗口拆解（已完成）

- 用 YouTube 官方 RSS、oEmbed、公开视频页和 About 页复核 Ink Explainer 当前 12 条；窗口覆盖 04-28 至
  08-07，跨度 101 天，平均 / 中位发布间隔 9.2 / 9.3 天，其中 7/11 个间隔为 8.9–10.1 天。
- 12 条当前播放合计 4,444,616、中位数 193,112；连续降雨与环球旅行两个 LuluJAI 锚点分别排第 1、
  第 4，合计占 42.8%。05-11 至 07-16 的连续 8 条全部超过 137,000，去掉最高单条后其余中位数仍为
  188,941，因此不是单条异常结构，但最新与最早各两条低位仍阻止“稳定基线”结论。
- 9/12 标题出现 `Human(s)`，3/12 点明技术 / 物质，2/12 点明环境限制，0/12 点名文明、地点、遗址或
  时期；细节集中在描述。至少 4 条有明显英语语法、大小写或标点问题。
- 12/12 缩略图均为 1280×720 且有顶部大字，但黄 / 白 / 黑红文字和人物画法并不完全统一。猛犸尸体
  住房与来源中的猛犸骨结构错位；疾病缩略图内嵌 `7:33`，与官方 8:03 时长不一致。图片只在临时目录
  观察，没有提交第三方副本。
- 11/12 有研究 / 来源块，最近 9 条连续给出外部直链，8/12 至少有学术或机构来源；最早三条没有可用
  直链，枪械来源主要为 Wikipedia。只保留“场景化限制 + 可点击来源 + 规律节拍”为候选观察，不更新
  策略记忆、Skill、六题排序、默认时长或生产流程。下一步先做前五张频道卡横向审计。合同：
  `docs/contracts/sprint-169-youtube-ink-explainer-channel-teardown.md`。

# Sprint 170 YouTube 前五频道横向审计（已完成）

- 对齐 Oddlyhuman、Pastly、Venn Stories、ThinkMan 与 Ink Explainer 五张频道卡，停止跨频道绝对播放
  排名；改按各自窗口识别单条异常、主题簇集中、宽分布低基线与连续高位带四种公开分布结构。
- 五个窗口共 57 条标题，47/57 直接使用 `Human(s)` 通用主体，只有 3/57 提供文明、地点或时期边界；
  共同供给模板已经拥挤，具体历史边界仍是明显空位。
- 视觉审计确认五者普遍使用短字、黑轮廓人物与单问题场景，但黄色字、兽皮人设、私密身体、暴力和猛犸
  不具备因果证据；错误时长、语法、无来源数字和视觉证据错位被列为发布前 QA 风险。
- 来源公开从 ThinkMan 0/12 直接链接到 Ink Explainer 9/12 差异明显。只迁移“限制入口—具体历史边界—
  机制物件—主张 / 来源 / 未知项”组合，不把链接数量、发布节奏或单条播放升级为规则。
- 依据既有 129 条标题暂缓 Basically Primitive、History Alive Animated、Axen 与 Zenn；Explain In Paint
  作为次级候选。下一张只拆 Buried Empires：它 0/12 使用通用人类主体、11/12 有明确历史边界，是唯一
  结构强对照，但 10/12 为战争 / 惩罚题，研究价值不等于产品适配。
- 新增 `channel-teardowns/five-channel-cross-audit.md`，同步更新拆解索引、YouTube 索引和研究日志；没有
  新抓取、实验、脚本、媒体或发布，策略记忆、Skill、六题排序与生产流程不变。合同：
  `docs/contracts/sprint-170-youtube-five-channel-cross-audit.md`。

# Sprint 171 YouTube Buried Empires 具体文明结构对照（已完成）

- 用 YouTube 官方 RSS、12 个公开视频页、About 页和 12 张临时缩略图完成 Buried Empires 当前窗口卡；
  频道当前显示 7.61K 订阅、2,535,485 总播放、132 条视频，窗口覆盖 07-08 至 08-08。
- 12 条时长 17:53–26:41、中位数约 23:57；0/12 使用 `Human(s)`，11/12 点名文明、人物或具体群体，
  确认它是通用古人类标题的强结构对照。
- 当前窗口播放合计 184,887、中位数 1,488.5；Sparta 懦夫单条 159,180、占 86.1%，前三条占 93.7%。
  另外两条 Sparta 和另外四条清单均未同步异常，不能把具体文明、清单或暴力强度写成增长原因。
- 10/12 为战争 / 惩罚；最新 9 张缩略图去掉文字并转向写实合成感的囚禁、处刑和惊恐人物。视觉中多项
  具体刑罚与精确温度没有在描述来源里定位，不迁移写实伤害包装。
- 12/12 有章节和命名来源栏、至少 7/12 使用证据边界语言，但 0/12 有来源直链、版本、页码或段落；
  只保留文明主体前置、来源反差入口和章节化因果链，作者名单不能替代主张映射。
- Buried Empires 触发预设停止规则：停止 Basically Primitive、History Alive Animated、Explain In Paint、
  Axen 与 Zenn 的机械补卡。下一步转入 Paynes Creek V1–V7 视觉来源与授权清单，仍不自动生成或发布。
- 新增 `channel-teardowns/buried-empires.md`，同步更新横向审计、拆解索引、YouTube 索引和研究日志；
  策略记忆、Skill、六题排序、默认时长与生产流程不变。合同：
  `docs/contracts/sprint-171-youtube-buried-empires-channel-teardown.md`。

# Sprint 172 YouTube Paynes Creek 视觉来源与授权清单（已完成）

- 为 Paynes Creek `V1–V7` 建立事实准确性与商业复用权双层矩阵；Natural Earth 公共领域底图可用于
  原创区域图，两篇 Cambridge 原始研究的 `CC BY 4.0` 图件可在按图号、创作者、DOI、许可和修改说明
  署名后作为可选真实证据插图。
- 2005 PNAS 船桨照片、AIA / LSU 网页图片、两篇 `CC BY-NC-ND` 论文图片和未确认开放商业许可的
  Elsevier 图片均不进入默认商业样片；本轮没有下载或提交任何第三方图片。
- `V1、V3、V7` 通过；`V2、V4、V5` 在明确“重建 / 可能”后通过；原 `V6 市场交换` 因具体路线、
  市场建筑、买家和价格未知而不通过，固定替换为海岸至未命名内陆节点的虚线网络图。
- 人物只保留低细节劳动剪影；同年代但异地、王室或神话类公共领域藏品不用于复原 Paynes Creek 盐工。
  整体视觉 Gate 有条件通过，下一步为逐镜证据板和 16:9 原创视觉规格，仍未进入脚本、媒体、实验、
  生成或发布，也未更新策略记忆与 Skill。合同：
  `docs/contracts/sprint-172-youtube-paynes-creek-visual-source-rights-ledger.md`。

# Sprint 173 YouTube Paynes Creek 12 镜证据板与 16:9 视觉规格（已完成）

- 把已通过来源与授权 Gate 的 V1–V7 收敛为 S01–S12：目标 138 秒、交付目标 1920×1080、每镜一个主张，
  并逐项绑定 F / S / R 来源、证据等级、画面构图、运动预设、允许项与禁止项。
- 原 V6 具象市场戏继续禁止，S10 只保留带证据断点的海岸—未命名内陆方向网络；S03、S07、S09、
  S10 的重建、可能和具体未知限制固定进入未来旁白与字幕。
- 对照当前代码确认：12 Scene、统一 16:9 和有限平移 / 缩放可直接执行；中文 Seed-TTS 与 Whisper zh
  可做本地验证，英语原声、独立标签 / 署名层、YouTube 16:9 账号画风和公开发布仍未通过。
- 新增 Markdown 权威规格与无外部网络依赖的 HTML 阅读板；浏览器在 1440×960 和 390×844 视口确认
  12 镜、138 秒、零控制台错误、零页面横向溢出，移动端兼容表按逐项账本重排。
- 根目录新增 `PRODUCT.md` 记录产品、用户、能力、证据与开放决策；YouTube 研究板的专用视觉系统记录在
  `docs/strategy/youtube/DESIGN.md`，避免误写成整个 DoodleStory UI 的全局设计身份。
- 内置构图探针两次因图片服务网络错误未返回，未切换到需要 API Key 的备用路径，也未伪造批准图；实际
  HTML 仍完成桌面 / 手机两轮检查、一次 detector 与修复后复拍。
- 本 Sprint 未写最终旁白，未生成图片、语音、字幕或视频，未创建 DoodleStory、实验或发布任务，也未
  更新策略记忆或 Skill。合同：
  `docs/contracts/sprint-173-youtube-paynes-creek-shot-evidence-board.md`。

# Sprint 174 YouTube Paynes Creek 中文旁白与逐镜 Prompt 包（已完成）

- 正式选定“考古证据驱动的古代技术与日常生活机制可视化”为首个实际制作赛道，第一条继续使用已通过
  来源与授权 Gate 的 Paynes Creek 玛雅盐业；当前只做中文本地生产验证，不建立 YouTube 市场实验。
- 定稿 S01–S12 共 536 个汉字；固定中文 `speed=1.0`，按每秒约 4 个汉字估算约 134 秒，目标时间带仍为
  138 秒。真实总时长必须在 TTS 返回后按 `duration_ms` 复核，并落在 120–150 秒。
- S03 明说依据遗迹和类比的“重建”，S07 保留盐饼“可能”并否定通用货币，S09 明说没有逐船货单，
  S10 明说路线、城市和买家未知；四处限定词会进入 TTS 原文与校准字幕。
- 新增 12 段自包含英文图片 Prompt；统一写入考古证据台视觉、中央 84% / 上方 70% 安全区、无画内文字
  和逐镜历史禁止项，可直接用于当前只有 `prompt` 与 `provider` 参数的 `generate_image`。
- 依据用户限定的 SiliconFlow 免费模型范围，专用 Style 草案只选 `Qwen/Qwen-Image`、`16:9`；不绑定
  生产账号，不添加第三方参考图，也不授权 Provider 失败后的自动切换。
- 进一步代码核对纠正了 Sprint 173 的尺寸假设：统一 Gateway 对 `16:9` 当前请求 `1792×1024`，Native
  Remotion 输出又直接跟随首图真实宽高，不会自动标准化为 1920×1080。因此下一步只允许生成 S03
  一张候选，先核验真实尺寸、对象锚点、重建语言和字幕安全区，未通过前不批量生成。
- 新增 `paynes-creek-chinese-script-prompt-pack.md` 与无媒体 ID 的
  `paynes-creek-production-draft.json`；本 Sprint 没有调用图片、TTS、Whisper 或 Remotion Provider，
  没有创建 Style、Run、实验或发布任务，也没有更新策略记忆与 Skill。合同：
  `docs/contracts/sprint-174-youtube-paynes-creek-chinese-script-prompt-pack.md`。

# Sprint 175 YouTube Paynes Creek S03 单镜真实媒体 Gate（已完成：stop_before_batch）

- 建立 Windows Python 3.11 隔离运行环境并完成迁移；按仓库配置启动本地 MLflow 与 FastAPI，两个
  health endpoint 均通过，startup 恢复扫描为 0 个待恢复 Native Run。
- 修复单实例锁的 Windows 导入阻塞：Windows 使用 `msvcrt` 非阻塞文件区间锁，POSIX 保持 `flock`；
  PID 元数据仍可读取，首实例释放后可重获，第二个真实子进程竞争明确失败。6 项聚焦测试通过。
- 在本地验证库创建 `Paynes Creek Evidence Desk 16:9` Style：`Qwen/Qwen-Image`、`16:9`、Prompt
  模式、零参考图；发布只授权 `generate_image`、`inspect_image` 的 S03 最小 Skill。
- 唯一一次 Native Run `de8b148d122343fd984a9d646801c12b` 在 Agent 首轮文本规划时失败：
  `gpt-5.5` 经当前火苗兼容地址返回 429 `usage_limit_reached`。数据库确认模型调用 1、图片调用 0、
  Step 0、图片 / 资产 / 语音 / 字幕 / 视频 0，没有发生 Qwen-Image 请求或生图扣费。
- 严格执行失败即停，没有重试、切换 Agent / 图片 Provider 或创建第二个 Run。因为没有图片，真实尺寸、
  `inspect_image` 和人工视觉复核均标为不适用，Gate 结论固定为 `stop_before_batch`。
- 新增 `paynes-creek-s03-media-gate.md` 并同步 YouTube 索引、Prompt 包与研究日志；不更新策略记忆或
  内容 Skill。下一步须先恢复当前 Agent 模型额度，或由用户批准独立模型路由兼容性 Gate。合同：
  `docs/contracts/sprint-175-youtube-paynes-creek-s03-media-gate.md`。
- 验证：锁聚焦测试 6/6、真实第二 Uvicorn 启动阻断、compileall、Alembic head 与控制器校验通过。
  全量后端运行 380 项，Windows 上仍有 8 个临时 SQLite / MLflow 文件句柄清理 error 和 1 个 Whisper
  POSIX 路径 assertion failure；与本轮改动无直接重叠，已记录但未扩项修复。

# Sprint 176 SiliconFlow Native Agent 兼容性决策（已完成：adapter_required）

- 交叉审计当前代码、已安装 `openai-agents==0.18.3` 源码与 SiliconFlow 官方文档，确认 Native Agent
  当前固定使用火苗 `/v1/responses`；`SILICONFLOW_*` 只进入既有 Chat Completions / 多媒体直连，
  不能通过替换 Base URL 直接接管 Native Loop。
- SiliconFlow 官方公开 Function Calling 使用 `/v1/chat/completions`；模型中心将当前已配置且在用户
  允许清单内的 `deepseek-ai/DeepSeek-V3.2` 标为支持工具调用，因此保留为第一且唯一真实 Gate 候选。
- 已安装 Agents SDK 可用 `OpenAIProvider(use_responses=False)` 建立 Chat Completions 模型，并把工具流
  转成现有事件处理器依赖的 `response.*` 事件；静态结论为 `adapter_required`，不等于生产兼容。
- 识别关键阻塞：官方 Chat API 把 `messages` 记录为 1–10 条，当前数据库 Session 完整重放所有 Item、
  Runner 最多 12 回合。真实 Gate 必须验证 10 / 11 条边界；若硬限制导致失败，不得截断或摘要绕过。
- 将“免费模型”表述校正为用户账号额度 / 运营白名单；官方公开价格页对 V3.2 输入输出列有非零价格，
  真实调用前仍需从账号侧确认额度。本轮没有读取账单、修改配置、调用模型或重试 S03。
- 新增 `siliconflow-native-agent-compatibility-decision.md`，同步出站调用清单、S03 Gate、YouTube 索引与
  研究日志。下一步需用户批准显式 Chat Completions 路由开发和零媒体兼容性 Gate；通过前
  `stop_before_batch` 保持有效。合同：
  `docs/contracts/sprint-176-siliconflow-native-agent-compatibility-decision.md`。

# Sprint 177 SiliconFlow Native Agent 适配实施蓝图（已完成：design_ready）

- 继续逐行审计当前安装的 `openai-agents==0.18.3` Chat Stream Handler，确认其每个 Chat Response 与
  Function Item 都复用固定 `__fake_id__`，真实 completion ID 只在流后段进入
  `provider_data.response_id`，且不会发当前持久化逻辑等待的
  `response.function_call_arguments.done`。
- 对照现有 Native Loop 证明直接切 `use_responses=False` 会产生两个确定性错误：第二模型回合与第一
  Step 幂等键冲突；同一响应中的多 Tool 参数因共享 Item ID 相互覆盖。适配器必须用应用侧
  `run + execution_attempt + call ordinal` 生成模型调用身份，按 `output_index → tool_call_id` 缓冲参数，
  并在 `output_item.done` 合成参数完成事件。
- 识别并纳入实施范围的既有路由快照缺口：`AGENT_MODEL` 同时服务旧 Router 与 Native Agent；Run 只存
  模型名，执行却继续读当前环境模型，Follow-up 也没有 Provider / API shape 快照。蓝图固定采用原子
  Run 级 route ID、独立 Native 模型配置、四字段路由快照、历史 `huomiao_responses` 回填和完整继承。
- 明确 Chat Tool Output 边界：`generate_image` 的图片部分不会被 V3.2 看见，首个
  `siliconflow_chat_v1` 能力 Profile 只允许 S03 的 `generate_image + inspect_image`，模型只收
  `image_id` 文本并读取视觉检查文本结果；文章多 Agent、YouTube 频道看图、发布和其他 Skill 继续禁止。
- 消息边界改为按 SDK Converter 生成并插入 system 后的最终 Chat messages 计数；生产 wrapper 在超过
  10 条时明确失败，不截断或摘要，独立真实 Gate 再测试 Provider 的 10 / 11 条行为。
- 新增实施蓝图、Sprint 合同和独立架构 SVG / 2960×1960 PNG，并同步修正 Sprint 176 决策、全量端点
  清单、S03 Gate、YouTube 索引与研究日志中“现有事件处理器原则上无需重写”的过度判断。本轮没有
  修改配置、代码或数据库，没有调用模型、图片或媒体 Provider；控制器校验保持通过，S03 仍为
  `stop_before_batch`。合同：
  `docs/contracts/sprint-177-siliconflow-native-agent-adapter-blueprint.md`。

# Sprint 178 YouTube 首片赛道定案与 Paynes Creek 生产控制台（已完成：lane_selected）

- 把长期 YouTube 研究正式收敛为首个实际制作赛道：“考古证据驱动的古代技术与日常生活机制解释”；
  第一条继续固定为 Paynes Creek 玛雅盐业中文本地生产验证，明确生产适配度已具备、市场适配度未验证。
- 新增 `paynes-creek-production-control-room.md` 权威运行手册，汇总 12 镜、138 秒计划、536 字旁白、
  12 段 Prompt、来源 / 权利、S03 429 和媒体全 0 的真实状态，并列出发布前 owner、审核、成本与回流空位。
- 新增无外部资源的响应式 HTML 生产控制台，以影片接触印样和制作登记账本呈现十二镜、唯一故障、
  G0–G9、产物导航与停止条件；Gate 筛选支持已通过、当前下一步、未开放和全部状态。
- 生产顺序固定为离线适配 G2 → 独立零媒体 G3 → 一张 S03 G4 → S01 / S04 视觉锚点 → 余图 →
  语音字幕 → 本地成片 → 发布准备；G2、G3、G4 不得合并授权或验收。
- 本轮没有修改 `.env`、运行时代码、数据库或 Provider，没有模型、图片、VL、TTS、字幕、视频或发布调用；
  `strategy_memory.md` 和 Skill 不更新，S03 保持 `stop_before_batch`。
- 浏览器在 1440×960 与 390×844 完成两轮检查：12 镜、10 个 Gate、四种筛选状态、Skip Link、
  reduced motion、打印样式、本地链接、控制台错误和页面横向溢出均通过；Impeccable detector 仅报告现有设计侧车
  未覆盖的颜色 / 字号 advisory。独立终审指出 Gate 数量文案与首屏状态对比度两项问题，修复复拍后
  最终 disposition 为 `PASS`，无 material open item。合同：
  `docs/contracts/sprint-178-youtube-paynes-creek-production-control-room.md`。

# Sprint 179 Paynes Creek S03 单镜重试证据包（已完成：ready_as_template）

- 对照当前 Native Runtime 源码固定未来 `inspect_image` 的真实输入与输出：当前 Run 的单张 `image_id`、
  1–10 个不重复 checks、预期对象，以及 `accept / revise / ask_user / blocked`、逐项分数、issues、
  Provider、模型与延迟；机器 verdict 不替代人工事实和视觉复核。
- 新增 `paynes-creek-s03-retry-protocol.md`，把 G2、G3、G4 拆成硬前置条件，并将一次 G4 限定为一个
  Run、最多一次生图、一张候选、一次 VL、事实复核一次和视觉复核一次；任何失败都保留证据并停止。
- S03 完整 Prompt 以 UTF-8、LF、无末尾换行锁定 SHA-256
  `3cd1a0820096f3b3804aad06ced282265559adf40460401a6b0b47f980303729`；执行前哈希不一致必须返回输入评审，
  不在媒体 Gate 内修改 Prompt。
- 新增 `paynes-creek-s03-gate-evidence-template.json`，预置 Scene、事实 / 来源 / 权利、构图、运动和机器
  checks；所有未运行字段保持 `null` 或 `not_run / not_reviewed`，不伪造 Run、资产、尺寸、成本或 verdict。
- 通过条件固定为机器 `accept` + 事实人工 `pass` + 视觉人工 `pass`；只有三者齐全才可写
  `PC-S03-approved.png` 并开放 G5 的 S01 锚点评审，不能自动进入 S04、余图或媒体批量生产。
- 同步生产控制室、YouTube 索引、研究日志和根 README。本轮未批准或实施 G2，没有外部模型、图片、VL、
  TTS、字幕、视频或发布调用，没有修改配置、数据库、运行时代码、策略记忆或 Skill。合同：
  `docs/contracts/sprint-179-youtube-paynes-creek-s03-retry-evidence-packet.md`。

# Sprint 180 SiliconFlow Native Agent 零媒体 Gate 证据包（已完成：protocol_ready）

- 重新核对当前仓库确认 G2 仍未实现：Native Run 不含 route / provider / API shape 快照，运行时固定
  `use_responses=True`，Chat Event Adapter、转换后消息计数 wrapper 和 G3 脚本均不存在；因此本轮只冻结
  未来执行协议，不产生兼容性通过结论。
- 新增 `siliconflow-native-agent-zero-media-gate-protocol.md`，把 G3 收敛为四个用例、最多 5 次请求：
  普通文本 1 次、单 Tool + 跨 Python 子进程恢复 2 次、转换后 10 条消息 1 次、测试专用 11 条 Provider
  边界探针 1 次；所有请求 retry 0、fallback 0、thinking 关闭、stream buffer 关闭。
- 测试专用 `echo_probe` 固定为无网络、无文件、无随机状态的确定性 Tool；Tool + 恢复用例必须只执行
  一次，并证明两个模型调用身份 / Provider ID 不冲突、参数 delta 与最终参数一致、已完成 Tool 不重复。
- 11 条消息只允许在先证明生产 wrapper fail-closed 后，由测试脚本专用 boundary client 绕过本地上限
  探测一次。Provider 接受或有完整请求标识的结构化拒绝都记录，但生产 route 继续保持 10 条上限。
- 新增 `siliconflow-native-agent-zero-media-gate-evidence-template.json`，覆盖前置 G2 / 授权 / 成本、固定
  Profile、四个 case、Step / Event / Session 交叉核对、媒体全 0 和脱敏检查；未运行值保持 `null` 或
  `not_run`，不伪造调用、usage、余额、成本或 verdict。
- Gate 只允许 `pass_for_s03_single_image_review` 或 `stop_before_media`；通过也只开放 G4 单图授权评审。
  同步架构蓝图、兼容性决策、生产控制室、S03 重试协议、YouTube 索引、研究日志和根 README。
- 本轮没有修改运行时代码、配置、数据库、迁移、默认路由、策略记忆或 Skill，没有调用 SiliconFlow、
  图片、VL、TTS、字幕、视频、发布或账单接口。合同：
  `docs/contracts/sprint-180-siliconflow-native-agent-zero-media-gate-evidence-packet.md`。

# Sprint 181 Native Agent Run 路由快照基础（待批准：未实施）

- 对照当前代码确认模型漂移点：新 Run 从 `settings.agent_model` 写 `model_snapshot`，但执行、文章 Compiler、
  Director / Writer / Reviewer、Agent 与 trace 又重新读取当前环境；排队或恢复前修改配置会让快照与执行
  事实不一致。Follow-up 也只继承模型名，没有 route / provider / API shape。
- 将 G2 离线实现拆成串行 G2-A / G2-B。待批准的 Sprint 181 只做 G2-A：新增
  `huomiao_responses / huomiao / responses / model` 四字段 Run 快照、历史迁移、Provider factory、API 读取、
  Follow-up / retry / recovery 继承和全链路只读快照。
- G2-A 保持唯一可执行路由为当前火苗 Responses，不增加 `siliconflow_chat_v1`、`use_responses=False`、
  Chat Event Adapter、Tool Output policy、capability profile 或消息 wrapper；这些留给 G2-B 的独立合同。
- 合同指定下一 revision `v3w4x5y6z7a8`：历史三字段固定回填当时唯一代码路径，原
  `model_snapshot` 不改；字段最终非空且不保留 server default，不新增无查询依据的索引。
- 新 Native 模型配置不从旧 `AGENT_MODEL` fallback；旧字段继续服务 `AgentModelRouter`。配置错误必须在
  Run 写库和 enqueue 前以安全 HTTP 503 失败，不创建半成品 Workflow 或 Item。
- 当前只新增并同步待批准合同、适配蓝图、生产控制室、YouTube 索引与研究日志；没有修改运行代码、配置、
  迁移、数据库或 `docs/spec.md`，没有外部调用。合同：
  `docs/contracts/sprint-181-native-agent-run-route-snapshot-foundation.md`。

# Sprint 182 YouTube Paynes Creek 本地样片验收包（已完成）

- 新增 `docs/strategy/youtube/paynes-creek-local-pilot-charter.md`，把首片固定为一轮
  `local_production_validation`：唯一变量是把锁定纸面生产包推进到真实媒体，不在同一 attempt 修改题目、
  脚本、画风规则、模型、Provider、时长目标或发布包装。
- 将最终成片验收收敛为四项：视觉证据连续性；脚本、来源、限定词与 120–150 秒节奏；中文专名、语音、
  字幕同义性与安全区；1920×1080 / 30 fps 渲染、完整播放和 Run / Step / Tool / Asset 可追溯性。
- 新增 `paynes-creek-local-pilot-acceptance-template.json`，所有真实媒体、时长、尺寸、调用计数、审核人与
  verdict 保持 `null / not_run / not_reviewed`；当前不伪造任何生产结果。
- 只有 G0–G8 和四维验收全部通过才允许 `pass_local_pilot`；该状态不构成 YouTube 市场结论，也不自动
  开放 G9、批量生产、公开发布或 Skill 规则升级。
- 更新生产控制室 Markdown / HTML、YouTube 索引、研究日志与根 README；HTML 新增可直接阅读的四维
  验收区，并把旧 G2 总体文案修正为当前待批准的 G2-A 与后续独立 G2-B。
- 本 Sprint 只新增文档和空白模板；未批准或实施 G2-A，没有运行时代码、配置、迁移、数据库、模型、媒体、
  发布或账单调用。合同：
  `docs/contracts/sprint-182-youtube-paynes-creek-local-pilot-acceptance-packet.md`。

# Sprint 183 YouTube Paynes Creek Style 状态对账（已完成）

- 以仓库本地验证库的只读连接复核 `Paynes Creek Evidence Desk 16:9`：Style 记录已存在且为
  `active / prompt / Qwen/Qwen-Image / 16:9`，参考图 0、Style Test 0、生成任务 0、关联 Native 图片 0、
  YouTube 频道绑定 0；本地 Style ID 只作为 lineage，不代表其他环境存在同一记录。
- 新增 `paynes-creek-style-state-audit.md`，把记录已创建、配置已启用、媒体输出已验证和频道绑定四层状态
  分开；明确当前 `active` 只满足配置启用条件，不能证明 Provider 调用、真实尺寸、构图、画风或人工验收。
- 将 `paynes-creek-production-draft.json` 升级为 schema v2，用 `style_snapshot` 取代歧义的
  `style_draft / binding_created`，保存 Style Prompt 字符数、SHA-256、测试 / 媒体 / 绑定计数和只读审计范围；
  下一动作改为先完成 G2-A、G2-B、G3，再单独授权 G4 并重新解析现有 Style。
- 同步 Prompt 包、生产控制室、S03 重试协议、YouTube 索引和根 README；未来 G4 必须重新核对 Style ID、
  状态、模型、比例、Prompt 哈希和参考图数量，任一变化即 `blocked_precondition` 并新建 attempt，不能自动
  重建 Style 或沿用旧本地 ID。
- 样片验收模板去掉会随文档提交自我过期的单一 Git commit 字段，改为逐文件 SHA-256 快照；五个锁定输入
  哈希全部重算匹配。两个 JSON 解析、内容控制器状态、本地链接、新增内容凭据扫描和 `git diff --check`
  均通过。
- 本 Sprint 未批准或实施 G2-A，未写数据库，未创建 / 修改 / 测试 Style，没有模型、图片、VL、TTS、字幕、
  视频、发布或账单调用。合同：
  `docs/contracts/sprint-183-youtube-paynes-creek-style-state-reconciliation.md`。

# Sprint 184 YouTube Paynes Creek G5 串行视觉锚点 Gate（已完成）

- 将 G5 umbrella 拆成两个不可合并的单图 Gate：G5-A 只生成和验收 S01 抽象地图，完整通过后写
  `pass_for_s04_anchor` 并停止；G5-B 另行授权 S04 陶器 / 火候图，通过后写
  `pass_for_remaining_image_plan` 并停止，仍不自动进入 G6 余图。
- 新增 `paynes-creek-g5-serial-anchor-protocol.md`，为每个子 Gate 固定一个 Run、一次生图、一张候选、
  一次 `inspect_image`、一次事实复核、一次视觉复核和独立成本 / 授权；失败不在同一 attempt 生成 v02。
- 新增机器可读 `paynes-creek-g5-anchor-profiles.json`：锁定 S01 / S04 Scene、Prompt SHA-256、前置 Gate、
  1–10 项合法 VL checks、人工检查 ID、尺寸 / 运动规则、通过状态和后继评审；Profile 规范 SHA-256 为
  `4987a38eb97466fdf9f3c8d4c7202e8b6aae304c7d22add3a3cad1b0a8bf86a9`。
- 新增通用空白 `paynes-creek-g5-anchor-attempt-template.json`，未来每个子 Gate 复制成独立不可覆盖记录；
  所有 Run、调用、资产、尺寸、机器与人工结果保持 `null / not_run / not_reviewed`，未伪造媒体事实。
- 对照 Remotion 实现纠正 S01 运动能力边界：`zoom_in` 只以 `center center` 从 `1.00` 缩放到 `1.08`，
  不能把变换原点移向泻湖。G5-A 用原图和末帧探针验证可读性，失败时记录 capability mismatch，不在
  当前 Gate 改 motion 或代码。
- 锚点门槛要求真实像素尺寸与已批准前序图完全相同，并另行记录当前 Remotion `0.01` 比例差容差；
  Gateway 1792×1024 请求目标和 1920×1080 交付目标都不能冒充真实输出。
- 同步逐镜证据板、生产控制室、样片章程、YouTube 索引和研究日志；重算样片验收模板中的证据板哈希。
  两个 JSON、两个 Prompt 哈希、Profile 哈希、锁定输入和内容控制器状态均通过验证。
- 本 Sprint 未批准或实施 G2-A，没有运行时代码、配置、数据库、Style、模型、图片、VL、语音、字幕、
  视频、发布或账单调用。合同：
  `docs/contracts/sprint-184-youtube-paynes-creek-g5-serial-anchor-gates.md`。

# Sprint 185 YouTube Paynes Creek G6 九镜串行生产设计（已完成）

- 将 G5-B 后的 S02、S05–S12 从一个“剩余图片”批次拆成九个不可合并的单图 Gate，生产顺序固定为
  S02 → S08 → S11 → S05 → S09 → S07 → S06 → S10 → S12；成片仍按 S01–S12 播放。
- 新增 `paynes-creek-g6-serial-production-protocol.md`，用依赖、视觉新颖度、事实漂移风险与失败成本解释顺序；
  每镜只允许一个 Run、一次生图、一张候选、一次 `inspect_image`、一次事实复核与一次视觉复核，首个失败
  阻断所有后继镜头，通过也只开放下一镜的授权评审。
- 新增 `paynes-creek-g6-scene-profiles.json`，锁定九镜 Scene、Prompt SHA-256、前序 Gate、approved 前序图、
  1–10 项机器检查、人工检查、尺寸 / 运动规则与唯一通过状态。Profile 规范 SHA-256 为
  `56f5ea4b77908f2af5c10af7822d38b3a68f7bc36b30e4358f64a463618b87bf`。
- 新增通用空白 `paynes-creek-g6-scene-attempt-template.json`；所有 Run、调用、资产、尺寸、机器与人工结果
  保持 `null / not_run / not_reviewed`，没有伪造图片或审核事实。
- 纠正生产控制室中 S07 / S08 / S10 / S11 / S12 的时长与 S11 主张；S11 恢复为“遗址后来被淹没，
  泥炭保存木柱与布局”，不再误写成交换解释。
- 消除 S08 证据板与 Prompt 冲突：一米四三只由旁白 / 字幕承载，画面改为无标签全长线与无标签轴径
  剖面，不要求生图模型生成 `1.43`、`5 cm` 或单位；重算本地样片验收模板锁定哈希。
- 同步 G6 协议、Profile、模板、生产控制室 HTML、样片章程、YouTube 索引、研究日志与根 README，并对
  HTML 做桌面 / 移动端检查与 Impeccable 机械检测。
- 本 Sprint 未批准或实施 G2-A，没有运行时代码、配置、数据库、Style、模型、图片、VL、语音、字幕、
  视频、发布或账单调用。合同：
  `docs/contracts/sprint-185-youtube-paynes-creek-g6-serial-scene-production.md`。

# Sprint 186 YouTube Paynes Creek G7 语音字幕与跨 Run 边界（已完成）

- 代码审计确认当前 `generate_subtitles` 只接受本 Run Audio，`render_story_video` 也只查询本 Run 的 Audio /
  Subtitle；Follow-up 会创建新 Run，现有等待输入只覆盖文章审批和图片质量。因此“12 镜逐镜独立人工试听
  → 独立 G8 成片 Run”目前无法执行。
- 新增 `paynes-creek-g7-audio-subtitle-protocol.md`，把 G7-0 固定为真实语音前置：未来 G8 只允许解析同一
  Native Conversation 中成功来源 Run 的音频 / 字幕，校验 owner、来源 Run、字幕—音频配对并保存 lineage；
  不复制资产、不跨 Conversation，也不把全部语音与渲染塞进一个 Run 绕过人工 Gate。
- G7 风险顺序固定为 S01 → S02 → S08 → S03 → S07 → S09 → S10 → S11 → S12 → S04 → S05 → S06，
  先验证“佩恩斯克里克”“伯利兹南部”“公元六百到九百年”“一米四三”，再验证重建、可能、不等于、
  没有、未知和后来淹没等边界词。
- 新增 `paynes-creek-g7-scene-profiles.json`，锁定 12 段旁白 UTF-8 SHA-256、火山
  `seed-tts-2.0-standard` / 固定音色 / MP3 24 kHz / speed 1.0、Whisper `zh` 词级时间戳、原文对齐、
  必听片段、字幕保留片段和串行通过状态。Profile 规范 SHA-256 为
  `b628c128bb857cf6008d9dcf5e6d564a01b3f036f7285c4b633aa6bd09054277`。
- 新增通用空白 `paynes-creek-g7-scene-attempt-template.json`，未来每镜记录一个 Run、一次 Speech、一次
  Subtitle、真实时长、文件哈希、cue 校验、人工试听与 G8 来源 Run；未观测结果保持
  `null / not_run / not_reviewed`。
- 字幕成功只证明原文与时间轴通过算法门槛，不能证明 TTS 读音正确；具体对齐率当前不持久化，模板明确
  禁止伪造。G7-12 只有 12 镜全部通过且真实总长为 120–150 秒才开放 G8 计划评审。
- 同步产品规格、生产控制室 Markdown / HTML、本地样片章程与验收状态、YouTube 索引、研究日志与根
  README；G7 标记为 `blocked by G7-0`，不把 Profile 写成可执行授权。
- 本 Sprint 未批准或实施 G2-A / G7-0，没有运行时代码、配置、数据库、模型、语音、Whisper、字幕、视频、
  发布或账单调用。合同：
  `docs/contracts/sprint-186-youtube-paynes-creek-g7-audio-subtitle-boundary.md`。

# Sprint 187 Native Agent 同会话跨 Run 媒体 Lineage（设计就绪，未授权实施）

- 复核 `_resolve_video_inputs()`、Audio / Subtitle / Video 实体、API 投影和现有测试，确认 G7-0 只需扩展
  `render_story_video` 的输入解析：`NativeAgentVideo.scenes_json` 已能承载新增来源快照，不需要数据库迁移、
  API endpoint、前端或新索引。
- 新增 `docs/architecture/native-agent-cross-run-media-lineage-blueprint.md`，固定资格公式：当前渲染 Run
  保持现有行为；历史媒体只接受同 Native Conversation、同 owner 且状态为 `succeeded` 的来源 Run。
  Admin 读取能力不构成跨 owner 渲染授权，未知 / 越权 / 未成功来源使用不泄露存在性的统一错误。
- 固定 Tool 输入不增加来源 Run ID，由服务端从 Image / Audio / Subtitle 记录推导；持久化 Subtitle 必须同时
  满足 `subtitle.audio_id == audio.id` 与 `subtitle.run_id == audio.run_id`，不能只依赖现有外键。
- 新视频 Scene 快照计划增加 `image_source_run_id`、`audio_source`、`audio_source_run_id`、
  `subtitle_source`、`subtitle_source_run_id`；Generation Task 图片和内联字幕使用明确来源类型并保存空 Run ID，
  历史视频不回填。
- 新增 `docs/contracts/sprint-187-native-agent-cross-run-media-lineage.md`，把成功、拒绝、当前 Run 回归、
  所有非成功状态、跨 Conversation、跨 owner、两类字幕错配、快照持久化、幂等和 renderer 零调用收敛为
  聚焦测试矩阵。
- 本轮只形成可审核设计，没有修改运行代码、配置、实体、迁移、API 或 Skill，没有调用模型、图片、VL、
  TTS、Whisper、Remotion、YouTube 或账单接口。Sprint 187 未授权，当前实际开发入口仍是 Sprint 181 /
  G2-A。

# Sprint 188 Native Agent YouTube 1080p 固定渲染 Profile（设计就绪，未授权实施）

- 代码审计确认新的 G8 硬边界：图片 Gateway 对 16:9 当前请求 1792×1024，而
  `narrated-panel-v1` Composition 跟随首图真实尺寸；本地样片却锁定精确 1920×1080。因此即使 G7-0 和
  12 组媒体全部通过，当前 G8 仍不能保证交付规格。
- 新增 `docs/architecture/native-agent-youtube-1080p-render-profile-blueprint.md`，保留现有 source 模板并设计
  顶层枚举 `output_preset=source | youtube_16_9_1080p`。新 preset 使用版本化
  `narrated-panel-16x9-1080p-v1`，不接受任意尺寸、模板、裁切、fps、codec 或 CSS。
- 固定 16:9 来源 Gate：相对 16:9 偏差不超过 2%、Scene 间比例差不超过 0.01、等比 cover 的基准中心
  裁切每边不超过 1%。1792×1024 对应上下各 8 px / 0.78125%，不拉伸、不补黑边，也不放宽既有
  zoom / pan 的逐镜安全区审核。
- 新 Profile 在持久化前必须用现有显式 `FFPROBE_EXECUTABLE` 核对真实 MP4：一个 H.264 / yuv420p
  1920×1080 30fps 视频流、一个 AAC 音频流、正时长且与帧数一致；任何 probe 或 Node 元数据冲突都失败，
  不保存 Video / FileAsset，不使用 stdout fallback。
- 新增 `docs/contracts/sprint-188-native-agent-youtube-1080p-render-profile.md`，把双模板注册、manifest 尺寸
  配对、crop 数学、真实文件 probe、preset 幂等、持久化快照和无网络校准 smoke 收敛为一个实现切片。
- 同步规格、YouTube 导航、本地样片章程 / 验收模板和 G7-0 流程图；验收模板升至 schema version 2，新增
  G8-A、固定 preset / template 以及“无未批准裁切”的机器字段。本轮没有修改运行代码或调用任何模型、
  媒体、发布 / 账单接口；当前开发入口仍是 Sprint 181 / G2-A。

# Sprint 189 Native Agent 冻结 Render Manifest Run（设计就绪，未授权实施）

- 代码审计确认当前参数化 `render_story_video` 只在模型发起 Tool Call 后把 Scene 参数写入 Step / Item；它能
  证明模型最终传了什么，不能证明认证用户事先批准了哪一版 12 组媒体，也不能阻止模型转抄时改变顺序、
  Motion、字幕或 output preset。
- 新增 `docs/architecture/native-agent-frozen-render-manifest-run-blueprint.md`，设计 Run 创建时由服务端批量解析
  同 owner、同 Conversation、`succeeded` 来源 Run 的 Native 图片 / 音频 / 字幕，核对图片
  `inspect_image=accept`、Audio / Subtitle 配对、Asset 元数据和 cues，再编译 canonical JSON 与 SHA-256。
- 设计只读 preview 先返回 canonical snapshot / SHA-256，不写库、不 enqueue；认证用户检查后，Run Create
  携带 expected hash，服务端在创建事务内重新编译且完全一致才保存。Run 计划增加 Manifest snapshot /
  hash / authenticated confirmer / server confirmation time 四字段与全空 /
  全非空约束；历史 Run 不回填，不增加索引。专用 `youtube-frozen-render` Skill 的 Tool 集必须恰好为
  `render_story_video`，Manifest-bound Run 只暴露零参数 Schema，并禁止 Follow-up 或发布上下文。
- 运行时在 Node 前复验 snapshot hash、数据库 lineage 和 materialized 文件真实 SHA-256，再把固定 Scene
  顺序与 `youtube_16_9_1080p` 交给 Sprint 188 renderer；同一 Manifest Run 即使使用不同 Tool Call ID 也只
  允许一次 Render，成功只产生 `rendered_awaiting_frame_evidence`，不自动写 `pass_local_pilot`。
- 新增 `docs/strategy/youtube/paynes-creek-g8-render-manifest-protocol.md`、12 镜空白 Manifest 模板和空白 G8
  attempt，固定 S01–S12 成片顺序、G4–G7 review ref 映射、单次渲染预算、自动证据、抽帧交接和人工完整
  观看终态；所有真实媒体 ID、hash、Run 与 reviewer 保持 `null / not_run / not_reviewed`。
- 新增 `docs/contracts/sprint-189-native-agent-frozen-render-manifest-run.md`，把 Schema、只读 preview、专用
  Skill、migration、canonical 编译、exact hash 确认、零参数 Tool、文件 hash 复验、幂等 / 恢复和安全错误
  收敛为一个实现合同；同步规格、根
  README、YouTube 导航、生产控制室 Markdown / HTML、本地样片章程与 schema version 3 验收模板。
- 本轮没有修改运行代码、数据库、配置或 Skill，没有调用模型、图片、VL、TTS、Whisper、Remotion、
  ffprobe、发布或账单接口；Sprint 189 未授权，当前实际开发入口仍是 Sprint 181 / G2-A。

# Sprint 190 Native Agent 成片逐镜帧证据包（设计就绪，未授权实施）

- 代码审计确认 G8 仍缺一层独立证据：ffprobe 只能证明文件结构，冻结 Manifest 只能证明批准输入，二者都
  不能证明 Scene 实际顺序、Motion 安全端点、限定词字幕帧、意外空白或完整解码；同时当前模板主动把每镜
  首尾各 8 帧淡成黑色，不能使用“发现黑帧即失败”的粗糙规则。
- 本机 ffmpeg / ffprobe 8.0.1 无网络合成校准证明单次 `select` 能精确提取 0 / 8 / 中点 / 倒数第 9 / 末帧；
  首尾 endpoint PNG 正确呈黑，但 `blackdetect` 没有报告 EOF 片尾黑段。因此固定端点 PNG 与亮度统计是必要
  证据，`blackdetect` 只保留为辅助观察。
- 新增 `docs/architecture/native-agent-video-frame-evidence-pack-blueprint.md`：把抽帧从 Render Tool 分离为
  owner-scoped、数据库持久化、默认并发 1 的小型后台作业。有效 MP4 一经保存保持不变；Pack 失败不触发
  重渲染或自动重试，重启中断明确失败，人工可用新 key 和 `previous_pack_id` 建立不可覆盖的审计链。
- 固定 `narrated_panel_review_v1`：每镜抽取 `expected_dark_start / safe_start / midpoint / safe_end /
  expected_dark_end` 五个角色，最多 30 镜与 20 个限定词 cue 目标；物理帧去重但保留全部角色。Worker 对同一
  Video hash 重做 ffprobe、完整 decode 和一次 ffmpeg select，再生成 canonical manifest、离线 HTML 与 PNG
  的一个确定性 ZIP Asset，不把证据帧混入普通图片资产。
- 新增 `docs/contracts/sprint-190-native-agent-video-frame-evidence-pack.md`、
  `docs/strategy/youtube/paynes-creek-g8-frame-evidence-protocol.md` 和空白请求模板；Paynes Creek 固定 12×5=60
  个核心角色及 S03 / S07 / S09 / S10 四组逐字限定词。验收模板升至 schema version 4，并新增 G8-C；Pack
  成功只把同一 MP4 推进到 `ready_for_full_watch_review`，仍需人工从头到尾观看后才能判断本地样片。
- 同步规格、根 README、YouTube 导航、研究日志、生产控制室 Markdown / HTML、样片章程以及 G7-0 / G8-A /
  G8-B 流程图。本轮没有修改运行代码、数据库、配置或 Skill，没有调用模型、媒体、Remotion、发布或账单
  接口；只运行了本地临时合成校准，当前实际开发入口仍是 Sprint 181 / G2-A。

# Sprint 191 Native Agent 不可变本地样片验收与发布登记门禁（设计就绪，未授权实施）

- 代码审计确认当前“审核并登记 Agent 视频”前端会直接提交 `review_status="approved"`，后端在 owner、公网
  URL 和未重复登记通过后原样写库；现有 `PublishableVideo` 与 PublishTask 都没有 Video / Render Manifest /
  Evidence Manifest / Archive hash、完整观看 attestation 或四维 verdict，因而不能承担 G8 最终验收事实。
- 现有漫画 `AgentApprovalRequest` 与文案 `NativeAgentArticleApproval` 分别绑定不同 Run / Artifact 并会驱动
  各自 Workflow，不能复用。设计独立 `native_agent_video_acceptances`：每个 Video 和 succeeded Pack 只允许
  一条 owner-signed 终态，且只能是 `pass_local_pilot | needs_revision`，不提供 pending、更新、删除或强制通过。
- 验收采用两阶段 exact-hash 确认：preview 零写入并重新 materialize Video / Archive bytes，提交时按相同请求
  重新编译 canonical snapshot。四个维度固定为视觉证据连续性、脚本证据与节奏、中文语音字幕、渲染交付与
  可追溯性；通过必须四项 pass 且完整观看 attestation 为真，snapshot 永久保存
  `publication_authorized=false`。
- Manifest-bound 视频只能通过新 strict Acceptance 登记路径创建 `PublishableVideo`；source Video、
  `review_status=approved` 和 synthetic 标志由服务端推导并保存 Acceptance lineage。旧创建接口对这类视频
  返回冲突，历史普通视频保持原行为；真正创建 PublishTask 前还要复验 Acceptance 与实际 Video hash，任何
  漂移都保证远程调用为 0。
- 新增 Sprint 191 合同、系统交接蓝图、Paynes Creek G8 人工验收协议与空白请求，并同步总规格、导航、研究
  日志、控制室、样片章程和 G8 模板。本轮没有修改运行代码、数据库、前端或配置，没有调用模型、媒体、
  Remotion、YouTube、发布或账单接口；下一研究切片是 G9-A 不可变发布包，当前实际开发入口仍是 Sprint 181 /
  G2-A。

# Sprint 181 Native Agent Run 路由快照基础（G2-A，已完成）

- 新增独立配置 `NATIVE_AGENT_DEFAULT_ROUTE=huomiao_responses` 与
  `NATIVE_AGENT_HUOMIAO_MODEL=gpt-5.5`。旧 `AgentModelRouter` 继续读取 `AGENT_MODEL`，Native 创建与执行
  不从该字段 fallback。
- 新增 fail-closed route resolver / Provider factory。创建 Run 前检查 route、Native 模型、火苗凭据和合法
  HTTP(S) Base URL；配置错误返回 503，Run、Item、Workflow 和 enqueue 均无新增。执行时只接受
  `huomiao_responses / huomiao / responses` 的一致快照，未知或矛盾组合在 Provider 请求前使 Run 失败。
- `native_agent_runs` 新增 route / provider / API shape 三个非空快照字段；revision `v3w4x5y6z7a8` 把历史
  Run 固定回填为当时唯一 Responses 路径并保持原 `model_snapshot`。空库 upgrade、历史 upgrade、downgrade、
  无 server default 和无 route 索引均已验证；当前本地开发库为该 head，1 条历史 Run 无异常快照。
- 普通 Agent、Workflow Compiler、Director、Writer、Reviewer、重试、启动恢复、Follow-up、API 投影和
  MLflow trace 已统一使用 Run 四字段快照。Follow-up 逐字段继承，retry / recovery 不重新解析环境默认值。
- 新增 `test_native_agent_model_routes.py`，并扩充 Native Loop / Follow-up / recovery / article 测试。聚焦 47 项
  与受影响模块 32 项通过；Windows SQLite / MLflow 测试夹具补齐连接释放、容错清理与路径归一化，不改变
  业务断言。完整后端 386 项、前端 14 项与 production build、Remotion 5 项与 typecheck、Python compileall、
  内容迭代控制器状态校验和 `git diff --check` 均通过。
- 为执行 TypeScript 构建按 lockfile 安装了本地依赖；`npm ci` 报告 frontend 3 个、Remotion 2 个 high severity
  依赖告警。本 Sprint 未擅自执行会改变依赖版本的 `npm audit fix`，后续应建立独立安全审计与升级切片。
- 本 Sprint 没有增加 `siliconflow_chat_v1`、`use_responses=False`、Chat Event Adapter 或能力 Profile，也没有
  调用火苗、SiliconFlow、图片、VL、TTS、Whisper、Remotion、YouTube、发布或账单接口。G2 总 Gate 仍未
  通过；下一步是冻结 G2-B 独立合同。

# Sprint 192 Native Agent SiliconFlow Chat 有界适配（G2-B，已完成）

- 新增 API-only 的 `model_route` 显式选择。默认仍为 `huomiao_responses`；只有 Admin 可选择
  `siliconflow_chat_v1`，并固定为 `siliconflow / chat_completions / deepseek-ai/DeepSeek-V3.2`。创建前精确
  校验凭据、URL、`generate_image + inspect_image` Tool Profile、有效 Style 和零创作 / 发布上下文，失败不
  写 Run、Item、Workflow 或 enqueue，也不回退火苗。
- 新增有界 Chat Provider / Model wrapper：`use_responses=False`、strict feature validation、关闭流式 Tool
  buffering 与 client / Runner retry、`enable_thinking=false`。使用锁定 SDK 同一 Converter 对最终 messages
  计数，含 system 最多 10 条；11 条在 HTTP 前失败，不截断、摘要或删除上下文。
- 新增 route-independent Model Event Adapter。每次调用使用
  `native:{run_id}:attempt:{execution_attempt}:call:{ordinal}`；SDK `__fake_id__` 不入模型调用或 Provider ID。
  Function Call 按 output index / call ID 隔离，Chat Item done 合成唯一参数完成，参数不一致、缺真实 call ID、
  Provider ID 冲突或未完成调用均 fail closed。Responses 文本、Tool、usage 与 Session 重放回归保持通过。
- revision `w4x5y6z7a8b9` 为未来模型 Step 增加调用 ID、route、model、Provider ID、attempt、ordinal、消息数与
  latency 观测字段；API 同步返回。空库、历史升级和降级实测通过，历史字段保持 `NULL`，旧 Step / Event /
  Session 内容不变；当前本地开发库已升级到该 head。
- Chat 图片 Tool 成功或重放只向模型返回文本 ID，不 materialize data URL；同一 Run 最多一次新的图片
  Provider attempt，必须为唯一图片形成一次真实 `inspect_image` 终态后才能结束。SiliconFlow S03 Follow-up
  明确拒绝，不能绕过单镜预算；`accept` 不会被写成人工审核通过。
- 完整后端 398 项、frontend 14 项与 production build、Remotion 5 项与 typecheck、Python compileall、
  内容迭代控制器状态和 `git diff --check` 均通过。npm 依赖仍保留既有 frontend 3 个、Remotion 2 个 high
  severity 报告，本 Sprint 未修改 lockfile 或执行 `npm audit fix`。
- 本 Sprint 没有调用火苗、SiliconFlow、图片、VL、TTS、Whisper、Remotion、YouTube、发布或账单接口。
  G2 现记为 `pass_offline`，当前状态为 `stop_before_g3`；真实兼容性与 S03 媒体仍需 G3 / G4 独立授权。

# Sprint 193 SiliconFlow Native Agent G3 真实零媒体 Gate（执行器已就绪，真实请求 0）

- 用户已明确授权为了首支本地视频执行真实 SiliconFlow、图片、VL、语音、字幕和 Remotion；本 Sprint 仍只
  执行 G3，最多 5 次 SiliconFlow Chat 请求，使用账号现有额度且不充值，不注册或调用任何媒体 / 发布 Tool。
- 新增测试专用 G3 执行器，固定 Z1 文本流、Z2 单 `echo_probe` 两回合跨进程恢复、Z3 转换后 10 条消息和
  Z4 11 条 Provider 边界；复用生产 Chat wrapper、Event Adapter、数据库 Session 和模型 Step 证据。
- 执行器只使用新建临时 SQLite，记录请求数、Run / Step / Event / Session / Tool 身份；报告按 allowlist
  脱敏，不保存密钥、Authorization、完整 Provider 请求、绝对数据库路径或用户凭据。
- 离线 Mock 已通过真实 Agents SDK 流式文本与 Tool Call 事件形态，验证 Tool Output 持久化后可恢复且不
  重执行；G3 聚焦 13 项和完整后端 406 项测试通过，Python compileall 与 `git diff --check` 通过。
- 下一步先把执行器提交为不可变来源 commit，再把该 commit 与脚本 SHA-256 写进一次真实 G3 报告；提交
  前外部 Provider 请求仍为 0，图片、VL、语音、字幕、视频和发布调用仍为 0。

# Sprint 194 Windows SQLite 绝对路径 URL 解析（已完成）

- G3 Attempt 1 在临时数据库建表后、创建测试用户前因 `no such table: users` 停止；HTTP 记录确认 Provider
  请求为 0，媒体与发布调用均为 0，失败报告已保存为不可变 Attempt 1。
- 根因是 `Settings.resolved_database_url` 对 Windows 绝对路径整体执行 URL quote，把盘符和分隔符变成
  `%3A / %5C` 字面文件名；Alembic 因此升级了工作区里的错误文件，而 G3 Session 读取的真实临时文件为空。
- 本 Sprint 只修正 SQLite URL 路径解析并补测试，不改变 schema、默认数据库、Provider 或 G3 用例。
- 修复已完成：SQLite URL 改为 SQLAlchemy 可识别的绝对 POSIX 分隔路径；所有探针连接显式关闭，避免
  Windows 临时文件句柄滞留。配置与 G3 聚焦 11 项、完整后端 409 项测试通过。
- 真实 Alembic 对含空格的临时绝对路径升级后，目标文件包含 64 张表、`users` 与 head
  `w4x5y6z7a8b9`；工作区编码路径孤儿为 0。下一步提交修复和 Attempt 1 报告，再执行 G3 Attempt 2。

# Sprint 193 SiliconFlow Native Agent G3 真实零媒体 Gate（已完成）

- Attempt 2 锁定来源 commit `b701126` 与脚本 SHA-256
  `c1a1b3200e667067e2ed6bfe99edb52517dbe0e7b97a4752aebf3e351abed492`，并关联保留 Attempt 1 的
  Windows SQLite preflight 失败记录，没有覆盖历史证据。
- 真实执行共发送 5 次 `deepseek-ai/DeepSeek-V3.2` Chat 请求且全部成功：Z1 文本流、Z2 单 Tool 跨进程
  恢复、Z3 转换后 10 条消息和 Z4 Provider 接受 11 条消息均通过；生产 wrapper 仍保持 10 条上限并在
  HTTP 前拒绝第 11 条。
- `echo_probe` 恰好执行 1 次；所有成功请求都有非伪 Provider ID 和 usage，Run / Step / Event / Session
  交叉复核通过，重试、fallback、模型切换、未知事件与持久化伪 ID 均为 0。
- 图片、VL、语音、字幕、视频和发布调用均为 0；报告通过凭据、Authorization、绝对数据库路径、原始
  Prompt 与签名 URL 扫描，终态为 `pass_for_s03_single_image_review`。
- G3 只开放 G4 的一张 S03：下一步必须是一个新 Run、最多一次图片 Provider attempt、一张候选、一次 VL
  和人工事实 / 视觉复核；不得直接批量生成或进入语音、视频和发布 Gate。

# Sprint 195 Paynes Creek G4 单张 S03 真实媒体 Gate（预检实现已就绪）

- Sprint 194 修正 SQLite URL 后，正确 `doodlestory.db` 尚未承接旧 URL 编码文件中的本地验证数据；本轮先
  对旧文件执行只读完整性、schema、Style / Skill 和 SHA-256 校验，再只在目标为 0 字节时非破坏性复制。
  两份文件 hash 均为 `ee25e2fce58bcc958c6280b9fbbb095ef736b83f279bea3974a601216fb71b32`，
  `integrity_check=ok`、64 张表、head `w4x5y6z7a8b9`；旧文件继续保留作恢复副本。
- 当前数据库重新解析到唯一 active Style：`Qwen/Qwen-Image / 16:9 / prompt / 0 references`，以及唯一
  published Skill Version 1：只含 `generate_image + inspect_image`。S03 完整 Prompt hash 与锁定值一致。
- Native `inspect_image` 已从 `TEXT_FALLBACK_MODEL` 改为用户许可清单内的
  `SILICONFLOW_VISION_MODEL=Qwen/Qwen3-VL-32B-Instruct`；调用明确 `max_retries=0`，技术失败不回退其他
  VL Provider。端点总表与规格同步更新。
- Agent Vision 3 项、Native 受影响 41 项、完整后端 412 项测试通过；Python compileall、控制器校验与
  `git diff --check` 通过。真实 G4 Run 尚未创建，新增图片、VL、语音、字幕、视频和发布调用仍为 0。
- 新增一次性 G4 Runner，执行前逐项复核 Git / Prompt / G3 / Style / Skill / Route / Provider 和关闭重试
  配置；执行时只创建一个 Conversation / Run，并把候选原始 bytes、真实尺寸及 `pan_right` 两端探针保存到
  本地 `storage/exports`。机器 `accept` 仍不会自动写最终 Gate 通过；脚本聚焦 3 项测试通过。
- G4 Attempt 02 Run `64332bdfc1cd4111b0da5ec532e13bb2` 成功结束；Agent 模型调用 3 次、图片 Provider
  1 次、SiliconFlow VL 1 次，全部零重试，语音 / 字幕 / 视频 / 发布均为 0。候选 PNG 为 1664×928，
  SHA-256 `d6a6941a61b9ccc08785273aa933ac3f72c06a142cd9de0810607a6b4383eada`。
- VL 返回 `revise`；原图与 `pan_right` 探针确认现代金属水龙头 / 管件、伪 Logo、乱码与底部字幕区占用。
  委托事实和视觉复核均为 `fail`，Gate 终态 `needs_revision`；没有 approved 文件或第二张图片，G5 未开放。

# Sprint 196 Paynes Creek G4 Attempt 03 正向对象白名单（已完成并停止）

- 基于 Attempt 02 的真实失败，新 Prompt 移除现代器件负面关键词枚举，改为只允许五组视觉元素、四角全空、
  底部 32% 全空的正向白名单；规范化 SHA-256 为
  `ecf5820ca7912cb5a5ba955abc17a4fa6575937f547a1c8b3bb3ffe9bb70195e`。
- G4 Runner 已支持显式 Prompt 文件 / hash、previous attempt、候选 stem 和独立输出路径；Attempt 02 默认
  入口保持兼容。聚焦 4 项测试与 compileall、`git diff --check` 通过。
- 本 Attempt 只改变图片 Prompt；Style、Skill、Agent / 图片 / VL 模型、Provider、比例、旁白和 Gate 门槛
  保持不变。Run `0759b5260bbe4e0da21c82fb8332fec4` 成功结束，Agent 模型 3 次、图片 Provider 1 次、
  SiliconFlow VL 1 次且零重试，语音 / 字幕 / 视频 / 发布均为 0。
- 候选 `PC-S03-v02.png` 为 1664×928，SHA-256
  `c61811900129a461ddbc9fa719c440c338a9e8b2ee786b252a1ddd1c82c40e9e`。现代器件已消失，但底部
  乱码、未获准木块、延伸虚线和字幕安全区占用仍存在；机器 `revise`、委托事实 / 视觉复核均为 `fail`。
- Gate 终态保持 `needs_revision`；未产生 approved 文件，G5 未开放。新尝试必须使用新合同和新 Prompt
  hash，不能在 Attempt 03 内重试或把失败候选用于成片。

# Sprint 197 Paynes Creek G4 Attempt 04 静默博物馆动画帧（已完成并停止）

- 根据 Attempt 03 的乱码、木块和虚线问题，冻结全幅深海墨空场、主体上移缩小的新 Prompt，并把重建
  边界保留在原旁白中；Prompt 与独立 inspection request 分别以 SHA-256 锁定。
- G4 Runner 已支持检查文件 / hash，并在真实运行后进一步修正证据路径：从实际 `inspect_image` Tool Item
  提取 checks / expected 与 observed hash，不再把模板 request 当成真实调用；未来不匹配会直接停止。
- Attempt 04 Run `1ea7b158e16349b1a4477798b2edf617` 成功结束；Agent 3 次、图片 Provider 1 次、VL 1 次
  且零重试，其他媒体与发布为 0。候选 1664×928，SHA-256
  `b5d75374896162dc0da3b3df54c247e52f778fe85799ead6db96ee1fa94ad5cd`。
- VL 给出 `accept` 和全项 1.0，但原图 / pan 探针人工委托复核否决：陶罐位于木槽土层内，滴嘴与木槽
  关系倒置，青绿液流向画外扩张并占用下方 42% 字幕区。事实 / 视觉均 `fail`，Gate=`needs_revision`。
- 未产生 approved 文件，G5 未开放；机器满分不能覆盖可见的事实与构图错误。

# Sprint 198 Paynes Creek 确定性矢量本地样片（已完成：pass_local_vector_pilot）

- 在三次随机 S03 图片均被事实 / 视觉复核否决后，改用本地 Remotion 内联 SVG / CSS 矢量动画制作完整
  12 镜样片；该路径不修改 G4 失败结论，也不把矢量样片伪装为已批准的随机图片资产。
- 使用生产草案锁定的 536 字中文旁白，一次调用 SiliconFlow
  `FunAudioLLM/CosyVoice2-0.5B:alex` 生成 115.704 秒 MP3；图片、VL、视频生成 Provider 调用均为 0，
  TTS、Remotion 与 FFmpeg 规范化各执行一次且无重试。
- 最终 MP4 为 1920×1080、30fps、H.264 / AAC、`yuv420p / color_range=tv`、3472 帧，容器时长
  115.776 秒，SHA-256 `e063e02009c8dfc109781b8f030134fd36dc327c368816efd86f919d523d6a09`。
- 完整视频 / 音频解码、媒体 Profile、12 镜接触表和 S03 专项构图复核均通过；S03 现已确定性锁定为
  木槽在上、陶罐在下、液流终止罐内。音频没有超过 1.5 秒的长静音，11 个场景边界到最近自然停顿的
  最大偏差为 0.780 秒。
- 当前终态为 `pass_local_vector_pilot`：本地成片可播放、可审计，但不代表原 G4 / G5 产品 Gate 通过，
  不代表市场验证，也未授权 YouTube 上传。ASR 发音转写因可用 Skill 要求另一次显式确认而未执行。
- 可审计摘要保存在 `docs/testing/paynes-creek-vector-pilot-2026-08-13.json`；完整媒体、Manifest、帧证据和
  运行报告保存在 `storage/exports/paynes-creek/vector-pilot-v1/`。

# Sprint 199 grokcli Native Agent AI 视频短镜头（已完成）

- xAI 账号恢复视频能力后，项目 `grokcli 0.2.0` 已真实生成 Paynes Creek 8 秒 I2V；首次成功下载暴露
  本机 `.env` 遗留 macOS FFprobe 路径，临时视频按安全设计清理，没有自动重试。
- 显式改用 Windows FFprobe 后，7 项视频适配器测试通过；最终选中镜头为 8.042 秒、1280×720、24fps、
  H.264，SHA-256 `5b6a1f9bb3e141eade11ec388be1b4e8ef0588b22193790c436ab026bb0457ec`。
- 四点接触表确认盐土托盘、漏斗、液流与陶罐关系稳定，无文字、现代器件或明显形变；未切换 Provider。
  Sprint 199 的真实媒体阻断解除，状态改为 Complete。

# Sprint 200 Paynes Creek Grok AI 五镜短片（已完成：pass_local_ai_short）

- 明确选中海岸钩子、卤水浓缩、火上结晶、独木舟运输、证据边界五个 16:9 Grok 首帧与 I2V。一次
  火上结晶图片因火焰和陶器关系错误被人工否决后才建立新 attempt；五个选中视频均通过四点抽帧检查。
- 新增 `paynes-creek-grok-ai-short-v1` 生产计划，记录选中图片 / 视频路径、hash、真实时长、旁白、证据
  标签和 attempt 统计。整个会话共 6 次 Grok 图片调用、7 次视频调用，选中 5 图 / 5 视频，无自动重试
  或 Provider fallback。
- 新增独立 Remotion 五镜模板、Manifest 校验与一次性 Python Runner；Runner 会复验所有媒体 hash 与
  1280×720/24fps/H.264，按一次 CosyVoice2 中文旁白真实时长分配场景帧并限制 playback rate，最终输出
  1920×1080/30fps/H.264/AAC/yuv420p、接触表和审计报告。
- Python 聚焦 3 项、Remotion 11 项测试、TypeScript typecheck、compileall 与 `git diff --check` 通过。
  源码已提交为 `07d9b23f9bac56f7e2776a2d8202b56b7e1b7b43`，干净 preflight 全部通过。
- 一次 CosyVoice2 旁白成功生成 41.796 秒音频；一次 Remotion 和一次 FFmpeg 规范化生成最终
  41.856 秒 MP4。文件为 1920×1080、30fps、H.264/AAC、yuv420p/tv range、1254 帧、37,294,529
  bytes，SHA-256 `e6b1089b084b21411ef4ee73df16920dfd6c0ee5be29aaa670258da0d5ac7b98`。
- 完整音视频流解码通过，没有超过 1.5 秒的静音；五镜中点和 20 帧高密度接触表确认镜头、标题、证据
  标签与字幕稳定可读。终态 `pass_local_ai_short`，本地视频可播放；未运行 ASR 逐字核对，仍需用户完整
  观看，且 `publication_authorized=false`、上传调用为 0。

# Sprint 201 Paynes Creek Grok AI 英文五镜短片（Attempt 2 待真实渲染）

- 复盘中文版后保留五个已验收 Grok 镜头，英文版不逐句翻译：脚本改为问题钩子、制盐机制、独木舟
  证据和“过程可重建、具体旅程未知”的英语 Story-style 叙事，共约 126 词。
- 新增 `paynes-creek-grok-ai-short-en-v1.json`，冻结 `en-US` 标题、证据标签、旁白、页脚、独立 artifact
  slug 和五个既有媒体 hash；Grok 图片 / 视频新增调用预算均为 0。
- 现有 Remotion 模板和 Manifest 已扩展 `zh-CN` / `en-US` locale：标签按语言白名单验证，英文使用
  Segoe UI / Inter 字体栈和较紧凑字号；Runner 改为可选择项目内计划文件与独立产物名，并在英文场景
  之间加入 TTS 所需空格，中文版保持回归兼容。
- 英文时长预演表明 45–55 秒区间的五镜 playback rate 为 0.76–1.24，无需循环镜头。Python 4 项、
  Remotion 12 项测试、TypeScript typecheck、JSON 校验、compileall 和 `git diff --check` 已通过。
  Attempt 1 已用一次英文 TTS、一次 Remotion 和一次 FFmpeg 生成 46.293 秒 MP4，媒体完整解码、无长静音，
  但最终英文校对发现首句 `How did salt made ...` 语法错误，因此该产物明确 rejected，未发布且不覆盖。
- 新增不可变 `paynes-creek-grok-ai-short-en-v2.json`：修正 S01 / S03 语法并让 S09 更自然，保持同一视觉、
  Provider、TTS 声音和媒体 hash；允许 Attempt 2 各执行一次 TTS、Remotion 与 FFmpeg。两次英文 attempt
  的新增 Grok 图片 / 视频调用仍均为 0，也没有自动重试或 Provider fallback。
