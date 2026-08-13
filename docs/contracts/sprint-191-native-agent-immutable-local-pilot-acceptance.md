# Sprint 191：Native Agent 不可变本地样片验收与发布登记门禁

状态：Ready for review（未授权实施；依赖 Sprint 189 / 190）

## Goal

把已经成功生成 Evidence Pack 的同一支 Native Agent 视频，经过一次明确、可复验、不可原地修改的人工
四维验收后，记录为 `pass_local_pilot` 或 `needs_revision`。只有前者才允许进入严格的
`PublishableVideo` 登记路径；后续标题、描述、标签或封面不能把一个未通过的 Manifest 成片包装成
“审核通过”视频。

本 Sprint 解决的是 G8 的最终人工事实和 G9 的入口资格，不创建 YouTube 发布任务、不上传视频，也不证明
市场效果。

## Preconditions and ordering

- Sprint 181 / G2-A 已完成；当前仍须先完成 G2-B 与后续前置 Gate，本合同不授权跳过前序实现或运行真实
  媒体。
- 实施顺序保持：Sprint 181 / G2-A → G2-B → G3–G7 → Sprint 187 / G7-0 → Sprint 188 / G8-A →
  Sprint 189 / G8-B → Sprint 190 / G8-C → 一次真实 G8 Render → Evidence Pack → Sprint 191 人工验收。
- 只接受 Sprint 190 中 `succeeded` 的 Evidence Pack，其 Video 必须仍绑定同一 Render Manifest、同一
  Evidence Manifest 和同一文件 bytes。
- 当前 Paynes Creek 没有真实 Video、Pack、审核人或验收结果；本 Sprint 的实现与测试不得填造这些事实。

## Current evidence

- 当前前端“审核并登记 Agent 视频”表单会直接提交 `review_status="approved"`；后端
  `PublishableVideoCreate` 也允许客户端在创建时选择 `draft | approved` 并原样写库。
- 当前 `publishable_videos` 只绑定 `source_native_agent_video_id`、公网 URL 和发布元数据；没有 Video
  SHA-256、Render Manifest SHA-256、Evidence Pack、Evidence Manifest SHA-256、人工审核人或四维 verdict。
- 当前发布服务只检查 `PublishableVideo.review_status == "approved"`。因此这个状态能证明管理员进行了登记，
  不能证明管理员完整观看并通过了特定 bytes 的母版。
- 现有 `AgentApprovalRequest` 只服务旧漫画方案，`NativeAgentArticleApproval` 只服务文案 Artifact；二者都
  绑定不同 Run / Artifact，并会触发各自 Workflow 状态变化，不能安全复用为视频验收。
- 当前系统没有组织、团队或多审核人 RBAC。v1 只能让认证 owner 对事实、视觉、语言和完整播放四个维度统一
  签署，不能声称四个独立账号分别审批。

## In scope

### 1. 固定四维验收请求

验收维度恰好为：

1. `visual_evidence_continuity`
2. `script_evidence_and_pacing`
3. `chinese_speech_and_subtitles`
4. `render_delivery_and_traceability`

每个维度只允许：

```json
{
  "verdict": "pass",
  "issues": [],
  "notes": null
}
```

- `verdict` 只接受 `pass | fail`。
- `issues` 最多 20 项，每项 1–500 字；`notes` 最多 2000 字。
- `pass_local_pilot` 要求四项全部 `pass`、`full_watch_attested=true`、`revision_summary=null`。
- `needs_revision` 要求至少一项 `fail` 且 `revision_summary` 为 1–4000 字；不得把失败维度留空。
- `publication_authorized` 不进入请求，服务端永远保存为 `false`。本地样片通过不等于授权发布。
- 不接收审核人 ID、审核时间、文件路径、URL、模型判断、客户端计算 hash 或任意附加维度。

### 2. 无写入 preview 与 exact hash 确认

新增 owner-scoped preview：

