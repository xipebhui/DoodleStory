# Sprint 155：YouTube 候选题、格式与相邻赛道多轮研究

## 状态

Complete

## Goal

在不进入开发、媒体生成或发布的前提下，连续完成候选历史题证据初查、公开频道格式观察、YouTube
普通视频 / Shorts 平台边界核对和相邻赛道压力测试，并把可复核结论写入独立研究资料。

## In Scope

- 为三个“古代城市如何解决日常限制”候选题建立至少两类来源的证据账本，区分可支持主张、不可支持
  主张、可画链路与停止条件。
- 观察 History Matters、The Armchair Historian 和 Simple History 的公开标题 / 描述结构，只记录格式，
  不推断后台表现。
- 使用 YouTube 官方 Help 核对最长 3 分钟方形 / 竖屏视频的 Shorts 分类、缩略图、分析指标和音乐 claim
  边界，修正原验证计划中混用普通视频与 Shorts 指标的问题。
- 对历史助眠、神话民俗、城市 / 地理、全动画军事史和 AI 写实历史重建做当前产品适配压力测试。
- 更新验证建议、外部准备清单、持续研究日志、目录索引和进度记录。

## Out of Scope

- 不创建或修改 Native Skill、Function Tool、数据库、前端、队列或视频模板。
- 不调用 DoodleStory 模型、频道研究、图像、TTS、字幕、Remotion 或发布接口。
- 不下载第三方频道视频、脚本、音乐、图片或评论数据。
- 不创建每日 / 定时研究任务；本轮由用户明确触发后在当前任务内连续完成。
- 不承诺任何题目、格式或赛道的播放、留存、获利或增长表现。

## Deliverables

- `docs/strategy/youtube/candidate-topic-source-ledgers.md`
- `docs/strategy/youtube/format-and-adjacent-lane-review.md`
- 更新 `docs/strategy/youtube/2026-08-youtube-niche-validation.md`
- 更新 `docs/strategy/youtube/external-dependency-readiness.md`
- 更新 `docs/strategy/youtube/research-log.md` 与目录索引
- 更新本合同与 `docs/progress.md`

## Done Means

- 每个候选题至少有两类来源，并明确写出来源不能支持的过度结论。
- 首轮实验不再混用 Shorts 与普通视频的分类、缩略图和指标。
- 相邻赛道判断能追溯到当前项目能力、已有真实 smoke 缺口和平台政策，而非仅凭主观热度。
- 文档内部链接、Markdown 格式和控制器状态验证通过。

## Verification

```powershell
py -3.11 .agents\skills\content-iteration-controller\scripts\validate_controller_state.py
git diff --check
```

另运行本地 Markdown 链接与关键措辞检查，确认新增索引可解析、所有来源账本包含“不能支持 / 停止条件”，
且没有遗留“每日自动研究”表述。

## Risks / Notes

- 公开频道页不提供可靠的留存、流量来源、成本、受众和标题测试历史。本 Sprint 只能形成格式观察，不能
  形成表现排名。
- 默认推荐 16:9、90–180 秒普通视频，是为了保留当前小规模生产假设并避免被归为 Shorts；这不是时长
  或内容类型已经被真实数据验证的结论。
- 目标语言、地区、频道基线和发布责任人尚未确定，不能开始真实实验。

## Handoff

用户下一次明确启动研究时，继续补齐三个候选题来源账本，并在内容类型和目标语言已经选定的前提下，
建立对应的发布前预测模板。没有用户启动时不创建后台或每日任务。
