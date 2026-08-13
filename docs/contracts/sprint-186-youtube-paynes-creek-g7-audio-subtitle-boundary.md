# Sprint 186：YouTube Paynes Creek G7 语音字幕与跨 Run 边界

状态：Complete（纯架构审计、生产协议、Profile 与空白证据模板；未调用语音或字幕）

## Goal

在真实 TTS 前核对 Native Agent 的音频、字幕、Follow-up 与视频渲染资产边界，确认 G7 是否能按人工 Gate
拆分执行；在可执行边界内固定 12 镜中文语音 / WebVTT 的风险顺序、单镜预算、发音与限定词验收、真实
时长记录和失败停止条件。

## In scope

- 核对 `generate_speech`、`generate_subtitles`、`render_story_video`、Follow-up 和媒体质量暂停的真实代码。
- 记录当前 G7 / G8 跨 Run 阻断及最小修正方向，不把设计写成已实现能力。
- 固定 G7-01 至 G7-12 的风险顺序、旁白文本哈希、Provider / Whisper 快照和每镜人工语言检查。
- 建立机器可读 G7 Profile 目录和通用空白 attempt 模板。
- 同步产品规格、生产控制室、样片章程、YouTube 索引、研究日志、根 README 与项目进度。

## Out of scope

- 不实现跨 Run 音频 / 字幕读取，不修改数据库、API、Native Tool、Skill、Worker、Whisper 或 Remotion。
- 不批准或实施 G2-A / G2-B，不运行 G3–G7，不调用火山 TTS，不加载 Whisper 模型，不生成媒体。
- 不修改 536 字旁白、语速、音色、Provider、模型、字幕算法或 120–150 秒总时长门槛。
- 不用单 Run 连续生成 12 段并渲染来绕过人工 Gate，也不引入复制资产、占位音频、在线 ASR 或静默回退。

## Deliverables

- `docs/strategy/youtube/paynes-creek-g7-audio-subtitle-protocol.md`
- `docs/strategy/youtube/paynes-creek-g7-scene-profiles.json`
- `docs/strategy/youtube/paynes-creek-g7-scene-attempt-template.json`
- 产品规格、生产控制室、样片章程、YouTube 索引、研究日志、根 README 与 `docs/progress.md` 更新。

## Done means

- 当前跨 Run 限制有代码证据：字幕只接受本 Run 音频，渲染只接受本 Run 音频 / 字幕，Follow-up 创建新 Run。
- 明确 G7-0 运行时前置：未来 G8 只允许读取同一 Conversation 中成功来源 Run 的音频 / 字幕，字幕必须
  绑定对应音频，权限与 lineage 可审计；未实现前 G7 保持关闭。
- 12 镜风险顺序固定为 S01 → S02 → S08 → S03 → S07 → S09 → S10 → S11 → S12 → S04 → S05 → S06。
- 每镜 attempt 最多一个新 Run、一次 `generate_speech`、一次 `generate_subtitles`、一段 MP3 和一份 VTT；
  两个 Tool 作为同一镜的授权对执行，完成后人工试听 / 校对并停止。
- 旁白按 UTF-8 原文 SHA-256 锁定；字幕拼接全文必须等于对应语音原文，时间轴单调且不超真实音频时长。
- S01 / S02 / S08 覆盖专名、地点、年代和度量锚点；S03 / S07 / S09 / S10 等限定词逐句验收。
- JSON 可解析，Profile 哈希与 12 个旁白哈希可复算，未观测字段保持 `null / not_run / not_reviewed`。

## Verification

```powershell
Get-Content docs/strategy/youtube/paynes-creek-g7-scene-profiles.json -Raw |
  ConvertFrom-Json | Out-Null

Get-Content docs/strategy/youtube/paynes-creek-g7-scene-attempt-template.json -Raw |
  ConvertFrom-Json | Out-Null

& backend/.venv/Scripts/python.exe `
  .agents/skills/content-iteration-controller/scripts/validate_controller_state.py

git diff --check
```

Manual checks:

- 对照 `volcengine_speech.py`、`whisper_subtitles.py`、`native_agent_loop.py`、`native_agent_persistence.py`、
  `native_agent_follow_up.py` 与 `NarratedPanels.tsx` 核对 Provider、字幕、Run 和渲染事实。
- 从生产草案重新提取 12 段旁白，以 UTF-8、无前后空白计算 SHA-256，与 Profile 比较。
- 核对 12 个前置状态、通过状态和下一 Gate 严格串联，最后只开放 G8 计划评审。
- 检查新增内容不含凭据、Authorization、签名 URL、绝对数据库路径或伪造媒体结果。

Verification result（2026-08-12）：

- 两份新增 JSON 与本地验收模板均可解析；12 个 Profile 的原文、字符数、UTF-8 字节数、文本 SHA-256、
  风险顺序、前置状态和通过状态已从生产草案复算并通过。Profile 规范哈希为
  `b628c128bb857cf6008d9dcf5e6d564a01b3f036f7285c4b633aa6bd09054277`。
- 9 份相关 Markdown 与生产控制室 HTML 的本地链接检查通过；控制器状态校验返回 `ok: true`、无 warning。
- 控制室在 1280 × 720 桌面视口与 390 × 844 手机 iframe 视口均无横向溢出；`未开放` 筛选、G7 卡片、
  `BLOCKED BY G7-0` 状态和三份 G7 资产入口可见，浏览器控制台无错误。
- Impeccable 静态检测仍报告页面原有的 67 条 DESIGN.md 色板 / 字号建议；本 Sprint 未修改 CSS，新增内容未
  引入新的布局或交互问题。
- 13 个变更文件的凭据特征扫描通过；`git diff --check` 通过。

## Risks / notes

- 当前主要阻断不是 TTS 可用性，而是人工 Gate 与 Run 级资产所有权不兼容。提前调用一段语音不能证明后续
  G8 能消费 12 个独立 Run 的音频 / 字幕。
- 当前字幕成功会把原文写回 cue，能保护限定词文本，但不能证明 TTS 实际读音正确；人工试听不可省略。
- 当前 Whisper 匹配率门槛只用于失败判定，不作为返回字段持久化；模板只能记录“成功路径已执行门槛”，
  不能伪造具体匹配率。
- 跨 Run 修正属于后续显式开发 Sprint；当前唯一可授权的开发入口仍是 Sprint 181 / G2-A。
