# Sprint 187：Native Agent 同会话跨 Run 媒体 Lineage（G7-0）

状态：Ready for review（未授权实施；默认排在 Sprint 181 / G2-A 之后）

## Goal

让 `render_story_video` 在保持当前 Run 行为不变的前提下，能够消费同一 Native Conversation 中已经成功
结束的历史 Run 所生成的 Audio / Subtitle，并把图片、音频、字幕的来源 Run 固化到新视频的 Scene 快照。
这一小步只解除“逐镜人工审核 → 独立 G8 成片 Run”的离线 lineage 阻塞，不生成任何媒体。

## Preconditions and ordering

- 当前可执行开发入口仍是 Sprint 181 / G2-A；本合同完成设计评审不会自动授权实现，也不改变生产 Gate
  顺序。
- 默认实施顺序为 G2-A → G2-B → G3–G6 → G7-0 → G7 逐镜语音；若要提前实现 G7-0，必须由用户
  明确调整顺序。
- 实施时以当时 `native_agent_loop.py` 的最新版本为基线，先 rebase，再处理与 G2 路由改造的重叠。
- 当前 G7 Profile、旁白、音色、Whisper 参数和 12 镜顺序保持锁定；本合同不修改内容输入。

## Current evidence

- `NativeVideoSceneInput` 只接收 `image_id`、`audio_id`、`subtitle | subtitle_id` 和 `motion_preset`；不接收
  来源 Run ID。
- `_resolve_video_inputs()` 已允许 Native 图片来自同一 Conversation 的历史 Run，但 Audio / Subtitle 查询
  都固定为 `run_id == 当前渲染 Run`。
- Follow-up 创建新 Run，不会把父 Run 的 Audio / Subtitle 改挂到子 Run。
- `NativeAgentVideo.scenes_json` 已保存 Scene 快照，API 以 `list[dict]` 原样投影；加入 lineage 字段不需要
  数据库迁移或响应 Schema 变更。
- 单次渲染最多 30 个 Scene，查询集合有明确上界；现有主键和 Run 外键索引足够，不需要新增索引。

## In scope

### 1. Tool 输入保持不变

- 不给 `NativeVideoSceneInput` 增加 `audio_source_run_id`、`subtitle_source_run_id` 或其他由模型提供的权限
  字段。
- 服务端从 `NativeAgentAudio.run_id`、`NativeAgentSubtitle.run_id` 和 `NativeAgentImage.run_id` 推导来源，
  不能相信模型声称的来源。
- 更新 `render_story_video` Tool 描述：Audio / Subtitle 可以来自当前 Run，或同一 Conversation 中状态为
  `succeeded` 的历史来源 Run。

### 2. 精确的来源资格

对每个 Scene 的 Audio 和 Subtitle 分别应用下表；全部查询都必须显式约束渲染 Conversation 的 owner，
Admin 可读能力不能转化为跨用户渲染授权。

| 候选来源 | Conversation | owner | 来源 Run 状态 | 结果 |
| --- | --- | --- | --- | --- |
| 当前渲染 Run | 当前 | 当前 | 当前执行状态 | 允许，保持现有行为 |
| 其他 Run | 相同 | 相同 | `succeeded` | 允许 |
| 其他 Run | 相同 | 相同 | 任意非 `succeeded` | 拒绝 |
| 其他 Run | 不同 | 相同 | 任意 | 拒绝 |
| 其他 Run | 任意 | 不同 | 任意 | 拒绝 |

- “历史来源 Run”不要求是渲染 Run 的直接 parent；同一 Conversation 是唯一允许的跨 Run 边界。
- 当前渲染 Run 不要求先成为 `succeeded`，否则会破坏现有 Tool 在运行中生成并立即渲染的行为。
- 未知、无权、跨 Conversation、跨用户和未成功来源使用同一类安全错误，不回显候选 ID、owner、
  Conversation 或真实存在状态。

### 3. Audio / Subtitle 配对与资产完整性

