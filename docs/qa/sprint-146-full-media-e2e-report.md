# Sprint 146：对标账号到全媒体最小链路 QA 报告

## Sprint

`Sprint 146 - Agent Media Quality Gates and Partial Rerun`

## Verdict

`FAIL`

文案与媒体资产均真实产出，但不能在同一个 Durable Run 内完成全流程：正文 Review 到视觉方案的
Gate 映射错误；经用户明确允许后，以审核通过的 118 字正文创建独立媒体 Run，最终生成图片、
旁白、字幕和视频，但该非文案 Run 又因遗留的文案 Durable Task 未完成而被标记失败。

## Scope Checked

- 从创作账号 `中国文明长纪录片` 读取绑定的对标账号与 `Q版本彩绘` 风格。
- 基于对标账号 `Our Lìshǐ（中国历史选题对标）` 生成并批准 1 个候选选题。
- 生成、机器计数、审批中文短文案，并执行 Reviewer 审核。
- 通过正式 `visual-plan` API 尝试进入 1 图、1 音频、1 视频的最小媒体链路。
- 经用户明确允许，将审核通过的正文作为不可改写输入，使用正式“完整故事转旁白视频” Skill
  创建独立媒体 Run，并锁定为 1 个 Chunk、1 个 Scene。
- 下载并核验真实图片、音频、WebVTT 字幕和 Remotion 视频。
- 检查 Run、Artifact、Native Approval、Durable Task 与 Durable Gate 的持久化状态。

## Evidence

- 基础检查：`./scripts/check.sh` 全部通过。
- 测试 Conversation：`b625c3b8bf3340cd991de7d4295a2673`。
- 文案测试 Run：`e62d493e0a9e444589e336303d142da6`。
- 媒体续作 Run：`a23fc6becb5c4fecb9796ed61351cdfa`。
- 创作账号：`a314f2142de9496d821bb30caf1fc38a`。
- 绑定风格：`4926710d71dd4a0aad144cd319f276cd`。
- 候选选题：`隋朝：一个短命王朝为什么能重新连接中国？`。
- 正文 Artifact：`fdcf941ede1d491eb49fe0994428ddf7`。
- Reviewer Artifact：`3f6fe082188e4fb7bffcfd800802686e`，结论为 `approved`。
- 正文机器计数为 118 个字符，符合“不超过 200 字”的测试约束：

> 隋朝很短命，却不是历史的插曲。它结束长期分裂，重新连接南北，让统一中国再次成为现实。大运河把不同区域的粮食、人口与权力连成一体，制度整合也为唐朝提供了基础。隋的崩溃，说明国家能力一旦过度使用会反噬自身；但它留下的结构，继续塑造后世中国。

- 最终 Run 状态：`failed / advance_to_review`，错误为
  `当前 Durable Task 尚未完成或仍等待人工 Gate，不能将 Run 标记成功`。
- 正式 `POST /api/v1/agent-loop/runs/{run_id}/visual-plan` 返回 409：
  `正文 Review 尚未批准，不能创建视觉方案`。
- 文案 Run 调用计数：模型 11，图片 0，语音 0，字幕 0，视频 0。
- 媒体 Run 调用计数：模型 7，图片 1，语音 2，字幕成功 1，视频 1。
- 图片 `f9f4981145c94a61835ce2db4e2dcf38`：1086×1448 PNG，实际画面为隋代官员、
  大运河、南北城市与粮船，无可见水印或乱码文字。
- 成功旁白 `8b70a7bbdb7e455bb77a6334cec7ae13`：火山 Seed-TTS、1.25 倍速、
  24.576 秒；保存文本与 118 字正文完全一致。
- 字幕 `2bee88d61b37476caa7fe3a9028cbcd6`：9 个 WebVTT cue、24.576 秒，字幕全文与
  旁白原文一致。
- 视频 `907adf599e47406aa48b9426e80e54b0`：1086×1448、30 fps、738 帧、
  H.264 + AAC、24.661 秒、45,551,472 bytes；12 秒抽帧确认字幕已叠加且画面正常。
- 本地核验产物位于 `output/sprint-146-full-media-e2e/`，不纳入 Git。

## Findings

### 阻塞：Reviewer Approval 被映射到错误 Gate

