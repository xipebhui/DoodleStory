# Sprint 188：Native Agent YouTube 1080p 固定渲染 Profile（G8-A）

状态：Ready for review（未授权实施；默认排在 Sprint 187 / G7-0 之后）

## Goal

为 `render_story_video` 增加一个版本化、可审计的 `youtube_16_9_1080p` 输出预设，使通过 16:9 图片 Gate
的源图可以在不拉伸、不补黑边、每边基准裁切不超过 1% 的前提下，生成并用真实文件探针确认
1920×1080、30 fps、H.264/AAC 的 MP4。现有跟随源图尺寸的渲染行为必须保持不变。

## Preconditions and ordering

- 当前可执行开发入口仍是 Sprint 181 / G2-A；本合同设计完成不改变该顺序，也不授权运行 Remotion。
- 默认实施顺序为 Sprint 181 / G2-A → G2-B → G3–G6 → Sprint 187 / G7-0 → G7 →
  Sprint 188 / G8-A → G8 Manifest 与真实本地成片。
- Sprint 188 实施时必须先 rebase，并以 Sprint 187 完成后的 `render_story_video` 输入、快照和测试为基线。
- Paynes Creek 的 1920×1080 交付要求保持不变；不能把 1792×1024 或其他 Provider 实际尺寸降格成新的
  交付标准。

## Current evidence

- 图片 Gateway 对 `16:9` 当前请求 `1792×1024`；图片结果只要求相对 16:9 偏差不超过 2%，实际输出尚未
  通过真实 Paynes Creek 图片调用确认。
- `render_remotion_video()` 当前把 Composition 宽高设为首张图片真实宽高，只把奇数边补成偶数；不会
  输出固定 1920×1080。
- `NarratedPanels` 已使用 `objectFit: cover` 和中心变换；当 Composition 与源图同尺寸时没有额外比例裁切，
  但固定 16:9 Composition 需要明确计算基准裁切。
- 当前 Node stdout 返回模板、宽高、fps 和帧数，Python 会直接保存这些值；最终 MP4 没有在持久化前做
  视频流、音频流、codec、真实宽高、fps 和真实时长探针。
- `FFPROBE_EXECUTABLE` 已是现有显式配置，可复用；不需要新增二进制依赖或隐藏 PATH fallback。

## In scope

### 1. 受控输出枚举

给 `render_story_video` 增加顶层参数：

```text
output_preset: "source" | "youtube_16_9_1080p" = "source"
```

- `source` 保持当前行为：Composition 跟随首图偶数化宽高，模板 ID 仍为 `narrated-panel-v1`。
- `youtube_16_9_1080p` 固定使用 `narrated-panel-16x9-1080p-v1`、1920×1080、30 fps。
- 不接受模型提供任意宽高、裁切百分比、object-fit、字幕 CSS、codec、fps 或模板 ID。
- G8 专用 Skill / Manifest 未来必须显式提交 `youtube_16_9_1080p`；不能依赖默认值猜测交付规格。
- 规范化后的 `output_preset` 必须进入 Tool Step 输入、Tool Item、事件、trace 和重试参数比较；同一
  `tool_call_id` 不能用另一个 preset 重放。

### 2. 版本化 Remotion 模板

- 保留 `narrated-panel-v1` 的动态宽高 Composition，不静默改变既有竖屏、3:4 或其他历史工作流。
- 新增 `narrated-panel-16x9-1080p-v1` Composition；复用现有 Scene、字幕、淡入淡出、七种 Motion 和 BGM
  逻辑，只把输出尺寸固定为 1920×1080。
- Node manifest 只接受两个已知模板 ID，并校验模板与尺寸的合法组合：
  - `narrated-panel-v1`：64–4096 的偶数动态宽高；
  - `narrated-panel-16x9-1080p-v1`：只能是 1920×1080。
- `render.mjs` 必须使用 manifest 中经过校验的模板 ID 选择 Composition，不能继续硬编码旧模板。

### 3. 16:9 来源与裁切预算

`youtube_16_9_1080p` 对每张源图执行：

1. 宽高仍在 64–4096；
2. 相对 16:9 的比例偏差不超过现有图片 Gate 的 2%；
3. 所有 Scene 与首图的实际比例绝对差不超过现有 0.01；
4. 固定 `objectFit: cover`、中心对齐、等比缩放；不允许非等比拉伸或黑边；
5. 由服务端计算基准中心裁切轴和每边比例，任何一边超过 1% 就在 Node / Remotion 前拒绝。

若源图比例为 `r_s`、目标比例为 `r_t=16/9`：