```text
POST /agent-loop/video-evidence-packs/{pack_id}/acceptance-preview
```

请求 v1：

```json
{
  "schema_version": 1,
  "expected_video_sha256": "<64-lowercase-hex>",
  "expected_render_manifest_sha256": "<64-lowercase-hex>",
  "expected_evidence_manifest_sha256": "<64-lowercase-hex>",
  "expected_evidence_archive_sha256": "<64-lowercase-hex>",
  "decision": "pass_local_pilot",
  "full_watch_attested": true,
  "dimensions": {
    "visual_evidence_continuity": {"verdict": "pass", "issues": [], "notes": null},
    "script_evidence_and_pacing": {"verdict": "pass", "issues": [], "notes": null},
    "chinese_speech_and_subtitles": {"verdict": "pass", "issues": [], "notes": null},
    "render_delivery_and_traceability": {"verdict": "pass", "issues": [], "notes": null}
  },
  "revision_summary": null
}
```

Preview 必须：

1. 从 Pack → Video → Run → Conversation 证明当前用户是 owner；Admin 身份本身不构成跨 owner 授权；
2. 确认 Pack 为 `succeeded`，Archive Asset、Evidence Manifest 和必需帧齐全；
3. 重新 materialize Video 与 Archive，计算真实 bytes SHA-256，并同时匹配 FileAsset 记录与四个 expected hash；
4. 复验 Run Render Manifest hash、Pack snapshot 和 Video Scene snapshot 一致；
5. 把服务端事实、四维 verdict、当前认证 user ID 和 `publication_authorized=false` 编译为 canonical JSON；
6. 返回 canonical snapshot 与 `acceptance_snapshot_sha256`，不写库、不发事件、不 enqueue、不改变 Video / Pack。

Canonical JSON 使用 UTF-8、固定字段顺序、紧凑分隔符、保留 issue 数组顺序；服务端先 trim 文本并拒绝空
issue、重复维度和额外字段。`decided_at` 不进入预览 hash，由最终写入时使用服务器时间单独保存。

### 3. 不可变终态提交

新增：

```text
POST /agent-loop/video-evidence-packs/{pack_id}/acceptance
```

请求为 preview 请求加：

```json
{
  "idempotency_key": "<caller-stable-key>",
  "expected_acceptance_snapshot_sha256": "<preview-exact-hash>"
}
```

- 服务端完整重做 preview；snapshot hash 不一致时 409，零写入。
- 同一 Video 只能有一条终态 Acceptance，同一 Pack 也只能被一条 Acceptance 使用。
- 第一次写入即终态，不存在 `pending`、update、delete、approve-later 或状态覆盖接口。
- 同一 video + idempotency key + request SHA-256 重放返回原记录；key 或请求内容漂移返回 409。
- `needs_revision` 后必须生成新 Manifest、Run、Video、Pack 和 Acceptance；不能把同一视频原地改成通过。
- 服务端保存真实 `decided_by_user_id` 和 `decided_at`；请求不能替他人签名或回填时间。

### 4. 持久化模型

新增 `native_agent_video_acceptances`：

```text
id
video_id                              unique FK native_agent_videos.id RESTRICT
evidence_pack_id                      unique FK native_agent_video_evidence_packs.id RESTRICT
decided_by_user_id                    FK users.id RESTRICT
status                                pass_local_pilot | needs_revision
schema_version                        1
idempotency_key
request_sha256
video_sha256_snapshot
render_manifest_sha256_snapshot
evidence_manifest_sha256_snapshot
evidence_archive_sha256_snapshot
review_snapshot_json
review_snapshot_sha256                unique
decided_at
created_at
```

- 使用 `Base` 而不是带 `updated_at` 的 mixin，强调记录不可修改。
- Check Constraints 限定 status、schema version、四个 64 位小写 hex hash 和非空 snapshot。
- `video_id`、`evidence_pack_id`、`review_snapshot_sha256` 的唯一约束已经支持全部读取路径；不增加 status、owner
  或时间索引。owner 由 Video → Run → Conversation 解析，不提供全量 Acceptance 列表。
