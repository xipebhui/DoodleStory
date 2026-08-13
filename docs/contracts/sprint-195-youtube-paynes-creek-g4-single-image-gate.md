# Sprint 195：Paynes Creek G4 单张 S03 真实媒体 Gate

状态：Complete（Attempt 02 `needs_revision`）

## Goal

在用户已授权完成本地样片的前提下，修复 Sprint 194 后本地验证数据库的文件落点，使用已通过 G3 的
`siliconflow_chat_v1` 路由创建一个新的 S03 Native Run，并在严格的一次图片请求、一次 VL 检查预算内形成
可审计的 G4 终态。通过时只开放 G5 的 S01 锚点；失败时保留证据并停止。

## Authorization and review boundary

- 当前用户消息“我都给你授权，你先把视频做出来”作为 G4 的 Run、一次图片 Provider 请求、一次
  `inspect_image` 和本地候选文件授权；仅使用已有账号额度，不充值、不购买套餐。
- Agent Chat 固定为 `deepseek-ai/DeepSeek-V3.2`，图片固定为 `Qwen/Qwen-Image`，VL 固定为
  `Qwen/Qwen3-VL-32B-Instruct`；三者都属于用户批准的 SiliconFlow 免费额度模型清单。
- 用户把本地制作判断委托给 Codex。事实与视觉字段分别记录为 `Codex delegated production reviewer`，
  并明确标注为 AI 操作员复核，不伪装成人类或发布审核；G8 / G9 仍需独立完整观看与发布许可。
- 不允许自动重试、第二个 Run、第二张候选、模型 / Provider 切换、Prompt 修改或 fallback。

## In scope

1. 对旧 URL 编码 SQLite 文件执行只读 `integrity_check`、schema head、表数量、Style / Skill 和 SHA-256
   校验；在目标仅为 0 字节探针文件时，将旧数据库非破坏性复制到正确 `doodlestory.db`，原文件保留为
   恢复副本，复制后再次校验 hash 与业务对象。
   当前唯一测试用户是历史 S03 Run 与 Skill 的 owner；在本地验证库中把该 workspace owner 显式设为
   `admin`，以满足 `siliconflow_chat_v1` 的既有 API 权限边界，不创建额外用户、不修改远端身份。
2. 将 Native `inspect_image` 从未在免费模型边界内的 `TEXT_FALLBACK_MODEL` 改为现有
   `SILICONFLOW_VISION_MODEL` / SiliconFlow 多模态客户端，并补充聚焦测试；失败不回退其他 VL。
3. 从当前数据库重新解析唯一 active Style、当前 published Skill Version、参考图数量、Prompt 与哈希，
   同时复核 G2 / G3、工作树和当前 Git commit。
4. 冻结一个不可覆盖 G4 Attempt 记录，创建一个 Conversation 和一个 `siliconflow_chat_v1` Run，执行生产
   Native Loop；图片网关 HTTP 与 VL 均最多一次，不启用客户端自动重试。
5. 从真实 FileAsset materialize 候选，记录 MIME、字节数、SHA-256、真实宽高，并生成 8% 放大、3% 右移
   的 `pan_right` 视觉探针。
6. 保存机器 verdict、事实复核和视觉复核。三者全部通过时生成 `PC-S03-approved.png`；否则保留
   `PC-S03-v01.png` 与错误证据并停止。

## Out of scope

- 第二次 S03 尝试、S01 / S04 或其余镜头生图。
- 语音、字幕、Remotion、视频上传或 YouTube 发布。
- 改写 S03 Prompt、Style Prompt、Skill、图片模型或默认 Native Route。
- 删除旧 URL 编码数据库恢复副本，或把本地 AI 操作员复核解释为发布批准。

## Done means

- 正确数据库与恢复副本 SHA-256 一致，`integrity_check=ok`，迁移 head 为 `w4x5y6z7a8b9`，Style / Skill
  唯一且字段与协议一致。
