# Sprint 190：Native Agent 成片逐镜帧证据包（G8-C）

状态：Ready for review（未授权实施；排在 Sprint 189 / G8-B 之后）

## Goal

为一个已经成功保存、绑定冻结 Render Manifest 的 Native Agent MP4 创建可恢复、可下载、可人工复核的
逐镜帧证据包。系统只按固定模板的真实帧号抽取证据，不调用模型或媒体 Provider，不把技术证据伪装成
人工验收；证据包成功后才允许把 G8 attempt 标为 `ready_for_full_watch_review`。

## Preconditions and ordering

- Sprint 181 / G2-A 已完成；当前仍须先完成 G2-B 与后续前置 Gate，本合同不授权提前实现或运行真实媒体。
- 实施顺序固定为 Sprint 181 / G2-A → G2-B → G3–G6 → Sprint 187 / G7-0 → G7 →
  Sprint 188 / G8-A → Sprint 189 / G8-B → Sprint 190 / G8-C → 一次真实 G8 Render →
  同一 MP4 的证据包 → 人工完整观看。
- 只接受 Sprint 188 的 `youtube_16_9_1080p`、模板
  `narrated-panel-16x9-1080p-v1`、30 fps，以及 Sprint 189 的 Manifest-bound Run；普通 source
  视频、历史模板和没有 Manifest hash 的视频保持原样。
- 真实 Paynes Creek 视频、媒体 ID、字幕 cue、视频哈希和审核人当前均不存在。本 Sprint 只实现能力与
  无网络合成校准，不填写真正 G8 结果。

## Current evidence

- Sprint 188 计划用 ffprobe 证明 MP4 的 codec、流、1920×1080、30 fps、帧数和时长，但 ffprobe 不证明
  Scene 顺序、字幕可读、Motion 安全、意外黑帧或空白帧。
- 当前 `NativeAgentVideo` 只保存视频 Asset、Scene JSON 和视频级元数据；没有证据包实体、帧采样计划、
  抽帧状态或可下载的人工审核索引。
- 当前 Remotion 模板每镜固定 `FADE_FRAMES=8`：本地帧 0 和末帧是预期黑场，帧 8 与倒数第 9 帧才是
  完全显影的安全内容帧。把所有黑帧直接判成失败会误报模板自己的转场。
- Windows 本机可解析 `ffmpeg` 与 `ffprobe` 8.0.1。无网络 30 帧合成校准中，单次 `select` 精确抽取了
  0 / 8 / 14 / 21 / 29 五帧；首尾 PNG 为预期黑场，但 `blackdetect` 只报告片头，没有在 EOF 报告片尾
  黑场。因此黑场证据必须同时使用固定端点帧与像素统计，不能只依赖 `blackdetect` 日志。
- 证据抽取是渲染后的派生作业。若把它放进 `render_story_video` Tool，抽帧失败会让一个已经有效的 MP4
  被丢弃或形成“失败 Tool 已产生视频”的不确定副作用；独立作业能保留同一视频并单独处理证据失败。

## In scope

### 1. 固定创建请求

新增 owner-scoped 创建入口：

```text
POST /agent-loop/videos/{video_id}/evidence-packs
```

请求 v1 只接受：

```json
{
  "schema_version": 1,
  "profile_id": "narrated_panel_review_v1",
  "idempotency_key": "<caller-stable-key>",
  "expected_video_sha256": "<64-lowercase-hex>",
  "expected_render_manifest_sha256": "<64-lowercase-hex>",
  "previous_pack_id": null,
  "qualifier_groups": [
    {
      "qualifier_key": "S03-reconstruction-and-possibility",
      "scene_key": "S03",
      "required_exact_fragments": [
        "依据遗迹和类比做的重建",
        "可能"
      ]
    }
  ]
}
```

- `schema_version` 只接受 1，`profile_id` 只接受 `narrated_panel_review_v1`。
- `idempotency_key` 为 1–120 个安全字符；同一 video + key + 请求 hash 重放返回同一 Pack，内容不同返回
  409，不创建第二个作业。
- `expected_video_sha256` 必须与数据库 Asset hash 和重新计算的真实文件 hash 同时相同。
- `expected_render_manifest_sha256` 必须与 Video 所属 Run 的冻结 Manifest hash 相同，防止把正确视频引用到
  错误的生产记录。
