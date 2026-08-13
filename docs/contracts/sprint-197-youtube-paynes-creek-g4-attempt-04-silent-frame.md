# Sprint 197：Paynes Creek G4 Attempt 04 静默博物馆动画帧

状态：Complete（Attempt 04 已执行并以 `needs_revision` 停止）

## Goal

根据 Attempt 03 已观测的乱码、多余木块、延伸虚线和字幕安全区失败，冻结一个不再使用信息图标注语法的
S03 Prompt 与检查请求，在同一 Style、模型、Provider 和 Gate 质量门槛下执行一个新的单图 Attempt。

## Authorization and cost boundary

- 当前用户对完整本地视频制作和现有免费额度调用的授权覆盖本独立 Attempt；不充值、不发布。
- Agent / 图片 / VL 继续固定为 `DeepSeek-V3.2 / Qwen-Image / Qwen3-VL-32B-Instruct`，Provider 保持
  `siliconflow / qy / siliconflow`；不重试、不回退、不切换模型。
- 本 Attempt 只改变 S03 图片 Prompt，以及把“重建”视觉编码从容易诱发箭头和标签的琥珀虚线改为可选的
  紧贴对象琥珀边缘光；旁白中的“依据遗迹和类比做的重建”保持原文，事实边界不降低。
- Codex 作为用户委托的 AI 制作复核者，不能冒充人类发布审核。

## In scope

1. 冻结 `paynes-creek-s03-attempt-04-prompt.txt`：主体缩小并上移，画面全幅使用深海墨背景，下方 42%
   为空；只保留木槽、含盐土、短木滴嘴、青绿液体和一个粗陶罐。规范化 UTF-8 / LF / 无尾随换行
   SHA-256 为 `7405efec3ac5522cb256239d0a901abdc7f6db05a2c8063ccba440c7d5984634`。
2. 冻结 `paynes-creek-s03-attempt-04-inspection.json`：明确不要求图片内箭头、标签或虚线，重建限定由旁白
   承担，可选琥珀边缘光只作视觉区分；无文字、多余对象和字幕区仍是硬失败。按键排序、紧凑 JSON 的
   规范 SHA-256 为 `78f4f7007590109a45190a3588742b828d5ffbf961ce16f6b89eeec95d49f55f`。
3. 扩展 G4 Runner 接受显式检查请求文件及 SHA-256，并把实际检查请求与 hash 写入记录。
4. 提交输入和 Runner 后运行 preflight，再只创建一个 Run、一次图片 Provider 请求、一张候选和一次 VL。

## Out of scope

- 图片编辑、参考图、后处理遮盖、Style / Skill 修改、模型或 Provider 切换。
- 同 Attempt 第二张图、G5、批量图片、语音、字幕、视频、发布。
- 覆盖 Attempt 02 / 03 记录或把其失败候选用于成片。

## Done means

- Prompt 与 inspection 文件的规范化 hash 与执行输入一致；Runner 默认 Attempt 02 行为保持兼容。
- 聚焦测试、compileall、控制器校验和 `git diff --check` 通过。
- 图片 / VL 调用均不超过 1，其他媒体与发布调用为 0。
- 只有机器 `accept`、委托事实 `pass`、委托视觉 `pass` 同时成立才产生 `PC-S03-approved.png` 和
  `pass_for_s01_anchor`；否则保存 `PC-S03-v03.png` 并停止。

## Verification

```powershell
& backend/.venv/Scripts/python.exe -m unittest backend.tests.test_paynes_creek_g4_gate
& backend/.venv/Scripts/python.exe -m compileall scripts/run_paynes_creek_s03_g4.py
py -3.11 .agents/skills/content-iteration-controller/scripts/validate_controller_state.py
git diff --check
```

## Handoff

- 通过：提交 Attempt 04 证据，再另建 G5-A S01 单图合同。
- 未通过：保留证据并停止；新 Attempt 必须基于新观察另建合同。

## Observed result

- Run `1ea7b158e16349b1a4477798b2edf617` 成功结束；Agent 3 次、图片 Provider 1 次、VL 1 次且零重试，
  语音、字幕、视频和发布调用均为 0。
- 候选 `PC-S03-v03.png` 为 1664×928 PNG，SHA-256
  `b5d75374896162dc0da3b3df54c247e52f778fe85799ead6db96ee1fa94ad5cd`。无现代器件、无文字，配色通过。
- 机器 VL 返回 `accept`，但委托事实与视觉复核均 `fail`：陶罐被放在木槽土层内，滴嘴 / 木槽空间关系
  倒置，青绿液流穿过木槽后向画外扩张并占满字幕安全区，不能表达“盐水经含盐土后收进陶罐”。
- 执行后发现报告模板仍展示旧 inspection request；数据库真实 `tool_call` 已确认使用 Attempt 04 新请求。
  Runner 已改为从真实 Tool Item 提取 request、计算 observed hash 并把不匹配作为停止条件。
- 没有生成 `PC-S03-approved.png`，G5 继续关闭。
