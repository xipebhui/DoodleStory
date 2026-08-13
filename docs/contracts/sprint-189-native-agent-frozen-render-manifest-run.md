# Sprint 189：Native Agent 冻结 Render Manifest Run（G8-B）

状态：Ready for review（未授权实施；默认排在 Sprint 188 / G8-A 之后）

## Goal

让一次专用 G8 Run 在创建时接收、服务端编译并不可变保存一份已经由人确认的 Render Manifest；运行时
`render_story_video` 只暴露零参数调用，并严格消费该快照。模型不能重新选择 Scene 顺序、图片、音频、
字幕、Motion、BGM 或输出 Profile。这个 Sprint 只建立确定性渲染入口和审计事实，不运行 Paynes Creek
真实媒体。

## Preconditions and ordering

- 当前可执行开发入口仍是 Sprint 181 / G2-A；本合同不改变既有生产顺序，也不授权调用任何外部服务。
- 默认顺序为 Sprint 181 / G2-A → G2-B → G3–G6 → Sprint 187 / G7-0 → G7 →
  Sprint 188 / G8-A → Sprint 189 / G8-B → Sprint 190 / G8-C 帧证据包 → 一次真实 G8 Render →
  同一 MP4 的证据包 → 人工完整观看。
- 实施时必须先 rebase，并以 Sprint 187 的跨 Run lineage 和 Sprint 188 的
  `youtube_16_9_1080p` preset 为已完成基线；任一前置合同未实施时，本合同只能继续停留在设计状态。
- Paynes Creek 的最终 Manifest 只能在 12 张图片、12 条语音和 12 份字幕都取得真实 ID、哈希与人工审核
  记录后冻结；当前空白模板不是可执行输入。

## Current evidence

- 当前 `NativeVideoSceneInput` 已包含渲染所需的图片、音频、字幕和 Motion，但这些参数直到模型发起 Tool
  Call 才保存到 Step；Run 创建前没有独立、已确认、可复核的渲染快照。
- `NativeAgentStep.input_summary_json` 和 Tool Item 能证明“模型最终传了什么”，不能证明“人事先批准了
  什么”，也不能阻止模型在转抄长 JSON 时改变一项参数。
- 现有 `NativeAgentRunCreate` 已对 YouTube 发布使用“结构化上下文 + 明确确认 + Run 快照”模式；Render
  Manifest 可以沿用这一成熟边界，不需要引入外部工作流引擎。
- Sprint 187 计划让服务端从数据库推导图片、音频和字幕的来源 Run；Sprint 188 计划让服务端固定输出
  Profile 并探针真实 MP4。Manifest 不应重复信任客户端声明的 lineage、尺寸、时长或文件哈希。
- 当前没有通用视频人工审批实体。G8 前确认可以作为 Run 创建授权事实；G8 后的事实、视觉、语言和完整
  观看结论继续进入本地样片 acceptance packet，不在本 Sprint 扩成通用审批系统。

## In scope

### 1. 客户端 Manifest 与确认 Schema

`NativeAgentRunCreate` 增加两个必须成对出现的可选字段：

```text
render_manifest: NativeAgentRenderManifestCreate | null
render_manifest_confirmation: NativeAgentRenderManifestConfirmation | null
```

Manifest v1 只接受：

```json
{
  "schema_version": 1,
  "manifest_key": "yt-pc-local-pilot-01-g8-v01",
  "purpose": "local_production_validation",
  "output_preset": "youtube_16_9_1080p",
  "bgm_asset_id": null,
  "scenes": [
    {
      "scene_key": "S01",
      "image_id": "<native-image-id>",
      "audio_id": "<native-audio-id>",
      "subtitle_id": "<native-subtitle-id>",
      "motion_preset": "zoom_in",
      "image_review_ref": "<immutable-review-record-ref>",
      "image_review_sha256": "<64-lowercase-hex>",
      "audio_subtitle_review_ref": "<immutable-review-record-ref>",
      "audio_subtitle_review_sha256": "<64-lowercase-hex>"
    }
  ]
}
```

- `schema_version` 只接受 `1`；未知版本明确拒绝。
- `manifest_key` 为调用方自己的稳定标签，1–160 字符；不作为数据库主键或幂等键。
- 两类 review ref 规范化后为 1–500 字符，配套 review SHA-256 必须匹配 `^[0-9a-f]{64}$`；ref 只作
  owner 已确认的审计定位，不允许 URL 凭据、Authorization 或本地绝对数据库路径。