- S03 Prompt SHA-256 为 `3cd1a0820096f3b3804aad06ced282265559adf40460401a6b0b47f980303729`；
  G3 证据终态为 `pass_for_s03_single_image_review`。
- `inspect_image` 聚焦测试和受影响 Native 测试通过，代码不会调用 TEXT_FALLBACK 或静默 fallback。
- 一个新 Run 最多形成一次图片 Provider HTTP、一个候选和一次 SiliconFlow VL；数据库调用计数、Step、
  Provider request ID、资产 hash 与真实尺寸可交叉复核。
- G4 记录终态只可能是协议允许值之一；只有机器 `accept`、事实 `pass`、视觉 `pass` 同时成立才写
  `pass_for_s01_anchor` 和批准文件名。
- `git diff --check` 与内容控制器状态校验通过，进度和生产控制室与真实终态一致。

## Verification

```powershell
& backend/.venv/Scripts/python.exe -m unittest backend.tests.test_agent_vision
& backend/.venv/Scripts/python.exe -m unittest backend.tests.test_native_agent_loop backend.tests.test_native_agent_route_capabilities
& backend/.venv/Scripts/python.exe -m compileall backend/app scripts
py -3.11 .agents/skills/content-iteration-controller/scripts/validate_controller_state.py
git diff --check
```

## Handoff

- `pass_for_s01_anchor`：提交本次不可变证据后，另建 G5 Attempt，只生成 S01 地图锚点。
- 其他任一终态：保留数据库 Run、候选或错误记录；不重试、不切换 Provider、不继续后续图片。

## Preflight implementation record

- 旧 URL 编码数据库与正确目标文件复制后 SHA-256 均为
  `ee25e2fce58bcc958c6280b9fbbb095ef736b83f279bea3974a601216fb71b32`，字节数 `1789952`；
  `integrity_check=ok`、64 张表、head `w4x5y6z7a8b9`。旧文件仍保留，目标在复制前严格为 0 字节。
- 当前 Style 唯一、active、未删除，模型 `Qwen/Qwen-Image`、比例 `16:9`、Prompt 模式、参考图 0，
  Style Prompt SHA-256 为 `5b8b5a7d144b13d6cdecc2ba2949205090df0958d8563b69968e8940a23b0d1b`。
- 当前 Skill 唯一、published、Version 1，只含 `generate_image + inspect_image`，Version ID 为
  `ba3a4875771248c4870b1ab6cf6afabd`。
- 新增 SiliconFlow VL one-shot 路径后，Agent Vision 3 项、Native 受影响 41 项、完整后端 412 项通过；
  Python compileall、控制器状态校验和 `git diff --check` 通过。
- 新增 `scripts/run_paynes_creek_s03_g4.py`：冻结 Prompt、Style、Skill、G3、Route 与一请求图片客户端配置，
  创建唯一 Run，执行生产 Native Loop，materialize 候选并生成 `pan_right` 首尾端点和接触表；报告在机器
  `accept` 后仍停在委托复核前。脚本聚焦 3 项测试通过。
- Attempt 02 使用来源 commit `55ce2be24c9761d85e0ff1bad5c19e4f328b748a` 创建唯一 Run
  `64332bdfc1cd4111b0da5ec532e13bb2`。Agent 模型调用 3 次，图片 Provider 与 VL 各 1 次，均无重试；
  语音、字幕、视频和发布调用为 0。
- 候选真实尺寸 `1664×928`、PNG、SHA-256
  `d6a6941a61b9ccc08785273aa933ac3f72c06a142cd9de0810607a6b4383eada`。VL 返回 `revise`；原图与
  `pan_right` 探针复核确认现代水龙头 / 管件、伪 Logo、乱码和底部字幕区占用，事实与视觉 verdict 均为
  `fail`，没有生成 `PC-S03-approved.png` 或第二张图片。
- 不可变报告：[Attempt 02 G4 记录](../testing/paynes-creek-s03-g4-2026-08-13-attempt-02.json)。下一步只能
  另建 Prompt 修订合同与 Attempt 03；不得把本 Run 改写为通过或直接进入 G5。