- qualifier group 为 0–10 组，key 与 Scene key 都必须唯一且使用安全标识；每组 1–4 个逐字片段，每段
  1–160 字符。服务端只在该 Scene 的持久化 Subtitle cues 中做逐字、唯一匹配，不做模糊搜索、摘要、
  同义词或模型判断。
- 服务端自动定位与片段相交的 cue；所有 group 合计最多选择 20 个 cue frame。片段不存在、出现多次、
  Scene 没有持久化字幕或超过上限时在 Pack 写库前拒绝。
- `previous_pack_id` 只用于显式人工重试的审计链，必须属于同一 owner、同一 video 且已终态；不覆盖旧 Pack。
- 创建请求不接收时间戳、帧号、文件路径、ffmpeg 参数、阈值、输出格式、尺寸、模板或任意 shell 文本。

### 2. 资格与只读预检

创建前服务端必须证明：

- 当前认证用户是 Video 所属 Conversation owner；Admin 身份不构成替其他 owner 创建证据的授权。
- Video 对应 Run 为 Manifest-bound，Run 的 Manifest hash 非空，Video Scene 快照全部携带同一 Manifest
  hash、唯一 manifest Scene key 和持久化 Subtitle lineage。
- 模板、宽高、fps、视频帧数、时长和 Asset 类型分别为
  `narrated-panel-16x9-1080p-v1`、1920×1080、30、正值、`video/mp4`。
- Scene 数为 1–30；每镜 `duration_ms` 为正，按模板固定公式
  `ceil(duration_ms / 1000 * 30)` 得到的连续帧区间总和与 Video `duration_in_frames` 完全相同。
- 每镜至少 19 帧，使本地帧 0、8、中点、倒数第 9 帧和末帧五个角色互不越界；不为短 Scene 猜测替代点。
- Video Asset、Run Manifest、Scene / Subtitle lineage 或真实文件 hash 任一不一致时不创建 Pack、不入队。

### 3. 持久化模型

新增 `native_agent_video_evidence_packs`：

```text
id
video_id                         FK native_agent_videos.id CASCADE
previous_pack_id                 nullable self FK RESTRICT
archive_asset_id                 nullable unique FK file_assets.id RESTRICT
status                           queued | running | cancel_requested | cancelled | succeeded | failed
schema_version                   1
profile_id                       narrated_panel_review_v1
idempotency_key
request_sha256
source_video_sha256_snapshot
render_manifest_sha256_snapshot
sampling_request_json
sampling_plan_json
sampling_plan_sha256
evidence_manifest_json           nullable
evidence_manifest_sha256         nullable
frame_count                      nullable
ffmpeg_version_snapshot          nullable
ffprobe_version_snapshot         nullable
attempts                         default 0
cancel_requested_at / started_at / finished_at
error_code / error_message
created_at / updated_at
```

- 唯一约束 `(video_id, idempotency_key)`；索引只增加 `(status, created_at)` 恢复扫描和
  `(video_id, created_at)` 有界列表。
- `succeeded` 必须同时具有 archive Asset、evidence manifest / hash、正 frame count 和二进制版本；其他状态
  不得伪造成功字段。数据库 Check Constraint 保护全有 / 全无组合。
- `FileAssetPurpose` 新增 `generated_video_evidence`；一个成功 Pack 只保存一个 ZIP Asset，不把几十张帧图
  混入普通 `generated_image`。
- 历史 Video 不回填；没有 Pack 就表示没有证据，不推断为失败或通过。

### 4. 小型后台作业

- 创建 API 在一个事务中保存 `queued` Pack，提交后只把 Pack ID 放入独立进程内队列并返回 202。
- 默认并发 1；数据库是状态事实来源，不引入 Redis、Celery、外部队列或新服务。
- 新配置 `FFMPEG_EXECUTABLE` 与现有 `FFPROBE_EXECUTABLE` 一样必须显式解析为可执行文件；本地启动脚本
  同时校验二者，容器继续使用已安装的 ffmpeg 包。不从不确定 PATH 静默寻找第二个二进制。
- Worker 开始前重新加载 Pack、Video、Run、Asset 和取消状态，只处理 `queued` ID。
- 无自动重试，`attempts` 最大为 1。服务重启时 `queued` 重新入队；遗留 `running / cancel_requested` 因
  文件写入不能由数据库证明是否完成，明确收敛为 `failed / interrupted_before_evidence_commit`，不自动
  覆盖存储或重复生成。人工可用新 key 和 `previous_pack_id` 创建新 Pack。