```text
r_s < r_t: vertical_crop_per_edge = (1 - r_s / r_t) / 2
r_s > r_t: horizontal_crop_per_edge = (1 - r_t / r_s) / 2
r_s = r_t: crop = 0
```

`1792×1024` 的基准裁切为上下各 `0.0078125`，即源图上下各 8 px；统一放大到 1920×1080。该裁切是
版本化模板的确定性行为，不等于允许任意裁切。已有 Motion 产生的动态裁切继续由 G5 / G6 的逐镜安全区
证据约束，不能借新 Profile 放宽。

### 4. 真实文件探针

`youtube_16_9_1080p` 的 Node 渲染成功后、读取 bytes 和保存 FileAsset 前，使用配置的
`FFPROBE_EXECUTABLE` 对临时 MP4 执行一次 JSON 探针，并要求：

- 恰好一个视频流：`codec_name=h264`、`pix_fmt=yuv420p`、1920×1080、30 fps；
- 恰好一个音频流：`codec_name=aac`；
- 真实容器时长为正；
- 真实时长与 `duration_in_frames / 30` 的差不超过一帧；
- Node 返回的模板 ID、宽高、fps 和帧数与选定 Profile / 计算值完全一致。

探针缺失、非零退出、JSON 非法、流缺失、codec / 尺寸 / fps / 时长不符时，Tool 明确失败，不信任 Node
stdout 兜底，不保存 Video 或 FileAsset。`source` preset 保持现有探针行为，不在本 Sprint 强制新增部署要求。

### 5. 持久化事实

- 新视频继续使用现有 `NativeAgentVideo.template_id_snapshot`、`width`、`height`、`fps`、
  `duration_in_frames` 和 `duration_ms`；不新增数据库列或迁移。
- `youtube_16_9_1080p` 的 `duration_ms` 使用 ffprobe 的真实文件时长，不再用 Scene Audio 毫秒简单求和；
  每镜 Audio 时长仍保留在 Scene 快照。
- Scene 快照在 Sprint 187 lineage 字段之外增加：
  - `source_image_width_px`
  - `source_image_height_px`
  - `baseline_cover_crop_axis`: `none | horizontal | vertical`
  - `baseline_cover_crop_per_edge_ratio`
- `output_preset` 已保存在 Tool Step / Item / Event；视频的模板 ID 与实际宽高共同构成不可变输出 Profile
  快照。历史视频不回填。

### 6. 字幕与 Motion 边界

- 新模板复用现有字幕容器：左右 72 px、距底 150 px、最大宽 936 px、字号 58 px；本 Sprint 不同时改
  字幕样式变量。
- 本地离线 smoke 必须用两行中文字幕抽帧，确认没有越界；这只是模板能力证据，Paynes Creek 仍需 G8
  最终逐镜字幕安全区与完整观看审核。
- 七种 Motion 数值不变；不增加任意缩放 / 平移参数、转场或自动镜头重构。

## Out of scope

- 不实现 Sprint 181、G2-B、Sprint 187 或其他前序 Gate。
- 不调用模型、图片 Provider、VL、TTS、Whisper、YouTube、账单或发布接口。
- 不渲染 Paynes Creek 真实素材，不填写真正 G8 结果，不开放 G8 或 G9。
- 不修改图片 Gateway 请求尺寸，不把 1792×1024 伪装成实际 Provider 输出。
- 不删除或改变 `source` preset，不强制历史视频或其他画幅改成 1920×1080。
- 不接受任意尺寸、任意 crop、contain / blur-fill、拉伸、黑边、自动补画、超分、插帧或 Provider 切换。
- 不修改字幕字体、颜色、字号、位置、Motion 参数、BGM、H.264/AAC 编码设置或前端播放器。
- 不新增数据库表、列、迁移、API endpoint、后台队列、外部渲染服务或分布式基础设施。
- 不创建 G8 Skill，不生成最终 Render Manifest；这两项在 Profile 离线通过后另立操作合同。

## Deliverables

- `backend/app/services/remotion_video.py`
  - preset 映射、16:9 / crop 校验、固定模板 manifest、Node 结果校验和 ffprobe 文件探针。
- `backend/app/services/native_agent_loop.py`
  - Tool 参数 / 描述、preset 传递与 Scene 裁切快照。
- `backend/app/services/native_agent_persistence.py`
  - preset 进入 prepared Tool 参数与重试一致性事实。
- `remotion/src/Root.tsx`、`remotion/src/types.ts`、`remotion/manifest.mjs`、`remotion/render.mjs`
  - 双模板注册、模板—尺寸校验和动态 Composition 选择。
