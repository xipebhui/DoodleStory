# Sprint 174：YouTube Paynes Creek 中文旁白与逐镜 Prompt 包

状态：已完成

## 背景

Sprint 173 已把 Paynes Creek 玛雅盐业收敛为 12 镜、约 138 秒的中文本地生产验证片，并为每镜绑定
事实、证据等级、视觉边界和 Remotion 运动预设。当前缺少可直接交给 `generate_speech` 与
`generate_image` 的最终文本；同时，进一步核对代码后确认：图片工具只接收一段完整 Prompt，16:9
来自 Style 快照，Remotion 最终分辨率直接跟随首张源图，并不会自动标准化为 1920×1080。

## Goal

为 S01–S12 定稿中文旁白和完整、可复制到当前图片工具的逐镜 Prompt，并把语速、字幕、图片比例、
资产审核与合成顺序写成明确 Gate，使下一 Sprint 可以先建立 16:9 Style，再只提交一张高风险镜头做
本地风格与尺寸验证，而不是直接批量生成整片。

## In scope

- 每镜一段最终中文旁白；保留唯一主张、证据等级及 F / S / R 来源映射。
- 使用中文释读“佩恩斯克里克”，避免把英文专名直接交给当前中文 TTS；不在旁白中强行朗读
  `Ek Way Nal`、`Ta'ab Nuk Na` 或 `briquetage`。
- 固定 `generate_speech(text, speed=1.0)` 为首轮配音参数；以每秒约 4 个汉字做计划估算，但不伪造
  Provider 的真实音频时长。
- 为每镜编写一段自包含英文图片 Prompt：统一风格、构图、对象锚点、字幕安全区与该镜事实负面约束
  全部写进同一个 `prompt` 字段。
- 给出建议 Style 规格：`16:9`、`Qwen/Qwen-Image`、Paynes Creek 专用视觉提示；只记录配置草案，
  不创建或绑定真实 Style。
- 修正“固定 1920×1080”的实现假设：1920×1080 是交付目标，当前 Native Remotion 实际跟随首图
  宽高；统一 Gateway 的 16:9 请求尺寸当前为 1792×1024，因此必须用真实首图尺寸通过 Gate。
- 产出不含任何伪造 `image_id`、`audio_id` 或 `subtitle_id` 的生产草案，并更新索引、日志与进度。

## Out of scope

- 不调用生图、TTS、Whisper 或 Remotion Provider，不生成图片、音频、字幕或 MP4。
- 不创建或修改真实 Style、账号绑定、Agent Skill、DoodleStory Run、实验或发布任务。
- 不实现图片裁切、补边、缩放、分辨率标准化或新的 Remotion 图层。
- 不切换图片 Provider，不在失败后引入备用模型或降级策略。
- 不写 YouTube 标题、缩略图、描述区、CTA、英语脚本或市场结论。

## Deliverables

- `docs/strategy/youtube/paynes-creek-chinese-script-prompt-pack.md`
- `docs/strategy/youtube/paynes-creek-production-draft.json`
- 更新 `docs/strategy/youtube/paynes-creek-shot-evidence-board.md`
- 更新 `docs/strategy/youtube/README.md`
- 更新 `docs/strategy/youtube/research-log.md`
- 更新 `docs/progress.md`

## Done means

- S01–S12 都有最终旁白、汉字数、计划时长、证据映射和合法运动预设。
- 12 段旁白总汉字数与计划时长落在 120–150 秒生产窗口；实际时长仍明确等待真实 TTS 验证。
- S03 明说“重建”，S07 明说“可能”且否定通用货币，S09 明说运输只是解释且无货单，S10 明说
  路线、城市和买家未知。
- 12 段 Prompt 都是当前 `generate_image(prompt, provider)` 可接受的一段完整文本，不依赖未实现的
  `negative_prompt`、像素尺寸或文字叠加参数。
- 每段 Prompt 都要求关键物件位于中央 84% / 上方 70%，不生成标题、说明文字、数字、Logo 或水印，
  并逐项包含该镜的历史事实禁止项。
- 生产草案 JSON 可解析，Scene 恰为 12 个、目标时长和为 138 秒、运动预设全部合法，且没有媒体 ID。
- 文档明确下一步只允许创建 16:9 Style 并生成 S03 单镜候选；实际宽高、画风、对象和证据边界未通过
  前，不批量生成另外 11 镜。

## Verification

- 运行内容迭代控制器状态校验。
- 用脚本检查 JSON 可解析、Scene 数量、目标时长、旁白汉字数、必要限定词和运动预设。
- 检查每镜 Prompt 都包含字幕安全区、无文字要求和镜头级禁止项。
- 检查 Markdown 本地链接、敏感字符串、`git diff --check` 与最终差异范围。

## Handoff

下一 Sprint 进入第一道真实媒体 Gate：建立或选择一个专用 16:9 Style，模型只允许使用当前约束内的
`Qwen/Qwen-Image`，随后只生成 S03 一张候选图并调用 `inspect_image`。若真实图宽高不是可接受的精确
16:9，或重建装置、字幕安全区、对象锚点任一不通过，停止批量生产，明确选择“更换已授权主路径”或
“单独开发图片标准化”后再继续；不自动切换 Provider 或裁切。

## Outcome

- 已定稿 S01–S12 共 536 个汉字；固定 `speed=1.0`，按每秒约 4 个汉字估算约 134 秒。S03、S07、
  S09、S10 的重建、可能、无货单与具体路线未知均已进入原文。
- 已为 12 镜编写自包含英文 Prompt，每段均包含统一证据视觉、中央 84% / 上方 70% 安全区、无画内
  文字要求和该镜事实禁止项；不依赖当前 Tool 不支持的独立负面 Prompt 或像素参数。
- 已新增机器可读生产草案；JSON 解析通过，12 Scene 目标时长和为 138 秒，声明汉字数与实际逐段计数
  一致，运动预设全部在 Runtime 白名单内，且未写入任何伪造媒体 ID。
- 已纠正输出尺寸假设：1920×1080 是交付目标，统一 Gateway 当前对 `16:9` 请求 `1792×1024`，
  Native Remotion 最终跟随首图真实宽高。下一步先用 S03 一张真实候选核验，不能直接批量生成。
- 内容迭代控制器校验、必要限定词、Prompt 数量与安全区、Markdown 本地链接、敏感新增扫描和
  `git diff --check` 均通过。本 Sprint 没有调用媒体 Provider，没有创建 Style、Run、实验或发布任务。