- queued 取消立即进入 `cancelled`；running 取消必须终止本地 ffmpeg 子进程、清理临时目录且不保存
  Archive Asset。取消是状态迁移，不删除历史。

### 5. 固定帧计划

对每个 Scene 使用真实帧区间，不使用计划秒数：

```text
scene_frames = ceil(duration_ms / 1000 * 30)
scene_start = sum(previous scene_frames)
scene_end_exclusive = scene_start + scene_frames
```

固定五个本地帧角色：

| role | local frame | 证据用途 |
| --- | ---: | --- |
| `expected_dark_start` | `0` | 证明模板预期淡入起点，不把它误判为故障 |
| `safe_start` | `8` | 淡入完成后的 Motion / 对象安全起点 |
| `midpoint` | `floor((scene_frames - 1) / 2)` | 每镜主要画面与通常字幕状态 |
| `safe_end` | `scene_frames - 9` | 淡出开始前的 Motion / 对象安全终点 |
| `expected_dark_end` | `scene_frames - 1` | 证明模板预期淡出终点 |

Qualifier cue 使用离散可见帧区间：

```text
first_visible = ceil(cue.start_ms * 30 / 1000)
last_visible = ceil(cue.end_ms * 30 / 1000) - 1
target = floor((first_visible + last_visible) / 2)
```

若区间没有任何 30fps 可见帧则明确失败。所有绝对帧按升序去重，但 Manifest 为每个物理帧保留全部 role、
Scene、qualifier group 和 cue 索引。通用上限为 30×5 + 20 = 170 个逻辑目标；去重后的物理帧不得更多。

### 6. 文件级复验与提取

Worker 在临时目录内按固定顺序执行：

1. materialize 同一个 Video Asset，重新计算 bytes SHA-256；
2. 用 ffprobe JSON 再确认一个 H.264 / yuv420p 1920×1080 30fps 视频流、一个 AAC 音频流、帧数与时长；
3. 用 ffmpeg 完整解码音视频到 null，`-xerror` 下必须零错误退出；
4. 一次 `select` 调用按排序后的绝对帧号输出 PNG，禁止逐帧启动 170 个进程；
5. 逐张解码 PNG，要求 1920×1080、非空、数量精确；计算 SHA-256、平均亮度、亮度标准差和黑像素比例；
6. 另行运行固定参数 `blackdetect`，只保存结构化区间作为辅助观察，不把其缺失或命中单独当成人工结论；
7. 生成 canonical evidence manifest、离线 `index.html` 和一个确定顺序 ZIP；
8. ZIP 保存为唯一 `generated_video_evidence` Asset 后，在一个数据库事务中绑定 Pack 并标记 succeeded。

命令必须使用参数数组和经过整数校验的 select 表达式，不经过 shell。错误记录固定安全摘要，不保存本地绝对
路径、完整 stderr、环境变量、签名 URL 或凭据。

### 7. 证据 Archive

ZIP 内固定：

```text
manifest.json
index.html
frames/
  0001-S01-expected-dark-start-f000000.png
  0002-S01-safe-start-f000008.png
  ...
```

- `manifest.json` 保存 source Video / Asset / Manifest hash、采样计划 hash、模板、fps、Scene 帧区间、每帧
  role / cue 映射、PNG hash / 尺寸 / 像素统计、decode 结果、blackdetect 结构化观察和二进制版本。
- `index.html` 不引用公网 CSS、JS、字体或视频 URL；只以转义后的本地数据组织逐镜五帧、qualifier 帧、
  黑场观察和“证据完整不等于审核通过”警告。解压后可直接打开并点进原尺寸 PNG。
- ZIP entry 使用排序后的固定路径、固定时间戳和固定压缩参数；Manifest hash 必须对同一计划与帧 bytes
  稳定。Archive hash 另由 FileAsset 记录，不写回 Manifest 形成循环依赖。
- Archive 不复制原 MP4、Audio、Subtitle 或审核文件，避免放大存储和泄露其他路径。

### 8. API、权限与人工交接

新增：

