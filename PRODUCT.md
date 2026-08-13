# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- 内容创作者和运营人员：把来源材料、故事或知识方案转成可审核的图片、语音、字幕与视频资产。
- Agent 流程设计者：复用持久化 Run、Skill、Tool、Artifact 和 Approval 语义，搭建新的内容生产流程。
- 管理员：维护用户、风格、Provider、YouTube 频道和发布任务，并检查跨用户隔离与任务状态。

## Product Purpose

DoodleStory 把文本与来源材料转成可追踪的多媒体生产任务。成功不只意味着“生成了内容”，还意味着输入、模型与工具调用、生成资产、人工确认和后续发布都能回查，失败也能从持久化状态继续处理。

## Positioning

DoodleStory 的差异机制是“文件化研究与持久化 Agent 编排共同约束媒体生成”：模型负责判断下一步，受控 Tool 负责真实副作用，关键证据、版本、产物和确认保留在仓库或数据库中，而不是只存在于聊天历史。

## Operating Context

- 开发者在本地仓库中按 Sprint 契约小步交付，并通过 `docs/spec.md`、`docs/progress.md` 和研究账本保存权威状态。
- 内容运营先做选题、来源、版权和表达边界审核，再进入脚本、分镜、媒体生成、成片与发布。
- Native Agent 在 Web 工作台中运行；FastAPI、数据库、进程内 Worker 和 SSE 承担持久化执行与状态投影。
- YouTube 公开研究、DoodleStory 媒体生成和第三方视频发布是三段独立链路，不能把其中一段可用写成整条链路已验证。

## Capabilities and Constraints

- 已有文本转分镜、图片生成、图片检查、火山 Seed-TTS、Whisper WebVTT 字幕、Remotion 图片旁白视频和 YouTube 异步发布积木。
- 当前 Remotion `narrated-panel-v1` 每个 Scene 使用一张图片和一段音频，最多 30 个 Scene；所有图片比例必须一致，运动只支持 `static`、四向平移和缩放预设。
- Native Remotion 的输出宽高直接跟随首张源图，不会自动标准化为 1920×1080；16:9 内容必须先核验图片 Provider 返回的真实尺寸与各镜比例一致性。
- 当前 Seed-TTS 默认绑定中文音色，Whisper 字幕生成固定以中文识别。英语原声 YouTube 样片需要后续显式开发和验证，不能用中文样片证明。
- 现有内容实验账号只绑定了 3:4 抖音画风；YouTube 16:9 生成前必须建立并核验独立风格绑定，不允许使用默认风格。
- 发布、高成本生成以及影响外部账号的动作需要明确 Gate；研究页面和本地样片不自动变成公开内容。
- 当前 YouTube 目标频道、原始语言、审核人、数据回流权限与基线仍是开放决定；在这些输入缺失时只能做生产验证，不能创建有市场含义的发布实验。
- 本产品上下文中的 YouTube 生产验证定位，是根据现有仓库证据和用户“按合理判断设计”的授权推导；不代表用户已确认长期频道品牌。

## Evidence on Hand

- 产品与架构事实：`README.md`、`docs/spec.md`、`docs/architecture/project-guide.html`。
- 交付与验证历史：`docs/progress.md`、`docs/contracts/`。
- YouTube 研究、候选题与来源账本：`docs/strategy/youtube/`。
- 内容迭代控制器状态：`content-lab/strategy_state/`；当前没有经过真实实验反复验证的有效策略规则。
- 尚无可用于宣传的 YouTube 频道增长结果、稳定播放基线、商业案例或可复制赛道结论；后续页面不得虚构。

## Product Principles

1. 证据先于主张，主张先于媒体，媒体先于发布。
2. 研究、生成、审核和发布各自留痕，不能用“已调用”替代“已成功”。
3. 同一轮实验只改变一个主要变量；单条表现不升级为长期规则。
4. 不引入未经授权的默认回退、占位结果或静默错误处理。
5. 人工确认保护账号、版权、事实准确性和高成本副作用。

## Accessibility & Inclusion

- Web 工作台和本地研究页面应支持键盘阅读、清晰焦点、语义化结构、足够文字对比度和窄屏重排。
- 视频字幕必须保留原始语义，并为画面底部字幕安全区预留空间。