第三次 Native Approval `90013041526b42aaaebe246b78f39672` 对应 `article_review` Artifact，
但 `mirror_native_article_approval` 将它再次绑定到 `draft_review_gate`，创建的 Durable Gate purpose
仍是 `article_draft_review`，`on_approve_action` 仍是 `advance_to_review`。

因此持久化状态变为：

- `review_draft`：`running`；
- `editorial_review_gate`：`pending`；
- `draft_review_gate` 下出现两个已批准的 `article_draft_review` Gate；
- Native Run 再次执行 Review，随后因必需 Durable Task 未完成而失败；
- Visual Plan 正式入口认定正文 Review 尚未批准，无法进入图片质量与局部重跑链路。

这是同一 Durable Run 全媒体主路径阻塞，不是 Provider、网络或生成质量问题。未直接改数据库或
绕过 Gate；后续媒体续作仅在用户明确允许使用已审核正文后，通过正式 Agent Run 执行。

### 阻塞：非文案媒体 Skill 仍被初始化为文案 Durable Workflow

媒体续作 Run 已成功保存图片、旁白、字幕和视频，但完成时仍检查 `research_topics`、
`topic_selection_gate` 等文案 Durable Task。由于这些任务与“完整故事转旁白视频” Skill 无关且未
完成，Run 最终状态为 `failed`，错误仍是：

`当前 Durable Task 尚未完成或仍等待人工 Gate，不能将 Run 标记成功`。

因此“最终媒体资产成功”和“Agent Run 失败”同时存在，调用方不能只凭 Run 状态判断视频是否可用。

### 资源缺陷：字幕失败后重复生成旁白

第一次旁白 `66865635168341cab71e9ee475445472` 已成功，但其字幕连续两次因
`WhisperSubtitleError: Whisper 返回了无效的词级时间戳` 失败。Agent 没有复用已有成功旁白，
而是再次调用 Seed-TTS 生成相同文本；第二段旁白的字幕成功。最终视频只绑定第二段音频，第一段
成为未使用的重复资产，额外消耗一次 TTS。

### 缺口：Skill 要求的图片检查未执行

媒体 Skill 明确要求生成图片后调用 `inspect_image`，但该 Run 的 Tool Step 只有
`generate_image`、`generate_speech`、`generate_subtitles` 和 `render_story_video`，没有
`inspect_image`。虽然人工抽查画面可用，但 Agent 在未完成自身质量检查条件的情况下继续渲染了视频。

### 环境备注：独立前端端口 CORS

独立前端 `13000` 访问独立后端 `18000` 时预检被拒绝，所以本次改用相同后端的真实 HTTP API
执行；所有业务写入仍经过正式接口。该问题不影响上述 Durable Gate 缺陷的复现。

## Follow-Up Required

- 修正 `article_review` Artifact/Approval 到 `editorial_review_gate` 的映射和完成动作。
- 增加回归测试：Topic 批准 → Draft 批准 → Review 批准后，`review_draft` 必须 succeeded，
  `editorial_review_gate` 必须 approved，且 Visual Plan API 可创建 1 个 Panel。
- 只为真正的文案 Skill 初始化 ARTICLE_TASKS；非文案媒体 Skill 成功产出最终资产后应能正常结束 Run。
- 字幕重试必须复用已成功音频，不能重新调用 TTS；为无效词级时间戳补充可验证的错误处理测试。
- 媒体 Skill 在 `inspect_image` 成功前不得调用 `render_story_video`。
- 修复后沿用同一最小规格重新执行，并要求单个 Run 成功结束：1 个选题、正文不超过 200 字、
  1 张图、1 段旁白、1 份字幕、1 个最短视频。

## Notes For Next Sprint

- 本轮实际调用 1 次生图、2 次 TTS、3 次字幕尝试（1 次成功）和 1 次视频渲染；没有发布。
- QA 专用 Skill `1ddf416fbd8f42f7b1a5f20e9a9e146f` / Version
  `38745b5be5984dac83e04e5b8301cc2d` 和失败 Run 保留，便于复现与修复后核对。
- 媒体 QA Skill `9d72c44b257943e4a6d21ac56545ff32` / Version
  `18b352d2340e4c30b8e01aecb43e5722` 及全部媒体资产保留。
- 本地数据库升级前备份为 `doodlestory.db.sprint146-e2e-backup-20260801-1558`，不纳入 Git。
