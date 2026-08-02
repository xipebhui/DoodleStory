# Sprint 154：YouTube 赛道验证包与 Agent 流程设计

## 状态

Complete

## Goal

在不进入业务开发、不创建发布任务和不改变现有 Agent Runtime 的前提下，选择最适合当前
DoodleStory 媒体能力的一个 YouTube 首轮验证方向，并交付可复用的流程设计与外部依赖准备清单。

## In Scope

- 调研近期公开 YouTube 平台趋势、动画 / 虚拟创作信号与 AI 内容政策，并在文档中保存来源链接和
  证据强度。
- 按“旁白 + 原创插画 / 静态分镜 + 字幕 + Remotion 视频 + 人工发布”的当前能力筛选赛道，明确
  推荐、备选与暂不适合方向。
- 为推荐赛道设计一轮不超过 6 条视频的验证计划、可比较指标、固定变量、唯一主动变量、停止条件和
  人工 Gate；不把研究判断当作已验证市场结论。
- 新增可复用的 Agent 流程设计模板和外部依赖准备清单，服务后续任何 YouTube 赛道的独立 Sprint。
- 将这些资料集中放入 `docs/strategy/youtube/`，避免分散到既有 API、产品和抖音实验文档中。

## Out of Scope

- 不创建新的 Native Skill、Function Tool、数据库 schema、前端页面或队列逻辑。
- 不调用模型、生图、TTS、Remotion、YouTube 发布平台或任何真实发布接口。
- 不将第三方频道的标题、脚本、画面或素材直接复刻为内容。
- 不承诺播放量、订阅增长、变现资格或赛道必然成立。

## Deliverables

- `docs/strategy/youtube/README.md`：验证包索引与推荐阅读顺序。
- `docs/strategy/youtube/2026-08-youtube-niche-validation.md`：赛道比较、首选方向、公开证据、
  对标观察对象与首轮实验设计。
- `docs/strategy/youtube/agent-flow-design-template.md`：新赛道 Agent 的 Skill、Tool、Artifact、
  Gate、状态和验收模板。
- `docs/strategy/youtube/external-dependency-readiness.md`：账号、研究来源、媒体、发布、数据、
  合规和成本的准备清单。
- 本合同与 `docs/progress.md` 的完成记录。

## Done Means

- 文档明确写出推荐结论来自“平台公开信号 + 当前产品适配度”的推断，而非对某个赛道已成功的承诺。
- 任何后续开发者可用流程模板写出一个新的小 Sprint，而不跳过副作用 Gate、证据账本、失败状态或
  发布后数据回流。
- 首轮验证计划不依赖新增开发即可被人工执行；若要自动化分析或批量化，文档明确标出这是后续需求。

## Verification

```powershell
git diff --check
# 检查新增 Markdown 的本地索引链接、标题层级和来源 URL。
```

Manual checks:

- 逐项核对推荐赛道与当前 HTML 架构导览中列出的媒体能力、单实例边界和发布确认规则。
- 逐项核对 YouTube 政策表述是否来自官方 Help / Blog，且没有把外部频道数据作为决定性市场结论。

## Risks / Notes

- 本轮采用“英文 / 全球受众也可理解的内容”作为比较基准，因为尚未指定目标国家与语言；这不是最终
  市场选择。语言、频道定位和账号已有基线确定后，首轮实验的题目与指标需要重新收紧。
- 内容迭代控制器的“先预测、单变量、真实数据后再升级规则”原则适用于 YouTube；现有抖音样本、
  权重、账号绑定与发布指标不能直接迁移为 YouTube 结论。

## Handoff

- 下一步：用户确认首选方向和目标语言后，先创建一个只做“对标频道研究 → 研究报告 → 3 个选题 →
  人工确认”的实现 Sprint；不要先开发全自动制片或自动发布。