- 历史 Video 不回填；没有 Acceptance 只表示未经过新验收，不推断为失败。

### 5. 读取投影

新增：

```text
GET /agent-loop/videos/{video_id}/acceptance
GET /agent-loop/video-acceptances/{acceptance_id}
```

- 只允许 Video owner；未知与越权统一 404。
- Video 投影只嵌套 Acceptance 摘要：ID、status、四个 hash、review snapshot hash、审核人和时间；详情接口才
  返回完整四维 snapshot。
- Evidence Pack 详情返回关联 Acceptance 摘要，但不修改其 Pack 状态。
- 不把 Acceptance 伪装成 Agent Tool result、Run completed event 或模型输出。

### 6. Manifest 成片的严格 PublishableVideo 登记

新增：

```text
POST /youtube/publishable-videos/from-local-pilot-acceptance
```

请求只接受：

```json
{
  "acceptance_id": "<id>",
  "expected_acceptance_snapshot_sha256": "<64-lowercase-hex>",
  "thumbnail_url": null,
  "title": "<final title>",
  "description": "<final description>",
  "tags": [],
  "planned_publish_at": null
}
```

- 仅 Admin；Acceptance 的 Video owner 必须仍是该 Admin。
- 服务端从 Acceptance 推导 `source_native_agent_video_id`，不接受客户端另传 Video ID。
- 重新核对 Acceptance 为 `pass_local_pilot`、snapshot hash、Video / Manifest / Evidence / Archive hash 和实际
  Video bytes，任一漂移都不创建 PublishableVideo。
- `review_status` 不进入请求，由服务端固定写 `approved`；`contains_synthetic_media` 不进入请求，由服务端固定
  写 `true`。
- 标题、描述、标签、封面 URL 和计划时间仍使用 Sprint 134 的现有字段规则。本 Sprint 只证明这些元数据绑定
  的母版已通过，不证明封面版权、标题效果或发布实验已准备。
- 现有 `/youtube/publishable-videos` 遇到 Manifest-bound Video 时必须 409，不能继续接受客户端自填
  `review_status="approved"`；历史普通 source 视频保持 Sprint 134 行为。

`publishable_videos` 增加全空 / 全非空的一组 nullable 字段：

```text
source_video_acceptance_id                 unique FK native_agent_video_acceptances.id RESTRICT
source_video_acceptance_sha256_snapshot
source_video_sha256_snapshot
source_render_manifest_sha256_snapshot
source_evidence_manifest_sha256_snapshot
```

历史记录不回填，以上字段全空。严格入口创建的记录必须全非空且与 Acceptance 相同。

### 7. 发布前再次复验

`create_youtube_publish_task()` 在任何远程调用前：

- 对带 Acceptance 的 PublishableVideo 重新读取并核对五个 snapshot 字段；
- 重新 materialize source Video 并计算 SHA-256；
- Acceptance 不存在、不是 `pass_local_pilot`、hash 漂移或 owner 不一致时明确失败，Fake / real publisher 调用数
  必须为 0；
- 将 Acceptance ID、Acceptance hash、Video hash、Render Manifest hash 和 Evidence Manifest hash 复制到
  `youtube_publish_tasks` 的 nullable snapshot 字段，保持发布时永久证据链；
- 历史 PublishableVideo 五字段全空时保持当前审核与发布行为，不把它静默解释成已通过新验收。

### 8. 最小前端交互

Manifest-bound 视频卡不能再直接显示“审核并登记发布”。未来 UI 固定为：

```text
Evidence Pack 未成功     -> 显示“等待帧证据”，无验收 / 登记按钮
Pack succeeded           -> 显示“开始完整观看验收”
needs_revision           -> 显示失败维度与“需要新成片”，无登记按钮
pass_local_pilot         -> 显示 Acceptance hash 与“登记发布资料”
```

