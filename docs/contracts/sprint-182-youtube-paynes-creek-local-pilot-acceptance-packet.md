# Sprint 182：YouTube Paynes Creek 本地样片验收包

状态：Complete（纯文档与本地 HTML；未实施 G2-A，未调用模型、媒体或发布接口）

## Goal

把“做出第一条视频”从宽泛目标收敛为一轮可证伪的本地生产验证：固定 Paynes Creek 首片的输入、
唯一验证问题、四个成片验收维度、证据记录与终态，使操作者在真实媒体完成后能明确判定
`pass_local_pilot`、`needs_revision` 或 `blocked_precondition`，而不是凭观感宣布赛道或链路成功。

## In scope

- 建立本地样片实验章程，区分生产验证、YouTube 市场实验和公开发布。
- 固定首片题目、中文、16:9、12 镜、536 字旁白、138 秒计划、无 BGM、原创解释图和证据限定词。
- 只验证一个问题：当前 DoodleStory 静态插画、中文语音、字幕与 Remotion 链路能否做出一条可审核的
  120–150 秒历史机制解释片。
- 定义四个必须同时通过的维度：视觉证据连续性、脚本与节奏、语音与字幕、渲染与可追溯性。
- 新增机器可读空白验收模板；未观测值保持 `null` 或 `not_run / not_reviewed`。
- 在现有 HTML 生产控制室加入验收阅读区，并修正 G2-A / G2-B 已拆分后的旧文案。
- 同步 YouTube 索引、生产控制室、研究日志、根 README 与项目进度。

## Out of scope

- 不批准或实施 Sprint 181 / G2-A，不创建 G2-B 合同，不修改运行时代码、配置、迁移、数据库或测试。
- 不调用火苗、SiliconFlow、图片、VL、TTS、Whisper、Remotion、YouTube、余额或账单接口。
- 不创建 Style、Skill、Conversation、Run、媒体资产、发布任务或内容市场实验。
- 不指定用户尚未确认的频道、地区、审核人、成本上限或发布责任人。
- 不修改旁白、Prompt、镜头、模型、Provider、画风规则或事实来源，不引入自动回退、Mock 或占位结果。
- 不把本地样片通过写成播放、留存、涨粉、获利或赛道成立，不更新 `strategy_memory.md` 或内容 Skill。

## Deliverables

- `docs/strategy/youtube/paynes-creek-local-pilot-charter.md`
- `docs/strategy/youtube/paynes-creek-local-pilot-acceptance-template.json`
- `docs/strategy/youtube/paynes-creek-production-control-room.html`
- 生产控制室 Markdown、YouTube 索引、研究日志、根 README 与 `docs/progress.md` 更新。

## Done means

- 章程只保留一个生产验证问题，并明确列出固定变量与不在本轮验证的市场变量。
- 四个验收维度分别写清输入、可观测证据、通过条件和失败停止动作。
- 只有 G0–G8 所需证据与四个维度全部通过，才允许终态为 `pass_local_pilot`；G9 不被自动开放。
- JSON 不含伪造 Run、资产、尺寸、成本、时长、审核人或 verdict，且能被标准 JSON 解析器读取。
- HTML 的阅读顺序为赛道 → 十二镜 → 样片验收 → 故障 → Gate → 产物 → 发布缺口；窄屏不依赖横向表格。
- HTML 明确显示 G2-A 只是当前待批准子 Gate，完成后仍需独立 G2-B，不能误读为已开放真实调用。
- 本轮无运行时代码与外部副作用；内容控制器状态仍合法，媒体与发布计数不变。

## Verification

```powershell
Get-Content docs/strategy/youtube/paynes-creek-local-pilot-acceptance-template.json -Raw |
  ConvertFrom-Json | Out-Null

& backend/.venv/Scripts/python.exe `
  .agents/skills/content-iteration-controller/scripts/validate_controller_state.py

node C:\Users\Administrator\.agents\skills\impeccable\scripts\detect.mjs --json `
  docs/strategy/youtube/paynes-creek-production-control-room.html

git diff --check
```

Manual checks:

- 对照来源账本、视觉权利清单、逐镜证据板、旁白 Prompt 包、生产草案与 G0–G9 控制室。
- 在桌面与手机视口检查新验收区的阅读顺序、无页面级横向滚动、键盘焦点与本地链接。
- 检查新增行不含密钥、Authorization、账号密码、签名 URL、绝对数据库路径或虚构市场数据。

## Risks / notes

- 这是一份未来填写的生产证据模板，不是现成结果；`pass_local_pilot` 当前不可选择。
- 536 字和 138 秒是锁定计划，真实 TTS 总长必须记录；若不在 120–150 秒，当前 attempt 失败，修改后
  另建 attempt，不能覆盖原记录。
- 1920×1080 是交付要求，不是图片 Provider 当前已验证返回；图片真实尺寸与最终视频探针必须分别记录。
- 生产通过只证明链路和成片达到本地标准，不证明标题点击、观看留存、频道适配或商业价值。

## Handoff

- Sprint 182 完成后，生产材料具备“开始前 Gate + 完成后验收”的双端证据结构。
- 当前执行下一步仍是用户明确批准 Sprint 181 / G2-A；该批准只覆盖 Responses 路由快照和离线测试。
- G2-A 通过后还要单独设计、批准并完成 G2-B；之后的 G3 零媒体调用、G4 单镜、余图、语音、成片与
  发布继续按各自 Gate 独立授权。
