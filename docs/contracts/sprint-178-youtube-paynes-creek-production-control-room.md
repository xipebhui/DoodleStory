# Sprint 178：YouTube 首片赛道定案与 Paynes Creek 生产控制台

状态：Complete（文档与本地 HTML；未执行模型、媒体或发布）

## Goal

把前序 YouTube 研究收敛为一个可执行但仍受 Gate 约束的首片生产入口：明确首个赛道与第一条视频，
把已有来源、授权、脚本、分镜、媒体尝试和 SiliconFlow 适配状态汇总到一份权威运行手册与本地 HTML
控制台，使后续操作者能在数秒内判断“现在能做什么、为什么还不能生图、通过后按什么顺序继续”。

## In scope

- 明确首个实际制作赛道、第一条视频及“生产适配度已验证 / 市场适配度未验证”的证据边界。
- 汇总 Paynes Creek 已有 12 镜、138 秒、536 字中文旁白、来源 / 版权、Prompt、Style / Skill 和 S03
  真实 Gate 证据，不复制完整 Prompt 或研究正文。
- 把当前状态拆成已完成、当前阻塞、需授权、待执行和发布前外部输入五类。
- 定义离线适配、SiliconFlow 零媒体 Gate、S03 单镜媒体 Gate、锚点镜检查、全片媒体、渲染与发布的
  严格顺序、负责人类型、输入、验收证据和停止条件。
- 输出 Markdown 权威运行手册与无外部网络依赖的响应式 HTML 控制台。
- 更新 YouTube 索引、研究日志、根 README 与项目进度。

## Out of scope

- 不修改 `.env`、Provider、数据库、后端、前端应用、Native Agent 或 Agents SDK 代码。
- 不调用火苗、SiliconFlow、图片、VL、TTS、Whisper、Remotion 或发布接口，不查询余额。
- 不重试 S03，不生成图片、语音、字幕或视频，不创建真实实验或发布任务。
- 不指定未确认的频道 owner、事实审核人、版权审核人、语言审核人或发布责任人。
- 不把 LuluJAI、单条公开视频或本地样片结果写成市场结论，不更新 `strategy_memory.md` 或 Skill。
- 不引入自动切换模型、截断上下文、摘要、占位媒体、Mock 结果或失败后的静默继续。

## Done means

- 文档明确写出首个赛道、首片题目、选择理由、适用范围和不能证明的市场结论。
- 操作者能从一个页面看见 12 镜制作概况、已存在产物、当前 `stop_before_batch` 原因和唯一下一授权点。
- 每个未来 Gate 都包含 owner 类型、输入、动作、通过证据与失败停止动作；互斥 Gate 不被合并。
- S03 通过前 S01、其余镜头、TTS、字幕、Remotion 与发布保持禁止；发布前缺失项单独列明。
- HTML 使用既有 YouTube “水下考古证据台”视觉系统，支持键盘焦点、窄屏重排、打印和 reduced motion，
  不依赖第三方脚本、字体或图片。
- 桌面与手机视口检查无页面级横向滚动，关键状态和链接可读，浏览器控制台无错误。

## Verification

- 对照 `paynes-creek-shot-evidence-board.md`、`paynes-creek-chinese-script-prompt-pack.md`、
  `paynes-creek-production-draft.json`、`paynes-creek-s03-media-gate.md`、SiliconFlow 兼容性决策与实施蓝图。
- 运行内容迭代控制器状态校验，确认没有把生产验证伪装为市场实验。
- 检查 HTML 语义、响应式布局、本地链接、控制台错误、焦点样式和打印边界。
- 运行 Impeccable detector、敏感信息扫描和 `git diff --check`。
- 本 Sprint 只验证文档和本地阅读页面，不把它写成运行时代码或真实媒体验收。

## Handoff

用户若批准开发，下一 Sprint 只能执行 SiliconFlow 适配蓝图 Phase A 的离线代码、迁移与聚焦测试，
仍不调用真实模型。Phase A 通过后，须另行批准一次零媒体 SiliconFlow 兼容性 Gate；只有该 Gate 返回
`pass_for_s03_single_image_review`，才允许创建一轮只生成一张 S03 候选的媒体 Gate。