- 本 Sprint 的冻结模式只接受 `purpose=local_production_validation` 和
  `output_preset=youtube_16_9_1080p`；不顺便开放任意 Profile。
- Scene 为 1–30 个，顺序即成片顺序；`scene_key` 必须唯一且符合 `^[A-Za-z0-9_-]{1,40}$`。
- 冻结模式只接受持久化 `subtitle_id`，不接受内联字幕；图片、音频和字幕必须是 Native Agent 媒体。
- Motion 仍只允许现有七个枚举；客户端不能传时长、宽高、来源 Run、Asset ID、哈希、裁切、模板、fps、
  codec、CSS 或文件路径。
- `image_review_ref` 与 `audio_subtitle_review_ref` 是审计定位信息，不被服务端伪装成已验证的审核内容；
  配套 SHA-256 必须为 64 位小写十六进制并进入 canonical hash。是否与真实审核文件匹配由当前认证用户
  在 preview 前核对，后端不读取仓库文件来伪装审核。
- `render_manifest_confirmation.confirmed` 必须为 `true`，并携带刚才 preview 返回的
  `expected_manifest_sha256`；服务端以当前认证用户和服务器时间记录确认人及时间，不接受客户端自报
  reviewer ID 或时间。

### 2. 只读 Preview 与精确 Hash 确认

新增 owner-scoped、无写入、无 enqueue 的预编译接口：

```text
POST /agent-loop/conversations/{conversation_id}/render-manifests/preview
```

- 请求体只含 `render_manifest`；复用 Run 创建时完全相同的 Schema、查询和 canonical compiler。
- 响应返回 canonical snapshot 与 `manifest_sha256`，不返回本地路径、签名 URL、邮箱或凭据。
- Preview 不创建 Run、Item、Workflow、Step、Event、FileAsset 或队列消息，也不调用模型 / 媒体。
- 用户检查 canonical snapshot 后，把 hash 原样放入 RunCreate confirmation；Run 创建事务内重新编译，只有
  `recompiled_sha256 == expected_manifest_sha256` 才能保存并 enqueue。
- 两次编译间任一媒体、来源状态、Asset hash、审核 ref / hash 或 Scene 字段漂移都明确返回 409；不自动
  接受新 hash。用户必须重新 preview、重新确认。

### 3. 专用 Skill 与 Run 创建边界

- 新增系统 Skill `youtube-frozen-render`，发布版本只暴露 `render_story_video`。
- 说明固定为：Manifest 已由用户确认并保存在 Run；只调用一次零参数 `render_story_video`，按真实 Tool
  Result 报告，不得重新设计、补全或替换媒体。
- 提供 `render_manifest` 时，所选 Skill Version 的 Tool 集合必须**恰好**为
  `['render_story_video']`；多一个或少一个 Tool 都在创建 Run 前拒绝。
- Manifest Run 不接受 `style_id`、`creation_channel_id` 或 YouTube 发布上下文；它只做本地渲染。
- 普通 Run 不提供 Manifest 时保持现有创建和 Tool Schema，不受专用 Skill 影响。
- Manifest-bound Run 禁止创建 Follow-up；修改任何输入都必须创建新 manifest key 和新 Run，保留旧记录。

### 4. 服务端编译与不可变快照

Run 创建事务内，服务端批量解析最多 30 组媒体并生成 canonical snapshot：

- 所有 Native 图片、音频、字幕均属于当前 owner 的同一 Conversation；来源 Run 必须为 `succeeded`。
- 每张图片的来源 Run 中存在同一 `image_id` 的成功 `inspect_image` Step，且输出 verdict 为 `accept`。
- 每条 Subtitle 必须满足 `subtitle.audio_id == audio.id` 且 `subtitle.run_id == audio.run_id`。
- 三类 FileAsset 必须存在并具有非空 `checksum_sha256`；图片必须有真实宽高，音频与字幕必须有正时长，
  字幕 cue 必须可解析且位于对应音频时长内。