- `backend/tests/test_remotion_video.py`、`backend/tests/test_native_agent_loop.py`、
  `remotion/tests/manifest.test.mjs`
- `docs/architecture/native-agent-youtube-1080p-render-profile-blueprint.md`
- `docs/spec.md`、`docs/progress.md` 与 Paynes Creek 生产 / 验收文档同步。

明确不属于 Deliverables：Alembic migration、实体 / API Read Schema、前端、G8 Skill、Paynes Creek 媒体。

## Done means

### 现有行为不回归

- 未提供 `output_preset` 或显式使用 `source` 时，Tool Schema 默认、模板 ID、首图偶数化输出、比例拒绝、
  字幕、Motion、BGM、幂等和持久化行为与当前一致。
- 旧 `narrated-panel-v1` 仍可渲染竖屏 / 3:4；不会被固定到 1920×1080。

### 固定 Profile

- `1792×1024` Scene 被计算为上下各 0.78125% 基准裁切，生成 manifest 为
  `narrated-panel-16x9-1080p-v1 / 1920×1080 / 30fps`。
- 精确 1920×1080 源图的基准裁切为 0；2% 比例边界内的图片每边裁切不超过 1%；超界或混合比例在
  Node 前拒绝。
- 新模板不拉伸、不补黑边，复用现有 Motion 与字幕；离线校准帧证明两行字幕位于画布内。

### 真实文件与持久化

- ffprobe 真实确认 H.264 / yuv420p、AAC、1920×1080、30 fps、一个视频流、一个音频流和正时长。
- Node stdout 与 ffprobe 任一冲突都明确失败；失败时不保存 Video / FileAsset。
- 成功 Video 的模板、真实宽高、fps、帧数、真实时长以及每 Scene 源图尺寸 / crop 快照可从 API 与数据库
  回查。
- 同一成功 Tool Call 重放复用原视频；preset 变化不能伪装为同一参数重试。

## Verification

```powershell
npm test --prefix remotion
npm run typecheck --prefix remotion

& backend/.venv/Scripts/python.exe -m unittest `
  backend.tests.test_remotion_video `
  backend.tests.test_native_agent_loop

& backend/.venv/Scripts/python.exe -m compileall backend/app
./scripts/check.sh
git diff --check
```

聚焦测试至少覆盖：

1. `source` 未提供 / 显式提供时行为相同。
2. 未知 preset 被 Function Schema 拒绝。
3. `1792×1024`、精确 1920×1080、2% 上下边界的 crop 轴与比例计算。
4. crop 每边超过 1%、单图偏离 16:9 超过 2%、Scene 比例差超过 0.01 时 Node 调用为 0。
5. 两个模板 ID 与尺寸合法组合通过，交叉组合拒绝。
6. Node 选择 manifest 中的新模板，旧模板仍可动态尺寸渲染。
7. Node stdout 模板、宽高、fps 或帧数不匹配时拒绝。
8. ffprobe 缺失、非零、非法 JSON、多流 / 缺流、非 H.264 / AAC、非 yuv420p、非 30 fps、非
   1920×1080 或时长偏差超一帧时均拒绝。
9. 成功视频保存实际探针元数据、模板 ID、preset 参数和 Scene crop 快照。
10. 同一 Tool Call 重放不执行第二次 Node / ffprobe / 文件保存。

Offline real smoke：使用本地生成的 1792×1024 校准网格、两行中文字幕和短音频运行一次真实 Remotion，
用 ffprobe 与抽帧确认 1920×1080、30 fps、H.264/AAC、上下等量中心裁切、无拉伸 / 黑边和字幕不越界；
不调用任何外部服务。

## Risks / notes

- 2% 源图比例容差数学上对应每边最多约 1% 的 cover 裁切；这只是基准裁切，不包含既有 8% zoom 与 3%
  pan。后者必须继续逐镜探针和人工复核。
- 新模板 ID 是行为版本边界；以后若改变字幕、Motion、裁切或编码，必须新建模板版本，不能改写历史含义。
- ffprobe 只证明文件结构与技术参数，不证明字幕可读、事实准确、声音自然或整片节奏合格。
- 本合同解除精确交付尺寸阻塞，不代表 Render Manifest、完整观看或本地样片已经通过。

## Handoff

- 默认先完成 Sprint 181、G2-B、Sprint 187 和 G7；随后由用户明确回复“批准 Sprint 188”或
  “批准 G8-A”才实施。
- Sprint 188 离线实现与真实本地校准通过后，才设计 / 冻结 Paynes Creek 12 镜 G8 Render Manifest。
- Profile 通过不授权使用 Paynes Creek 真实媒体运行 Remotion，也不授权发布。