- 验收 Dialog 播放同一 Asset、显示 Video / Manifest / Evidence hash、提供 Archive 下载和四维 pass / fail 表单。
- `pass_local_pilot` 按钮必须要求四维全 pass、完整观看明确勾选，并展示最后一次 exact hash 确认。
- UI 的播放事件只用于帮助操作者，不作为服务端“真的看完”的证明；权威事实是认证用户对 exact hash 的签署。
- 关闭、刷新或错误不自动提交；提交成功后记录不可编辑。
- 通过后再打开现有发布资料 Dialog；严格入口不发送 `review_status`、`contains_synthetic_media` 或 Video ID。

## Out of scope

- 不实施或绕过 Sprint 181、187–190，不运行真实 Paynes Creek 视频。
- 不调用模型、图片、VL、TTS、Whisper、Remotion、YouTube、发布服务或账单接口。
- 不增加多审核人协作、团队权限、Reviewer 邀请、电子签名、法务审批或通用 Approval Engine。
- 不通过摄像头、眼动、播放遥测或防作弊技术证明人确实观看；只记录认证用户的明确 attestation。
- 不自动从 Evidence 指标生成 pass / fail，不让模型代替审核人。
- 不审核标题效果、封面版权、频道适配、披露文本、发布时间、预测指标或市场假设；这些属于后续 G9 发布包。
- 不创建、取消、刷新或真实提交 YouTube PublishTask。
- 不为 `needs_revision` 自动重渲染、重抽帧、换模型或生成修订版。
- 不删除、覆盖或修改历史 Acceptance。

## Deliverables

- `backend/app/models/entities.py`：`NativeAgentVideoAcceptance` 与 PublishableVideo / PublishTask nullable snapshots。
- 新 Alembic revision：Acceptance 表、唯一 / check / FK 约束、两组全空 / 全非空约束。
- `backend/app/schemas/native_agent.py`、`backend/app/api/native_agent.py`：preview、终态提交和 owner 读取。
- `backend/app/services/native_agent_video_acceptance.py`：资格复验、canonical snapshot、hash 与幂等写入。
- `backend/app/schemas/youtube.py`、`backend/app/api/youtube_channels.py`：严格 PublishableVideo 入口和旧入口阻断。
- `backend/app/services/youtube_publishing.py`：远程调用前 Acceptance / bytes 复验和任务 snapshot。
- `frontend/src/api/client.ts`、`frontend/src/main.tsx` 与现有样式：四维验收、状态和严格登记。
- 后端聚焦测试、前端行为测试 / 浏览器证据、规格、进度和 Paynes Creek 文档同步。

## Done means

### 验收事实

- Preview 对同一个真实 Video / Pack / user / verdict 产生稳定 canonical hash，且没有数据库写入。
- 终态提交重新编译 exact hash；通过和失败结构不合格、任何 source hash 漂移、越权或 Pack 未成功时零写入。
- 一支 Video 最多一条 Acceptance；同请求幂等，冲突请求不覆盖。
- `needs_revision` 永远不能成为 PublishableVideo；`pass_local_pilot` 仍保存
  `publication_authorized=false`。

### 发布登记

- Manifest-bound 视频无法从旧入口自填 approved；严格入口只从 pass Acceptance 推导源视频并固定合成披露。
- PublishableVideo 和 PublishTask 都保留 Acceptance / Video / Manifest / Evidence hash 快照。
- 实际发布前任一 hash 漂移都在远程请求前失败。
- 历史普通视频和历史 PublishableVideo 全空新字段时保持现有行为；不会被伪造为新验收结果。

### UI

- 未有 succeeded Pack、needs revision 和 passed 三种状态给出不同且准确的唯一下一动作。
- 用户能打开同一视频和 Evidence Archive，填写四维 verdict，明确确认 exact hash，并看到不可编辑终态。
- 未通过视频没有登记发布入口；通过后登记调用不再发送客户端 `review_status="approved"`。