```text
GET  /agent-loop/videos/{video_id}/evidence-packs?limit=1..20
GET  /agent-loop/video-evidence-packs/{pack_id}
POST /agent-loop/video-evidence-packs/{pack_id}/cancel
```

- 列表稳定按 `created_at DESC, id DESC`，只返回摘要；详情才返回 sampling plan 与 evidence manifest。
- `generated_video_evidence` Asset 读取权限由 Pack → Video → Run → Conversation owner 证明；未知和越权统一
  返回 404，不泄露存在性。Admin 只读行为遵守既有 Asset 规则，但不能替 owner 创建或取消 Pack。
- Render Tool 成功只产生 `rendered_awaiting_frame_evidence`；Pack `succeeded` 且 required frames 齐全后，
  操作记录才可写 `ready_for_full_watch_review`。
- Pack 只报告 decode、抽帧、哈希、像素观察和证据完整性。字幕可读、对象安全、事实限定词是否被听见、
  画面是否跳变以及整片是否通过，仍由真实人完整播放同一个 MP4 后签字。

## Out of scope

- 不实施或绕过 Sprint 181、G2-B、Sprint 187、188、189。
- 不渲染 Paynes Creek，不调用火苗、SiliconFlow、图片、VL、TTS、Whisper、Remotion、YouTube、账单或发布。
- 不增加 Agent Tool，不让模型选择采样点，不用 VL 自动判断成片，不生成 AI 质量结论。
- 不支持任意模板、任意 fps、任意帧表达式、任意 ffmpeg filter、视频编辑、转码、补帧或修复。
- 不把 evidence frame 登记为普通图片，不增加通用媒体库、通用视频审批表或前端审核工作台。
- 不自动重渲染、自动重抽、替换视频、降低分辨率、切换二进制、压缩成低清证据或发布视频。
- 不把 `blackdetect`、像素指标、离线 HTML 或 Pack success 当作 `pass_local_pilot`。

## Deliverables

- `backend/app/core/config.py` 与本地启动入口：显式 `FFMPEG_EXECUTABLE`。
- `backend/app/models/enums.py`、`backend/app/models/entities.py`：Evidence status、FileAsset purpose 与 Pack 表。
- 新 Alembic revision：表、FK、约束和两个有依据的索引。
- `backend/app/schemas/native_agent.py`、`backend/app/api/native_agent.py`：创建、列表、详情、取消。
- `backend/app/services/native_agent_video_evidence.py`：资格、计划、ffprobe、完整解码、抽帧、像素统计、
  canonical manifest、离线 HTML 与 ZIP。
- `backend/app/services/native_agent_video_evidence_worker.py`：单进程队列、恢复、取消与终态。
- `backend/app/api/assets.py`：Evidence Archive owner 读取。
- `backend/tests/test_native_agent_video_evidence.py` 与 startup / Asset 权限聚焦回归。
- 本架构蓝图、Paynes Creek G8-C 协议 / 空白请求模板、规格和进度同步。

## Done means

### 资格与创建

- 只有 owner 的 Manifest-bound 1080p / 30fps / 固定模板成功 Video 能创建 Pack；视频 hash、Manifest、
  Scene timeline、Subtitle lineage 和 qualifier 逐字片段全部在写库前校验。
- 同一 video + idempotency key 相同请求只创建一个 Pack；请求漂移、跨 owner、旧模板、非 30fps、坏 hash、
  短 Scene、片段缺失 / 重复或超过 20 cue frame 都零入队。

### 执行与证据

- Worker 只按 Pack ID 读取数据库；每镜五角色、qualifier cue 和绝对帧计划可重复计算且总帧数有界。
- 真实 Video bytes、ffprobe、完整 decode、一次 select、PNG 数量 / 尺寸 / hash 与 ZIP 结构全部通过后才成功。
- Paynes Creek 12 镜空白校准预期为 60 个固定角色目标，加 4 组未来 qualifier 所解析的 4–20 个 cue 目标；
  当前模板不填真实帧号或伪造 Pack。
- `blackdetect` 只作为辅助；首尾 endpoint PNG 与像素指标始终存在，能够显示预期淡入淡出和异常观察。
- Archive 只含 manifest、离线 HTML 与 PNG，不含 MP4、凭据、绝对路径或外部依赖。

### 状态、恢复与不回归