- Scene 使用 `subtitle_id` 时，Audio 和 Subtitle 都必须先独立通过来源资格检查。
- `subtitle.audio_id == scene.audio_id` 且 `subtitle.run_id == audio.run_id`；只满足外键关联但来源 Run 不同也
  必须拒绝。
- Audio 的 FileAsset、Subtitle 的 FileAsset、Audio 的正整数 `duration_ms` 以及现有 cue 数据都必须存在；
  失败时明确终止，不复制、移动、重挂、补建或伪造资产。
- Scene 使用内联 `subtitle` 时保持现有行为，不创建 Subtitle 记录。
- `generate_subtitles` 继续只接受当前 Run 的 Audio，不在本 Sprint 放宽。

### 4. 新视频 Scene 快照

新写入的每个 `scenes_json` Scene 在现有字段基础上增加：

```json
{
  "image_source_run_id": "native-image-source-run-or-null",
  "audio_source": "current_native_run | conversation_native_run",
  "audio_source_run_id": "native-audio-source-run",
  "subtitle_source": "inline_scene_text | current_native_run | conversation_native_run",
  "subtitle_source_run_id": "native-subtitle-source-run-or-null"
}
```

- Native 图片保存真实 `image_source_run_id`；Generation Task 图片保存 `null`。
- 内联字幕保存 `subtitle_source=inline_scene_text`、`subtitle_source_run_id=null`，并继续保存
  `subtitle_id=null` / `subtitle_asset_id=null`。
- Audio 与持久化 Subtitle 的来源 Run ID 都从数据库记录推导；不得从 Tool 参数抄入。
- 历史 `native_agent_videos.scenes_json` 不回填、不重写；本合同只保证新渲染视频的不可变快照。
- `NativeAgentVideoRead.scenes` 继续原样返回快照，因此无需新增 API 字段或兼容回退。

### 5. 查询与错误边界

- Audio / Subtitle 查询按最多 30 个 Scene 的 ID 集合批量完成，不能逐 Scene 形成 N+1 查询。
- 查询应在 SQL 层只返回“当前 Run，或同 Conversation + 同 owner + `succeeded` 的来源 Run”候选，
  不先加载无权记录再决定是否暴露。
- 现有图片授权、`inspect_image` Gate、Generation Task 图片、BGM、比例、真实时长、Remotion、Tool 幂等、
  取消和持久化流程保持不变。
- G8 未来必须使用只暴露 `render_story_video` 的专用 Skill Version；创建或发布该 Skill 不属于本合同。

## Out of scope

- 不实现 Sprint 181 / G2-A、G2-B 或 SiliconFlow Chat Event Adapter。
- 不调用火苗、SiliconFlow、图片、VL、火山 TTS、Whisper、Remotion、YouTube 或账单接口。
- 不生成 Paynes Creek 图片、语音、字幕或视频，不填写真实 Gate 结果。
- 不修改 `generate_speech`、`generate_subtitles`、Follow-up、媒体人工暂停或 Durable Runtime 状态机。
- 不允许同一用户跨 Conversation、Admin 跨 owner、任意 FileAsset ID 或来源 Run 未成功的引用。
- 不复制 / 移动媒体，不增加素材库、跨 Run 自动发现、自动挑选、重试、Provider 切换或 fallback。
- 不新增数据库表、列、迁移、索引、API endpoint、前端页面或管理端选择器。
- 不创建 / 发布 G8 Skill，不自动开放 G7-01，不修改策略记忆或 Skill 规则。

## Deliverables

- `backend/app/services/native_agent_loop.py`
  - 同会话已成功来源 Run 的批量 Audio / Subtitle 解析。
  - 配对、owner、状态与资产完整性校验。
  - Tool 描述和 Scene lineage 快照。
- `backend/tests/test_native_agent_loop.py`
  - 聚焦来源资格、配对、安全错误、当前 Run 回归和快照持久化测试。