- 客户端 Scene 字段与服务端推导的 `image/audio/subtitle source_run_id`、Asset ID、Asset SHA-256、尺寸、
  时长、字幕文本 SHA-256 和 cue 数合并成 canonical snapshot。
- canonical JSON 使用 UTF-8、排序 key 和固定紧凑分隔符计算 SHA-256；哈希由服务端生成，不接受客户端值。
- 任一 Scene 失败时 Run、Item、Workflow 和 enqueue 均为 0；错误不泄露其他用户或其他 Conversation 的
  记录是否存在。

`native_agent_runs` 新增：

```text
render_manifest_snapshot_json       TEXT NULL
render_manifest_sha256_snapshot     VARCHAR(64) NULL
render_manifest_confirmed_by_user_id VARCHAR(32) NULL FK users.id RESTRICT
render_manifest_confirmed_at        DATETIME NULL
```

- 四字段必须同时为空或同时非空；Manifest Run 由数据库 Check Constraint 保护。
- 历史 Run 全部保持 `null`，不回填、不推断；不增加索引，因为只按 Run 主键读取。
- API Read 返回 canonical snapshot、hash、确认人 ID 与确认时间；凭据、绝对路径和签名 URL不进入快照。

### 5. 零参数冻结渲染

- `build_render_story_video_tool()` 根据 Run 是否存在 Manifest 快照选择 Tool Schema：
  - 普通 Run：保持 Sprint 188 后的 `scenes / bgm_asset_id / output_preset` 参数；
  - Manifest Run：同名 `render_story_video()` 零参数函数。
- 零参数调用从 Run 快照取出唯一输入，不读取用户消息或让模型重新传 Scene。
- `prepare_video_tool()` 的参数事实至少保存 `render_manifest_sha256`、`manifest_key`、Scene 数、preset 和
  `bgm_asset_id`；完整 canonical snapshot 只保存在 Run，避免在多个事件中重复大 payload。
- 在任何 Node / Remotion 调用前重新计算 Run snapshot hash，重新解析来源资格，并对 materialized 的
  36 个图片 / 音频 / 字幕文件计算实际 SHA-256；任一事实与快照不一致都明确失败。
- 通过后用 snapshot 的 Scene 顺序、ID、Motion 和 `youtube_16_9_1080p` 调用 Sprint 188 renderer；不能
  修改 BGM、替换资产、改用内联字幕或回退到 source preset。
- 同一 `tool_call_id` 的成功重放继续复用同一 Video；失败不自动重试，不自动创建新 Manifest。
- Manifest-bound Run 只能准备一次 `render_story_video`，不同 `tool_call_id` 也不能发起第二次渲染；首次
  prepared / running / failed / cancelled / succeeded Step 都封闭该 Run 的后续 Render 调用。需要再次执行时
  必须由人创建新 Run，不能靠模型换 Tool Call ID 绕过单次预算。

### 6. 输出 lineage 与恢复

- 每个新 Video Scene 快照在 Sprint 187 / 188 字段之外增加：
  - `render_manifest_sha256`
  - `render_manifest_key`
  - `manifest_scene_key`
  - `image_review_ref`
  - `audio_subtitle_review_ref`
- Tool Step、Item、Event 和默认脱敏 trace 保存 Manifest hash 与 key，不复制完整审核文本或本地路径。
- startup recovery、同 Run retry 和取消恢复只使用已存 Run snapshot；不从新请求、Skill 当前草稿或环境
  重新编译 Manifest。
- Manifest-bound Run 的模型、Provider 和 API shape 仍由届时已经完成的 Run 路由快照决定；本 Sprint
  不创建第二套路由事实。

### 7. 自动结果与人工交接

- Sprint 188 的 ffprobe 成功只产生技术结构证据；渲染 Tool 成功后状态是
  `rendered_awaiting_frame_evidence`。只有 Sprint 190 / G8-C 对同一 Video SHA-256 生成完整帧证据包后，
  操作记录才可进入 `ready_for_full_watch_review`；两者都不是 `pass_local_pilot`。
- Paynes Creek 操作记录必须把 Run ID、Manifest hash、Video / Asset ID、文件 SHA-256、探针值、逐镜
  抽帧引用和人工完整观看 verdict 写入独立 G8 attempt 与总 acceptance packet。
