# Sprint 156：YouTube 六题矩阵、多语言与获利路径研究

## 状态

Complete

## Goal

在不进入开发、媒体生成或发布的前提下，把历史机制候选从三个扩展为六个，核对 YouTube 多语言能力、
当前项目发布调用缺口与 YPP 普通视频 / Shorts 路径，并形成可供后续人工决策的六题研究矩阵。

## In Scope

- 为印加道路接力通信、吴哥水网和江户消防建立双来源账本，记录可支持主张、过度推断、可画链路与
  停止条件。
- 使用 YouTube 官方 Help / Data API 文档核对自动配音、多语言音轨、翻译标题 / 描述、原始语言字段
  和人工审核边界。
- 对照本地 Video API 归档与 DoodleStory 发布代码，明确当前调用已经支持和尚未支持的多语言字段。
- 使用 YouTube 官方 Help 核对 YPP 早期功能、广告收益门槛、普通视频公开观看时长和 Shorts 有效观看
  的独立路径；不做收入预测。
- 将六题按机制分组，形成仅用于后续选择的实验矩阵与发布前预测草案边界。
- 更新 YouTube 研究索引、验证建议、准备清单、研究日志和项目进度。

## Out of Scope

- 不修改 Native Skill、发布 API、数据库、前端、视频模板或任何业务代码。
- 不调用项目频道研究、模型、生图、TTS、字幕、Remotion 或发布接口。
- 不创建真实实验目录、`prediction.json` 或发布任务，因为目标语言、频道和责任人仍未确定。
- 不创建每日、定时或后台研究任务。
- 不承诺题目、语言、视频形态、YPP 资格、观看或收入表现。

## Deliverables

- 扩展 `docs/strategy/youtube/candidate-topic-source-ledgers.md`
- 新增 `docs/strategy/youtube/language-and-monetization-boundaries.md`
- 新增 `docs/strategy/youtube/six-topic-experiment-matrix.md`
- 更新验证报告、外部依赖准备清单、研究日志、目录索引和 `docs/progress.md`

## Done Means

- 六个候选题都有至少两类来源和明确停止条件。
- 文档明确区分 YouTube 平台能力、YouTube Data API 字段、外部 Video API 能力和 DoodleStory 当前调用。
- YPP 门槛只作为运营约束，不被写成内容市场或收益预测。
- 六题矩阵保持一个主要变量原则，并明确尚不能创建真实发布前预测的缺失输入。
- 控制器状态、Markdown 本地链接、关键结构和 `git diff --check` 通过。

## Verification

```powershell
py -3.11 .agents\skills\content-iteration-controller\scripts\validate_controller_state.py
git diff --check
```

另检查六个候选题与六个停止条件、本地 Markdown 链接、平台能力 / 当前项目能力措辞，以及仓库中没有
新增实验数据、媒体产物或定时任务。

验证结果：Windows 本地 Python 3.11 控制器状态校验通过且无 warning；10 份 YouTube Markdown 与本合同
的本地链接全部可解析；六个候选题和六个停止条件计数正确；能力边界措辞检查与 `git diff --check` 通过。
本 Sprint 仅修改研究文档，未运行与本次范围无关的后端、前端和 Remotion 全量测试。

## Risks / Notes

- 自动配音支持语言、功能开放范围和 YPP 门槛可能变化；进入真实实验前必须重新核对官方页面。
- 公开政策与产品文档只能说明能力和资格边界，不能说明英语、中文、普通视频或 Shorts 哪个会表现更好。
- 当前默认 16:9、90–180 秒普通视频仍是低成本验证假设，不是已证明的最佳时长。

## Handoff

完成本 Sprint 后，需要用户或频道负责人明确目标语言、频道所在地区、普通视频 / Shorts 选择和审核人，
才能创建真实实验目录与发布前预测。
