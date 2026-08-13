# Sprint 196：Paynes Creek G4 Attempt 03 正向对象白名单

状态：Complete（Attempt 03 已执行并以 `needs_revision` 停止）

## Goal

根据 Attempt 02 已观测的现代器件、伪文字和字幕区失败，冻结一份只描述允许对象与空间关系的 S03 Prompt，
在不切换 Style、模型或 Provider 的前提下执行一个新的 G4 Attempt。仍只允许一个 Run、一次图片 Provider
请求、一张候选和一次 SiliconFlow VL。

## Authorization and cost boundary

- 当前用户对“先把视频做出来”的完整本地制作授权覆盖本独立 Attempt；只使用已有账号额度，不充值。
- Agent / 图片 / VL 固定为 `DeepSeek-V3.2 / Qwen-Image / Qwen3-VL-32B-Instruct`，Provider 与 Attempt 02
  相同；不重试、不回退、不切换模型。
- 本 Attempt 的唯一变量是 S03 图片 Prompt：从长负面禁词列表改为正向对象白名单与严格留白，不修改
  旁白、事实主张、Style Prompt、Skill、比例或审核门槛。
- Codex 继续作为用户委托的 AI 制作复核者，记录必须明确非人类发布审核；G8 / G9 边界不变。

## In scope

1. 新增不可变 `paynes-creek-s03-attempt-03-prompt.txt`，只允许木托盘、托盘内含盐土、短木滴嘴、单一青绿
   液体路径、一个粗陶罐和局部琥珀虚线关系；所有角落为空、底部 32% 全空。
   规范化 UTF-8 / LF / 无尾随换行 SHA-256 为
   `ecf5820ca7912cb5a5ba955abc17a4fa6575937f547a1c8b3bb3ffe9bb70195e`。
2. 扩展 G4 Runner 接受显式 Prompt 文件、预期 hash、previous attempt、候选 stem 和输出路径；Attempt 02
   默认参数与测试保持兼容。
3. 提交 Runner 与 Prompt 后运行 preflight，再创建一个新 Conversation / Run；图片与 VL 均 one-shot。
4. 保存候选、真实尺寸 / hash、`pan_right` 两端探针、机器 verdict 和委托事实 / 视觉 verdict。

## Out of scope

- 修改 Style Prompt、Skill、Agent / 图片 / VL 模型、Provider 或默认 Route。
- 在本 Attempt 内生成第二张图、执行 G5、批量图片、语音、字幕、视频或发布。
- 覆盖 Attempt 02 报告或把失败候选用于成片。

## Done means

- 新 Prompt hash 与执行输入严格一致，且不包含 Attempt 02 诱发的现代器件关键词或任何要求画内文字的内容。
- Runner 聚焦测试、受影响 Native 测试、compileall、控制器校验和 `git diff --check` 通过。
- 一个新 Run 的图片 / VL 调用计数均不超过 1，其他媒体和发布调用为 0。
- 只有机器 `accept`、事实 `pass`、视觉 `pass` 同时成立才产生 `PC-S03-approved.png` 和
  `pass_for_s01_anchor`；否则保留 `PC-S03-v02.png` 并停止。

## Verification

```powershell
& backend/.venv/Scripts/python.exe -m unittest backend.tests.test_paynes_creek_g4_gate
& backend/.venv/Scripts/python.exe -m compileall scripts/run_paynes_creek_s03_g4.py
py -3.11 .agents/skills/content-iteration-controller/scripts/validate_controller_state.py
git diff --check
```

## Handoff

- 通过：提交 Attempt 03 证据后，另建 G5-A S01 单图合同。
- 未通过：保留证据并停止；下一次修订必须基于新观察另建合同，不在同一 Run 重试。

## Observed result

- Run `0759b5260bbe4e0da21c82fb8332fec4` 成功结束；Agent 模型 3 次、图片 Provider 1 次、SiliconFlow
  VL 1 次，全部零重试；语音、字幕、视频和发布调用均为 0。
- 候选 `PC-S03-v02.png` 为真实 1664×928 PNG，SHA-256
  `c61811900129a461ddbc9fa719c440c338a9e8b2ee786b252a1ddd1c82c40e9e`。
- 正向对象白名单消除了 Attempt 02 的现代水龙头与管件，但模型仍在底部生成乱码，并增加未获准木块与
  延伸虚线，陶罐和伪文字占用字幕安全区。机器 `revise`、委托事实 `fail`、委托视觉 `fail` 一致。
- 没有生成 `PC-S03-approved.png`，G5 保持关闭。后续只能基于这些新观察另建 Attempt，不能覆盖或重用
  本候选。
