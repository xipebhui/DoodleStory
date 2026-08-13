# Sprint 184：YouTube Paynes Creek G5 串行视觉锚点 Gate

状态：Complete（纯文档与空白证据模板；未调用模型或媒体）

## Goal

把 S03 通过后的 G5 视觉锚点检查拆成两个不可合并的单图 Gate：先用 G5-A / S01 验证抽象地图语言，
再用 G5-B / S04 验证陶器、黏土支座与热源关系。每个 Gate 分别授权、生成、检查、人工复核、写终态并
停止，避免一张图通过后自动生成第二张或直接开放余图。

## In scope

- 核对 S01 / S04 的事实、来源、权利、完整 Prompt、运动预设和当前 Native Tool 约束。
- 固定 S01 / S04 Prompt 的规范提取方式和 SHA-256。
- 定义 G5-A / G5-B 顺序、前置条件、单次副作用预算、机器检查、事实复核、视觉复核和终态。
- 记录当前 Remotion `zoom_in` 是以画面中心为原点的 `1.00 → 1.08` 缩放，不支持改变焦点。
- 建立机器可读 Gate Profile 和通用空白 attempt 模板。
- 同步生产控制室、样片章程、逐镜证据板、YouTube 索引、研究日志、根 README 与项目进度。

## Out of scope

- 不批准或实施 G2-A / G2-B，不运行 G3、G4、G5，不创建 Run、图片、资产或审核结果。
- 不修改 S01 / S04 的旁白、完整 Prompt、Style、图片模型、Provider 或 `zoom_in` 预设。
- 不增加自定义缩放中心、动态地图、图层、箭头标签、视频模板能力或运行时代码。
- 不授权第二候选、自动重试、Provider / 模型切换、S02 或其他余图、语音、字幕、视频或发布。
- 不把协议、Profile 或空白模板写成真实图片、质量、尺寸、成本或 Gate 通过证据。

## Deliverables

- `docs/strategy/youtube/paynes-creek-g5-serial-anchor-protocol.md`
- `docs/strategy/youtube/paynes-creek-g5-anchor-profiles.json`
- `docs/strategy/youtube/paynes-creek-g5-anchor-attempt-template.json`
- 生产控制室、样片章程、逐镜证据板、YouTube 索引、研究日志、根 README 与 `docs/progress.md` 更新。

## Done means

- G5-A 只允许一张 S01；只有完整通过才开放 G5-B 的单独授权评审。
- G5-B 只允许一张 S04；只有完整通过才开放 G6 余图生产计划评审，不自动生成任何余图。
- 每个 attempt 最多一个新 Run、一次 `generate_image`、一张候选、一次 `inspect_image`、一次事实复核和
  一次视觉复核；失败后不在同一授权内生成 v02。
- S01 通过条件明确区分抽象地图问题与确定贸易路线；S04 明确区分机制重建与完整出土炉灶。
- 两张锚点必须与已批准前序图保持完全相同的实际像素尺寸，并记录 Remotion 的 `0.01` 比例差容差；
  请求目标和交付目标不得冒充真实文件。
- `zoom_in` 探针按当前代码的中心缩放执行；S01 不再声称运行时会把变换原点移向泻湖。
- JSON 可解析、Profile 哈希和 Prompt 哈希可复算，所有未观测结果保持 `null / not_run / not_reviewed`。
- 本轮无运行时代码、数据库或外部副作用，内容控制器状态保持合法。

## Verification

```powershell
Get-Content docs/strategy/youtube/paynes-creek-g5-anchor-profiles.json -Raw |
  ConvertFrom-Json | Out-Null

Get-Content docs/strategy/youtube/paynes-creek-g5-anchor-attempt-template.json -Raw |
  ConvertFrom-Json | Out-Null

& backend/.venv/Scripts/python.exe `
  .agents/skills/content-iteration-controller/scripts/validate_controller_state.py

git diff --check
```

Manual checks:

- 从 Prompt 包按标题和 `text` 代码块重新提取 S01 / S04，统一 UTF-8、LF、无末尾换行后计算哈希。
- 对照 `native_agent_loop.py`、`agent_vision.py`、`remotion_video.py` 与 `NarratedPanels.tsx` 核对 Tool、
  判定、比例和运动事实。
- 检查 Profile、attempt 模板、协议、控制室和章程的 Gate 顺序与终态名称一致。
- 检查新增内容不含凭据、Authorization、签名 URL、绝对数据库路径或伪造媒体结果。

## Risks / notes

- S01 的创作意图是让视线靠近泻湖，但当前 `zoom_in` 固定以中心缩放；G5-A 只能验证现有运动是否仍可读。
  若失败，应另建 motion revision attempt，不在 G5-A 内改代码或预设。
- “完全相同实际像素尺寸”是本地首片的一致性门槛；当前 Provider 真实输出尚未知，不能预填尺寸。
- 事实审核人与视觉审核人、每个 Gate 成本上限和具体授权人仍未指定，模板准备不开放媒体调用。

## Handoff

- Sprint 184 完成后，G5 的验收方法已准备，但 G2-A 仍是当前唯一可授权的下一步。
- 未来 G4 只有写出 `pass_for_s01_anchor` 才能评审 G5-A；G5-A 只有写出 `pass_for_s04_anchor` 才能
  评审 G5-B；G5-B 通过也只开放 G6 计划评审。
