# Sprint 157：YouTube 第三方趋势源评估与接入边界

## 状态

Complete

## Goal

在不进入 Agent 开发、媒体生成或发布的前提下，评估 LuluJAI 会员站点能否作为 DoodleStory YouTube
赛道研究的辅助证据源，并把可用字段、抽样结果、可信度限制和人工接入流程写成可复核文档。

## In Scope

- 只读检查 LuluJAI 的长视频蓝海榜、月度趋势榜、低粉频道增长榜、搜索热词榜、Shorts 蓝海榜和案例
  拆解页。
- 对“英语 + 历史悬疑”交叉结果抽取至少 8 条卡片，记录分类噪声与可用于后续复核的 YouTube 原链接。
- 至少用一条 YouTube 原视频页复核标题、频道、时长、观看量与订阅量，判断第三方快照的新鲜度边界。
- 区分原始 YouTube 可见事实、LuluJAI 的派生指标 / 模型解释和本项目的研究推断。
- 设计“第三方发现候选 → YouTube 原页 / 官方 Data API 复核 → 来源账本 → 人工 Gate”的最小研究流程。
- 更新 YouTube 研究索引、验证建议、外部依赖清单、研究日志和项目进度。

## Out of Scope

- 不逆向隐藏接口，不绕过站点会员权限，不抓取或批量导出完整站点数据。
- 不保存账号、密码、Cookie、Token、个人资料或付费信息，不提交收藏、频道夹、联盟申请或任何购买。
- 不把“机会度、供给缺口、动量、爆发”等未公开计算口径直接写成市场事实。
- 不调用模型、生图、TTS、字幕、Remotion 或发布接口，不创建真实实验或定时研究任务。
- 不修改 `strategy_memory.md`、Skill 规则、业务代码、数据库、前端或发布链路。

## Deliverables

- 新增 `docs/strategy/youtube/third-party-trend-source-assessment.md`
- 更新 `docs/strategy/youtube/README.md`
- 更新 `docs/strategy/youtube/research-log.md`
- 更新 `docs/strategy/youtube/2026-08-youtube-niche-validation.md`
- 更新 `docs/strategy/youtube/external-dependency-readiness.md`
- 更新 `docs/progress.md`

## Done Means

- 文档列出已检查的六类页面、核心字段、适用研究问题和不能支持的结论。
- “英语 + 历史悬疑”至少 8 条样本被汇总，分类混杂问题有具体例证。
- 至少一条站内快照和 YouTube 原页完成同日对照，差异不被误写成精确抓取延迟。
- 明确 LuluJAI 只进入候选发现层，任何选题结论仍需要原页 / 官方 API、来源账本和人工审核。
- 仓库中没有出现登录凭据、私有账号信息、媒体产物、实验数据或定时任务。
- 控制器状态、Markdown 本地链接、敏感字符串检查和 `git diff --check` 通过。

## Verification

```powershell
py -3.11 .agents\skills\content-iteration-controller\scripts\validate_controller_state.py
git diff --check
```

另使用只保留文件名、不输出匹配正文的本地扫描检查用户凭据原文；检查本 Sprint 相关 Markdown 的
相对链接可解析、十二条样本数量、六类页面覆盖，以及所有“机会”指标均标记为第三方派生信号而非
官方事实。

2026-08-03 验证结果：控制器状态校验返回 `ok: true` 且无警告；凭据扫描无命中；7 份相关 Markdown
本地链接全部可解析；样本表为 12 条；`strategy_memory.md` 未变化；`git diff --check` 通过。

## Handoff

完成本 Sprint 后，下一步仍是研究而非开发：围绕“古代日常生活中的具体限制”再收集 5–10 条可复核的
低粉频道样本，并与现有“历史系统机制”六题矩阵分开记录。只有站点提供稳定 API / 导出、公开计算口径
且多次人工复核一致后，才讨论 Agent 自动接入。
