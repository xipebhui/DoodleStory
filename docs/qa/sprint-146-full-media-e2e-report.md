# Sprint 146：对标账号到全媒体最小链路 QA 报告

## Sprint

`Sprint 146 - Agent Media Quality Gates and Partial Rerun`

## Verdict

`FAIL`

文案链路通过，但正文 Review 到视觉方案的 Durable Gate 映射错误，正式媒体入口被阻塞。为避免
绕过状态机或产生无效费用，本次没有调用图片、语音、字幕和视频 Provider。

## Scope Checked

- 从创作账号 `中国文明长纪录片` 读取绑定的对标账号与 `Q版本彩绘` 风格。
- 基于对标账号 `Our Lìshǐ（中国历史选题对标）` 生成并批准 1 个候选选题。
- 生成、机器计数、审批中文短文案，并执行 Reviewer 审核。
- 通过正式 `visual-plan` API 尝试进入 1 图、1 音频、1 视频的最小媒体链路。
- 检查 Run、Artifact、Native Approval、Durable Task 与 Durable Gate 的持久化状态。

## Evidence

- 基础检查：`./scripts/check.sh` 全部通过。
- 测试 Conversation：`b625c3b8bf3340cd991de7d4295a2673`。
- 测试 Run：`e62d493e0a9e444589e336303d142da6`。
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
- 调用计数：模型 11，图片 0，语音 0，字幕 0，视频 0；媒体资产数量均为 0。

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

这是全媒体主路径阻塞，不是 Provider、网络或生成质量问题。直接改数据库、绕过 Gate 或单独调用
媒体服务都会破坏本次端到端测试语义，因此没有采用。

### 环境备注：独立前端端口 CORS

独立前端 `13000` 访问独立后端 `18000` 时预检被拒绝，所以本次改用相同后端的真实 HTTP API
执行；所有业务写入仍经过正式接口。该问题不影响上述 Durable Gate 缺陷的复现。

## Follow-Up Required

- 修正 `article_review` Artifact/Approval 到 `editorial_review_gate` 的映射和完成动作。
- 增加回归测试：Topic 批准 → Draft 批准 → Review 批准后，`review_draft` 必须 succeeded，
  `editorial_review_gate` 必须 approved，且 Visual Plan API 可创建 1 个 Panel。
- 修复后沿用同一最小规格重新执行：1 个选题、正文不超过 200 字、1 张图、1 段旁白、1 个最短视频。

## Notes For Next Sprint

- 本轮没有媒体 Provider 费用；只发生 11 次文本模型调用。
- QA 专用 Skill `1ddf416fbd8f42f7b1a5f20e9a9e146f` / Version
  `38745b5be5984dac83e04e5b8301cc2d` 和失败 Run 保留，便于复现与修复后核对。
- 本地数据库升级前备份为 `doodlestory.db.sprint146-e2e-backup-20260801-1558`，不纳入 Git。