## Verification

```powershell
& backend/.venv/Scripts/python.exe -m unittest `
  backend.tests.test_native_agent_video_acceptance `
  backend.tests.test_youtube_channels `
  backend.tests.test_native_agent_loop

& backend/.venv/Scripts/python.exe -m compileall backend/app
npm run build --prefix frontend
./scripts/check.sh
git diff --check
```

Migration checks:

1. 空 SQLite 从 base 升级到实施时 head；确认 Acceptance 表、唯一约束、status / hash check 和 snapshot 约束。
2. 含历史 Video、PublishableVideo、PublishTask 的前一 revision 升级后，历史行数量不变且新字段全空。
3. 合法 pass / needs revision 均可插入；重复 video / pack、坏 status、半空 snapshot 和 63 位 hash 被拒绝。
4. downgrade 移除新表和字段，保留原视频、可发布视频和发布任务数据。

Focused assertions 至少覆盖：

1. 四维 key 恰好一致；pass / fail 结构、full-watch attestation 和 revision summary 交叉约束。
2. Preview 零写入、canonical hash 稳定、服务端 user ID 进入 snapshot、服务器时间不进入 hash。
3. Video、Manifest、Evidence Manifest、Archive 四类 hash 的 DB / snapshot / bytes 三方漂移。
4. 同请求幂等、不同请求冲突、同 Video / Pack 二次决定和 `needs_revision` 不可覆盖。
5. owner、跨 owner、Admin 非 owner、未知 ID 使用安全错误且不泄露存在性。
6. 旧 Publishable 入口拒绝 Manifest-bound Video；严格入口拒绝 fail Acceptance 和 stale expected hash。
7. 严格入口固定 `review_status=approved`、`contains_synthetic_media=true` 并保存五个 snapshot。
8. 发布服务在 Acceptance 或 bytes 漂移时 Fake publisher 调用 0，合法严格 / 历史路径均保持既有幂等。

Browser QA 至少覆盖：

- Desktop 1440×900 与窄屏 390×844；
- Pack 未完成、可验收、needs revision、pass 四种状态；
- 四维 fail 时 revision summary 必填，pass 时 full-watch attestation 必填；
- Dialog 关闭 / 重开不提交，提交中防重复，成功后不可编辑；
- 通过前无登记按钮，通过后严格登记，API 409 可读；
- 无横向溢出、焦点陷阱、键盘关闭、触发焦点恢复和 console error。

不执行真实 YouTube 发布 smoke；本 Sprint 的测试 publisher 必须为 Fake，真实外部副作用仍需单独授权。

## Risks / notes

- 一名 owner 签署四个维度是当前单用户产品的诚实边界；它不是四人复核。需要独立审核人时必须先设计团队
  权限与逐角色签名，不能在 JSON 里填名字冒充身份。
- 不可变终态意味着误点也不能编辑；UI 必须用 preview hash 和最后确认降低误操作。内容失败只能新成片。
- 严格入口仍接受可选封面 URL，证明的是母版通过，不证明封面权利或标题策略；G9 发布包必须继续审核。
- 对象存储按不可变 storage key 使用；复验通过 materialize bytes 完成，不以公网 URL 字符串代替文件事实。
- 本 Sprint 不把文件化 `prediction.json` 强行塞进数据库；真实市场发布前仍必须单独设计 G9 实验与预测引用。

## Handoff

- 用户未明确批准 Sprint 191 前，不修改运行代码、数据库、前端或 API。
- Sprint 190 实施并通过后才可实施本 Sprint；本 Sprint 通过只开放 G9 发布包设计，不授权发布。
- 下一切片应设计 G9-A 不可变发布包：目标频道、单一实验变量、`prediction.json` 引用、标题、封面 Asset /
  权利、描述、标签、合成媒体披露、可见性和计划时间；最终 PublishTask 仍需再次明确确认。
