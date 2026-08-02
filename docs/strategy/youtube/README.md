# YouTube 赛道验证包

这里集中存放 DoodleStory 面向 YouTube 新赛道的非开发性研究与设计资料。它不替代
`docs/architecture/` 的运行架构说明，也不混入抖音的市场样本或实验结论。

## 推荐阅读顺序

1. [赛道比较与首轮验证建议](2026-08-youtube-niche-validation.md)
2. [候选历史题来源账本](candidate-topic-source-ledgers.md)
3. [历史机制六题研究矩阵](six-topic-experiment-matrix.md)
4. [第三方趋势源评估：LuluJAI](third-party-trend-source-assessment.md)
5. [多语言与获利路径边界](language-and-monetization-boundaries.md)
6. [格式观察、平台分流与相邻赛道压力测试](format-and-adjacent-lane-review.md)
7. [新赛道 Agent 流程设计模板](agent-flow-design-template.md)
8. [外部依赖准备清单](external-dependency-readiness.md)
9. [持续研究日志](research-log.md)

## 当前结论

首轮应优先验证“原创插画历史微纪录片 / 历史机制解释”，而不是立即开发全自动视频工厂。
它最贴合当前的旁白、静态分镜、字幕、Remotion 和人工发布能力；不过这只是基于平台公开信号
与产品适配度的推断，必须通过真实发布后的数据验证。

首轮发布前还必须先锁定内容类型：默认建议以 **16:9、90–180 秒的普通视频**验证单一因果问题；
若继续使用 3:4 竖屏且不超过 3 分钟，YouTube 会将其归为 Shorts，必须改用 Shorts 指标和缩略图规则，
不能与普通视频混在同一实验里。

候选池已扩展为六题，覆盖物流、通信、供水、季风水网、城市消防和排水证据。首批只使用一个原始语言；
YouTube 平台支持多语言能力，但当前 DoodleStory 发布请求尚不支持原始语言、翻译元数据或第二音轨，
不能把平台能力写成项目现成功能。YPP 普通视频与 Shorts 门槛只作运营约束，不作为首轮成功指标。

LuluJAI 会员站点可作为第三方人工雷达：长视频与 Shorts 榜单、低粉频道增长和原始 YouTube 链接能
帮助缩小候选池，但其分类和机会分数不能直接成为选题结论。本轮“英语 + 历史悬疑”前 12 条中只有
1 条严格符合事实型古代历史解释；任何候选仍必须回 YouTube 原页或官方 Data API 复核。

## 边界

- 本目录不保存 API Key、频道登录信息、受版权保护的脚本、下载的视频或私有数据。
- 外部频道仅作为格式观察对象，不复制标题、脚本、画面、音乐或素材。
- 赛道结论不能直接写入 Skill；同一机制至少需要多轮真实发布证据后，才可以成为候选规则。
