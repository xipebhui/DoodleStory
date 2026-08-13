# Sprint 173：YouTube Paynes Creek 逐镜证据板与 16:9 视觉规格

状态：已完成

## Goal

把已通过来源与授权初审的 Paynes Creek 玛雅盐业候选题，收敛成一份可直接交给脚本、图片、配音和 Remotion 阶段使用的 12 镜证据板；同时明确当前链路只能先制作中文本地生产验证片，不能把它当作 YouTube 市场实验。

## In scope

- 固定生产验证片规格：16:9、1920×1080、12 个 Scene、目标约 138 秒、中文旁白与中文字幕、无 BGM、仅使用原创解释性画面。
- 为每个镜头记录时间带、唯一主张、父场景、证据 ID、证据等级、画面构图、运动预设、允许项、禁止项和字幕意图。
- 将原 V6 具象市场交换替换成“海岸—内陆方向网络”，保留 exact routes unknown 的事实边界。
- 定义 16:9 原创视觉系统、字幕安全区、构图规则、对象锚点、共用 Prompt 约束、资产命名和制作 QA。
- 对照当前 `generate_speech`、Whisper 字幕和 `render_story_video` 的真实能力，记录能直接执行和仍需开发的部分。
- 同步一份无需服务端、无外部媒体依赖的本地 HTML 阅读板，并在桌面与移动视口检查。
- 更新 YouTube 研究索引、研究日志、项目进度和本地设计说明。

## Out of scope

- 不写最终逐字旁白、标题、描述区、缩略图文案或发布 CTA。
- 不生成图片、语音、字幕或 MP4，不创建 DoodleStory 任务。
- 不绑定或修改生产账号画风，不更改 TTS、Whisper 或 Remotion 业务代码。
- 不创建 YouTube `prediction.json`、发布任务或自动化，不登录外部账号。
- 不把候选题排序、中文样片质量或单条媒体结果写成市场结论。

## Done means

- Markdown 和 HTML 均完整覆盖 S01–S12；目标时长相加为 138 秒，每镜只有一个主要事实主张。
- 每镜都能从视觉来源与授权清单追溯到 R1–R9 和对应事实边界；重建、解释与直接证据在页面上一眼可区分。
- 所有 Scene 都使用当前 Remotion 支持的单图、单音频、统一 16:9 和合法运动预设；字幕安全区依据当前模板实际位置定义。
- 页面明确标记：中文本地生产验证可进入下一步；英语市场样片、16:9 风格绑定和正式发布仍未就绪。
- HTML 无外部脚本、字体、图片或网络请求，桌面和移动端无横向溢出、关键内容不被遮挡。
- 索引、日志、`docs/progress.md` 和设计记录同步，仓库没有敏感凭据或失效本地链接。

## Verification

- 运行内容迭代控制器状态校验。
- 检查 12 镜数量、目标时长和运动预设是否合法。
- 通过本地浏览器分别检查桌面与移动视口，并保存截图证据。
- 运行 Impeccable detector 一次，处理机械问题并记录最终审查结论。
- 检查 Markdown / HTML 本地链接、敏感字符串、`git diff --check` 和最终差异范围。

## Handoff

下一 Sprint 只进入“最终中文旁白与逐镜 Prompt 包”。通过事实、语言和 16:9 画风人工审核后，才允许提交一个本地生成任务；成片验收通过后，再决定是否开发英语 TTS / Whisper 支持并建立正式 YouTube 市场实验。

## Outcome

- 已把 V1–V7 收敛为 S01–S12：目标 138 秒、统一 1920×1080、每镜一个主张，全部使用当前 Remotion
  支持的静止、平移或缩放预设。
- 已固定 S03、S07、S09、S10 的重建 / 可能 / 具体未知表达；原 V6 具象市场戏被永久替换成有断点的
  海岸—内陆方向网络。
- 新增 Markdown 权威规格和本地 HTML 证据板；浏览器在 1440×960 与 390×844 视口确认 12 镜、138 秒、
  无控制台错误、无页面横向溢出，移动端运行 Gate 改为逐项账本。
- 最终截图证据：桌面 [首屏](../../.impeccable/reviews/sprint-173/desktop-final-hero.png)、
  [代表镜头](../../.impeccable/reviews/sprint-173/desktop-final-shot.png)、
  [运行 Gate](../../.impeccable/reviews/sprint-173/desktop-verdict-runtime.png)；手机
  [首屏](../../.impeccable/reviews/sprint-173/mobile-final-hero.png)、
  [代表镜头](../../.impeccable/reviews/sprint-173/mobile-final-shot.png)、
  [运行 Gate](../../.impeccable/reviews/sprint-173/mobile-verdict-runtime.png)。中间调试截图由同目录
  `.gitignore` 排除，不进入提交。
- 已把当前代码能力与缺口写进 Gate：中文本地生产验证可进入脚本阶段；英语原声、独立画面标签、第三方
  证据图署名层、YouTube 16:9 画风和公开发布仍未通过。
- 设计探针的内置图片生成两次因网络错误未返回；没有切换到需要 API Key 的备用路径，也没有伪造批准
  comp。页面按用户委托的“水下考古证据台 × 影片接触印样”方向完成，并通过实际桌面 / 手机截图复核。
- 本 Sprint 没有生成图片、音频、字幕或视频，没有创建 DoodleStory、实验或发布任务，也没有更新策略
  记忆和 Skill。