- `docs/architecture/native-agent-cross-run-media-lineage-blueprint.md`
- `docs/spec.md`、`docs/progress.md` 与相关 Paynes Creek 导航 / 协议状态说明。

明确不属于 Deliverables：实体模型、Alembic migration、Native API Schema、前端、G8 Skill、真实媒体资产。

## Done means

### 正向行为

- 当前运行中的渲染 Run 仍可使用自己的 Audio 与内联字幕或自己的 Subtitle。
- 同一 Conversation、同 owner、状态为 `succeeded` 的历史 Run Audio / Subtitle 可以进入解析结果。
- 一条使用历史 Native 图片、历史 Audio 和历史 Subtitle 的 Scene 能生成包含三个真实来源 Run ID 的
  快照；Generation Task 图片或内联字幕按合同保存 `null`。
- `complete_video_tool()` 持久化这些快照，同一成功 `tool_call_id` 重放继续复用原视频与原 lineage。

### 拒绝行为

- 同 owner 不同 Conversation、不同 owner、历史来源 Run 非 `succeeded`、Audio / Subtitle ID 不存在时
  都在调用 Remotion 前拒绝。
- `subtitle.audio_id != audio.id` 或 `subtitle.run_id != audio.run_id` 时拒绝。
- 拒绝错误不泄露候选记录属于哪个用户、Conversation 或状态。
- 任一拒绝路径不复制资产、不调用渲染器、不保存视频。

### 不回归

- `NativeVideoSceneInput` JSON Schema、1–30 Scene 上界、当前图片授权、`inspect_image`、BGM、真实时长、
  比例检查、Tool 幂等与 API 读取行为不变。
- 无数据库迁移；迁移 head、实体关系和历史视频快照保持不变。
- 没有网络、Provider 或媒体调用，G7-0 只在离线测试全部通过后记录
  `pass_for_g7_scene_runs`。

## Verification

```powershell
& backend/.venv/Scripts/python.exe -m unittest `
  backend.tests.test_native_agent_loop

& backend/.venv/Scripts/python.exe -m compileall backend/app
./scripts/check.sh
git diff --check
```

聚焦断言至少覆盖：

1. 同 Conversation 的 `succeeded` 来源 Run Audio + Subtitle 成功，并保存 image / audio / subtitle 三个
   来源 Run ID。
2. 当前 Run Audio + 内联字幕保持成功，并保存当前来源与 `inline_scene_text`。
3. 对所有历史非 `succeeded` 状态逐一拒绝。
4. 同 owner 不同 Conversation 拒绝。
5. 不同 owner 拒绝，错误不包含候选 ID、邮箱或 owner ID。
6. Subtitle 指向另一条 Audio 时拒绝。
7. Subtitle 与 Audio 的 `audio_id` 匹配、但 `run_id` 不同时仍拒绝。
8. 成功视频的 `scenes_json` 原样保存 lineage；同一 Tool Call 重放不生成第二份视频。
9. 拒绝路径中 renderer 调用次数与新增 Video / FileAsset 数均为 0。

## Risks / notes

- 同一 Conversation 已经意味着同一 owner，但查询仍显式约束 owner，避免未来关系变化或损坏数据扩大
  权限边界。
- 历史视频没有新增字段是正常历史事实，不允许以回填默认值伪装来源。
- `subtitle.run_id == audio.run_id` 当前不是数据库级跨表约束，必须在解析时显式检查并由测试锁定。
- 本合同解决的是媒体引用与审计，不证明 G7 语音质量、G8 成片质量或 YouTube 市场适配。

## Handoff

- 设计评审可在不触发外部调用的情况下进行。
- 默认先完成并提交 Sprint 181 / G2-A；随后由用户明确回复“批准 Sprint 187”或“批准 G7-0”才实施。
- 实施通过后，只把本地样片 G7-0 Gate 更新为 `pass_for_g7_scene_runs`；G7-01 的真实 TTS 仍需单独授权。