- 人工发现字幕遮挡、Motion 裁切、空白帧、对象漂移、语音问题或事实限定词缺失时，保留原 Video 和
  Manifest，终态写 `needs_revision`；不得原地改 hash 或把失败 Run 重新标成通过。
- 本 Sprint 不增加“点击即通过视频”的产品 API；最终 `pass_local_pilot` 仍由现有本地验收包记录。

## Out of scope

- 不实施 Sprint 181、G2-B、Sprint 187、Sprint 188 或其他前置 Gate。
- 不调用火苗、SiliconFlow、图片、VL、TTS、Whisper、Remotion、ffprobe、YouTube、账单或发布接口。
- 不创建 Paynes Creek 最终 Manifest，不填写任何真实媒体 ID、哈希、Run、Reviewer 或验收结果。
- 不支持任意 output preset、任意模板、任意尺寸、内联字幕、任意 FileAsset、跨 Conversation 或跨 owner。
- 不增加通用资产库、通用视频审批表、通用工作流引擎、Redis、外部队列或独立 Worker。
- 不修改图片、语音或字幕生成，不自动寻找“最新资产”，不按文件名猜 ID，不自动替换失败媒体。
- 不自动重试、切 Provider、降级 Profile、缩短 Scene、删除字幕、改 Motion、补 BGM 或发布视频。
- 不修改 G9 标题、缩略图、频道、语言、AI 披露或数据回流设计。

## Deliverables

- `backend/app/schemas/native_agent.py`
  - Manifest / confirmation Create 与 Run Read Schema。
- `backend/app/models/entities.py`
  - 四个 Run 快照 / 确认字段和全空 / 全非空约束。
- 新 Alembic revision
  - 从实施时 migration head 增加字段、FK 和约束；升级 / 降级可验证。
- `backend/app/api/native_agent.py`
  - 只读 preview、专用 Skill / 上下文组合校验、hash 一致性、原子保存和安全错误。
- `backend/app/services/native_agent_render_manifest.py`
  - canonical 编译、哈希、来源资格与运行时完整性复验。
- `backend/app/services/native_agent_loop.py`
  - 普通 / Manifest 两种同名 Tool Schema 和冻结执行。
- `backend/app/services/native_agent_persistence.py`
  - Manifest hash 进入 Step / Item / Event / Scene lineage 与幂等事实。
- `backend/app/services/agent_skill_management.py`
  - 幂等 seed `youtube-frozen-render` 系统 Skill。
- `backend/app/agent_skills/youtube-frozen-render/SKILL.md`
- `backend/tests/test_native_agent_render_manifest.py`
- 对 Native Loop、Follow-up、Skill seed、migration 的聚焦回归测试。
- `docs/architecture/native-agent-frozen-render-manifest-run-blueprint.md`
- Paynes Creek G8 协议、空白模板、`docs/spec.md` 与 `docs/progress.md` 同步。

## Done means

### 创建与冻结

- 合法 1–30 Scene Manifest 可先无副作用 preview；用户确认返回的 hash 后，Run 创建在一个事务中重编译、
  比对 expected hash、保存 canonical snapshot / hash / authenticated confirmer，然后才 enqueue。
- canonical snapshot 的所有 lineage、Asset ID、hash、尺寸、时长和 cue 事实来自数据库，不来自客户端。
- 相同业务输入的 canonical hash 稳定；Scene 顺序、任一 ID、Motion、review ref 或 preset 变化都会改变 hash。
- Manifest 与 confirmation 缺一、未确认、expected hash 缺失 / 不匹配、未知 schema、重复 scene key、
  非专用 Tool 集、额外创建 / 发布上下文都在 Run 写库前拒绝。

### 资格与安全

- 同 Conversation / owner 的 succeeded 来源媒体、accept 图片检查和正确 Audio / Subtitle 配对通过。
- 跨 owner、跨 Conversation、非 succeeded 来源 Run、未 accept 图片、缺资产 / hash / 尺寸 / 时长、坏 cues
  或配对错误全部拒绝，且不创建 Run 或 enqueue。
- 错误响应不包含候选媒体 ID、owner ID、邮箱、Conversation ID、数据库路径或真实存在状态。

### 执行与不回归

