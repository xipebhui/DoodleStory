# Sprint 185：YouTube Paynes Creek G6 九镜串行生产设计

状态：Complete（纯文档、Profile 与空白证据模板；未调用模型或媒体）

## Goal

把 G5-B 之后尚未覆盖的 S02、S05–S12 拆成九个不可合并的单图 Gate，按依赖、视觉新颖度和事实漂移
风险决定生产顺序。每个 Gate 单独授权、只生成一张候选、完成机器检查与两类人工复核、写终态并停止，
避免把“剩余九张图片”误解成一次批量任务。

## In scope

- 核对九镜的 Scene、来源、权利、证据等级、完整 Prompt、Prompt SHA-256、文件名与运动预设。
- 建立九镜依赖 / 风险矩阵，并固定 G6-01 至 G6-09 的串行顺序。
- 固定每镜单一验证问题、机器检查、事实复核、视觉复核、尺寸探针、运动探针与通过状态。
- 建立机器可读 G6 Profile 目录和通用空白 attempt 模板。
- 纠正生产控制室中 S07、S08、S10、S11、S12 的时长与 S11 唯一主张。
- 消除 S08 证据板“画面内数字比例尺”与完整 Prompt“禁止数字 / 标签”的冲突。
- 同步生产控制室、样片章程、YouTube 索引、研究日志、根 README 与项目进度。

## Out of scope

- 不批准或实施 G2-A / G2-B，不运行 G3、G4、G5 或 G6，不创建 Run、图片、资产或审核结果。
- 不修改九镜旁白、完整 Prompt、Style、模型、Provider 或 Remotion 运行时代码。
- 不授权批量生图、自动重试、第二候选、Provider / 模型切换、图片重采样、语音、字幕、视频或发布。
- 不把设计顺序写成时间线顺序，不把 Profile、模板或 HTML 状态写成真实 Gate 通过证据。

## Deliverables

- `docs/strategy/youtube/paynes-creek-g6-serial-production-protocol.md`
- `docs/strategy/youtube/paynes-creek-g6-scene-profiles.json`
- `docs/strategy/youtube/paynes-creek-g6-scene-attempt-template.json`
- 生产控制室、逐镜证据板、本地样片章程与验收模板、YouTube 索引、研究日志、根 README、
  `docs/progress.md` 更新。

## Done means

- 九镜顺序固定为 S02 → S08 → S11 → S05 → S09 → S07 → S06 → S10 → S12，并有可复核理由。
- 每个子 Gate 最多一个新 Run、一次 `generate_image`、一张候选、一次 `inspect_image`、一次事实复核和
  一次视觉复核；任何失败都结束当前 attempt，并阻止所有后继镜头。
- 每镜都有唯一验证问题、1–10 项合法机器检查、具体事实 / 视觉人工门槛和唯一通过状态。
- 所有新图真实像素尺寸必须与所有已批准前序图完全相同；请求目标与交付目标不得冒充文件实测值。
- `static`、`zoom_out`、`pan_right`、`pan_down` 探针与当前 Remotion 实现一致。
- S08 的一米四三只由旁白 / 字幕承载；画面使用无标签长度线与无标签轴径剖面，不要求模型生成数字。
- JSON 可解析，九个 Prompt 哈希与 Profile 哈希可复算，未观测字段保持 `null / not_run / not_reviewed`。
- 本轮无运行时代码、数据库或外部副作用，内容控制器状态保持合法。

## Verification

```powershell
Get-Content docs/strategy/youtube/paynes-creek-g6-scene-profiles.json -Raw |
  ConvertFrom-Json | Out-Null

Get-Content docs/strategy/youtube/paynes-creek-g6-scene-attempt-template.json -Raw |
  ConvertFrom-Json | Out-Null

& backend/.venv/Scripts/python.exe `
  .agents/skills/content-iteration-controller/scripts/validate_controller_state.py

node C:\Users\Administrator\.agents\skills\impeccable\scripts\detect.mjs --json `
  docs/strategy/youtube/paynes-creek-production-control-room.html

git diff --check
```

Manual checks:

- 从 Prompt 包按标题与 `text` 代码块重新提取九镜 Prompt，以 UTF-8、LF、无末尾换行计算 SHA-256。
- 对照 `native_agent_loop.py`、`agent_vision.py`、`remotion_video.py` 与 `NarratedPanels.tsx` 核对 Tool、
  verdict、比例和运动事实。
- 核对九个 Profile、attempt 模板、协议、控制室和样片章程中的 Gate 顺序、前置状态与终态名称。
- 在桌面和移动端检查 HTML 时长、S11 主张、G6 顺序和产物链接可读性。
- 检查新增内容不含凭据、Authorization、签名 URL、绝对数据库路径或伪造媒体结果。

## Verification result

- 九镜 Profile 顺序、前后终态链、每镜 1–10 个唯一 checks、九个 Prompt 字符数 / 字节数 / SHA-256 与
  Profile 目录规范哈希全部复算通过。
- Profile、空白 attempt 与本地样片验收 JSON 均可解析；样片五个锁定输入的文件 SHA-256 全部匹配。
- 内容控制器状态校验、本地 Markdown 链接、旧错误时长 / S11 主张 / S08 数字画面指令扫描、敏感值扫描和
  `git diff --check` 通过。
- Impeccable 机械检测已执行；只报告原 HTML 未改动 CSS 中的设计令牌 advisory，没有本轮新增结构错误。
- 本地 HTML 在 1440×1000 与 390×844 验证：页面无横向溢出，12 个镜头时长与 S11 文案正确，G6 顺序
  和三个 G6 产物链接可见；移动端“未开放”筛选只显示 G3–G9，G6 行无内部溢出，浏览器控制台错误为 0。

## Risks / notes

- 生产顺序故意不等于 S02、S05、S06……的成片顺序；先验证高信息量或高误读风险的视觉族，能更早停止
  不成立的视觉系统。
- S11 被提前到第三张，是为了尽早验证唯一的“现代浅水—泥炭保存—古地面”环境切面，避免八张完成后才
  发现该视觉语法不可控。
- S10 与 S12 放在最后，因为它们依赖此前对象已经稳定；过早生成会诱发模型用抽象箭头补全尚未验证的
  运输与交换结论。
- G6 设计完成不改变当前真实执行状态：G2-A 仍待用户明确批准，所有媒体 Gate 仍关闭。