- queued / running / cancel_requested / cancelled / succeeded / failed 状态、时间、attempt 和安全错误均可读。
- 无自动 retry；重启中断明确失败，显式新 Pack 通过 `previous_pack_id` 保留历史；取消不留下成功 Asset。
- 普通 Video、普通 Run、既有 Asset 权限、Remotion 渲染、发布登记和历史 API 不变。
- Render Tool success 不再直接声称可人工验收；只有同一视频 hash 的 Pack 成功才开放完整观看。

### 人工边界

- Pack success 不写 `pass_local_pilot`、不创建 PublishableVideo，不自动判定字幕、事实、声音或视觉质量。
- 人工完整观看记录必须确认同一个 Video SHA-256 和 Evidence Manifest SHA-256。

## Verification

```powershell
& backend/.venv/Scripts/python.exe -m unittest `
  backend.tests.test_native_agent_video_evidence `
  backend.tests.test_native_agent_loop `
  backend.tests.test_native_agent_recovery `
  backend.tests.test_video_audio_tasks

& backend/.venv/Scripts/python.exe -m compileall backend/app
./scripts/check.sh
git diff --check
```

Migration checks:

1. 空 SQLite 从 base 升级到实施时 head，确认 Pack 表、FK、唯一约束、成功字段约束和两个索引。
2. 前一 revision 含历史 Video 的库升级后，历史行和 Asset 数不变、Pack 表为空。
3. 插入合法 queued / succeeded Pack，分别验证空 / 全成功字段组合；半空 succeeded 被数据库拒绝。
4. downgrade 后移除 Pack 表和新 purpose 依赖，其他 Video / Asset 数据保留。

Focused assertions 至少覆盖：

1. 两 Scene 合成视频的帧区间、每镜五角色和 cue 中点离散映射。
2. 30 Scene + 20 qualifier 的 170 上限，重复物理帧去重但 roles 不丢。
3. qualifier 片段跨 cue、缺失、重复和短到无 30fps 可见帧。
4. ffmpeg select 只启动一次；缺帧、多帧、坏 PNG、错尺寸、decode / probe / blackdetect 解析失败。
5. endpoint 黑帧存在但不自动失败；safe frame 黑 / 低方差只形成结构化 observation。
6. canonical plan / manifest / ZIP entry 顺序与 hash 稳定，Archive 不含路径和 MP4。
7. idempotency、跨 owner、取消、startup 中断、显式 previous pack 和 Asset 读取权限。
8. Pack 成功只开放完整观看，不改变 Run / Video 终态、不登记发布。

无网络校准：

- 用 ffmpeg 生成两个不同色块、各自 8 帧淡入淡出的 30fps 1920×1080 H.264/AAC 合成视频；
- 运行完整 Pack，核对每镜 5 个角色、首尾近黑、safe / midpoint 可见、HTML 本地图片可打开；
- 用浏览器打开解压后的 `index.html`，检查桌面和窄屏、无外部请求、无控制台错误；
- 修改一个视频 byte、一个 Scene duration、一个 qualifier fragment 和一个输出 PNG，分别证明对应校验失败。

## Risks / notes

- 像素统计和 `blackdetect` 只能提示异常，深色考古画面可能自然接近黑；最终视觉判断必须由人完成。
- 一个 ZIP 而不是几十个 FileAsset 牺牲了逐帧资产查询，但让持久化、权限、下载和失败边界保持小而完整；
  离线 HTML 已提供逐帧浏览，不需要在本 Sprint 建前端图库。
- 对象存储写入仍不是数据库事务；中断不会自动重写。失败 Pack 保留安全状态，人工用新 Pack 重试，并由
  运维按既有未引用资产清理规则处理可能的孤立对象。
- 本能力服务首支本地样片和同模板后续视频，不是通用视频质检平台。

## Handoff

- 当前只允许评审设计；用户没有明确批准 Sprint 190 / G8-C 前，不修改运行代码、迁移或配置。
- Sprint 189 离线通过后，可实施 Sprint 190；两者均通过才产生 `pass_for_single_g8_render`。
- 真实 G8 仍需单独成本与运行授权。视频成功后用同一 SHA-256 创建 Evidence Pack，Pack 成功再由人完整
  观看；之后按 [Sprint 191 不可变验收合同](sprint-191-native-agent-immutable-local-pilot-acceptance.md)对同一
  Video / Manifest / Evidence exact hash 签署终态。任何结果都不自动开放 G9。