- Manifest Run 的 Function Schema 对模型显示零参数；传任意参数被 Schema 拒绝，renderer 调用为 0。
- 零参数调用只消费 Run snapshot；snapshot hash、数据库 lineage 或实际文件 hash 漂移时在 Node 前失败。
- 成功调用使用固定 1080p preset、精确 Scene 顺序和 Motion，视频 Scene 快照包含 Manifest hash / key /
  scene key 与 review refs。
- recovery 和同 Tool Call 重放不重新编译、不产生第二个 Video；Manifest Run Follow-up 被拒绝。
- 普通 Run 的参数化 `render_story_video`、其他 Skill、历史 Run / Video 和 API 读取保持不变。

### 人工交接

- Tool 成功只输出 `rendered_awaiting_frame_evidence`，不会自动写 `ready_for_full_watch_review`、
  `pass_local_pilot` 或创建发布任务。
- 空白 Paynes Creek G8 模板所有未观测值均为 `null / not_run / not_reviewed`，没有伪造媒体事实。

## Verification

```powershell
& backend/.venv/Scripts/python.exe -m unittest `
  backend.tests.test_native_agent_render_manifest `
  backend.tests.test_native_agent_loop `
  backend.tests.test_native_agent_follow_up `
  backend.tests.test_agent_skill_management

& backend/.venv/Scripts/python.exe -m compileall backend/app
./scripts/check.sh
git diff --check
```

Migration checks:

1. 空 SQLite 从 base 升级到实施时 head，确认四字段、FK 和全空 / 全非空约束存在。
2. 在前一 revision 插入历史 Run 后升级，确认四字段保持 `null`，既有 Run / Video 数据逐字不变。
3. 插入合法 Manifest Run，确认 canonical JSON / hash / confirmer / time 全部非空。
4. 分别制造半空组合，确认数据库约束拒绝。
5. downgrade 到前一 revision，确认字段、FK 和约束被移除且其他数据保留。

Focused assertions 至少覆盖：

1. 合法 12 Scene Manifest 成功编译，hash 对 key 顺序不敏感、对业务值变化敏感。
2. Preview 零写入 / 零 enqueue；Run Create 重新编译与 expected hash 相同才成功，漂移时 409。
3. Manifest / confirmation 成对、`confirmed=true`、专用 Tool 集与互斥上下文。
4. 12 组媒体的同会话、owner、来源状态、inspect verdict、配对、Asset 元数据与 cue 校验。
5. 任一拒绝路径 Run / Item / Workflow / enqueue / renderer 均为 0。
6. Manifest Run Tool Schema 为零参数，普通 Run Schema 保持参数化。
7. DB snapshot 被改、Asset 数据库 hash 被改、materialized bytes 被改时各自明确失败。
8. 成功 Scene snapshot 与事件含 Manifest lineage，不含完整路径、凭据或签名 URL。
9. 同 Tool Call 重放、startup recovery、取消和 Manifest Follow-up 边界。

## Risks / notes

- `review_ref + review_sha256` 只解决“审核记录在哪里、确认时是哪份 bytes”，后端不读取仓库文件来证明其
  内容真实；真正的批准事实是当前认证用户 preview 后提交 exact canonical hash，最终质量仍以 G8 人工
  完整观看为准。
- 读取实际文件 hash 是为了防止数据库记录与存储 bytes 漂移；它会增加一次有界 I/O，但 Scene 上限 30，
  且渲染本身已经需要 materialize 图片和音频，不需要为此引入缓存或外部基础设施。
- 同名 Tool 的 Schema 随 Run 是否绑定 Manifest 而变，必须由明确的 schema 测试锁定，避免专用 Run 意外
  暴露参数化入口。
- 这是本地样片的确定性执行边界，不是通用视频项目管理、多人审批或 YouTube 发布系统。

## Handoff

- 当前只允许评审设计；用户没有明确批准 Sprint 189 前，不修改运行代码或数据库。
- Sprint 188 离线通过后，用户可明确回复“批准 Sprint 189”或“批准 G8-B”实施本合同。
- Sprint 189 离线通过后先实施 Sprint 190 / G8-C；两者均通过才产生 `pass_for_single_g8_render`。12 组
  真实媒体和审核记录齐全时才填写、确认 Paynes Creek Manifest；真实 G8 Render 仍需单独成本 / 运行授权，
  成功后先生成同一 MP4 的证据包，再进入人工完整观看，不自动开放 G9。
