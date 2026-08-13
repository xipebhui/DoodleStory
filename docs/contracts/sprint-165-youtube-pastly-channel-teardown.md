# Sprint 165：YouTube Pastly 单频道完整拆解

## 状态

Completed

## Goal

沿用 Sprint 164 的统一频道拆解模板，对 LuluJAI 第 41–60 条新增频道 Pastly 当前 12 条 YouTube
公开视频做完整拆解；验证其“现代人 / 现代生活 vs 古人类”的对照是否是稳定包装结构，并将观察、频道内
分布和不可得因果分开记录，为下一轮 Oddlyhuman / Pastly 横向比较提供同口径证据。

## In Scope

- 从已验证官方频道 ID 与 RSS 确认 Pastly 当前 12 条窗口和发布顺序。
- 对 12 条使用 YouTube 官方 oEmbed / 公共视频页复核标题、视频 ID、发布日期、时长、当前播放、
  非直播状态、描述来源包装与官方缩略图。
- 临时读取 12 张官方缩略图，逐条记录文字、主体、构图、色彩、现代对照、视觉谜题与史实风险；不提交图片。
- 按统一字段标记问题类别、标题主体、具体性、现代参照、缩略图机制和来源等级。
- 描述总量、中位数、前 3 / 后 3、异常值、视频年龄和去异常后的基线；不做增长速度或因果推断。
- 只在 Pastly 卡内总结其频道结构；与 Oddlyhuman 的正式横向比较留给 Handoff。
- 更新频道拆解索引、YouTube 研究日志和项目进度。

## Out of Scope

- 不继续翻 LuluJAI 榜单，不研究 Venn Stories 或其他频道，不改变统一拆解字段。
- 不观看或下载完整视频，不读取字幕、脚本、评论、后台、CTR、留存、流量来源、收入或制作成本。
- 不把视频当史实来源，不复制标题、缩略图、人物造型、脚本、画面、音乐或素材。
- 不因播放量把“现代对照”写成成功原因，不承诺增长、获利或平台分发。
- 不创建脚本、分镜、媒体、发布实验、定时任务或自动采集实现。
- 不修改六题排序、默认视频长度、`strategy_memory.md`、Skill、业务代码、数据库或前端。

## Deliverables

- 新增 `docs/strategy/youtube/channel-teardowns/pastly.md`。
- 更新 `docs/strategy/youtube/channel-teardowns/README.md`。
- 更新 `docs/strategy/youtube/README.md`。
- 更新 `docs/strategy/youtube/research-log.md`。
- 更新 `docs/progress.md`。

## Done Means

- 官方 RSS 与视频页共同覆盖当前 12/12 条；视频 ID 唯一，必要字段无缺失。
- 12 条均完成与 Oddlyhuman 相同的标题、缩略图、来源包装和问题类别记录。
- 明确计算直接现代对照标题 / 缩略图的数量与比例，不凭印象判断频道定位。
- 播放分布包含总量、中位数、前 3、后 3、异常值、视频年龄和去异常基线。
- 至少记录 3 个可借鉴、3 个不应复制和 3 个需实验验证的机制，不升级长期规则。
- 仓库不包含缩略图副本、视频、凭据、会话、私有响应或发布任务。
- 控制器校验、本地 Markdown 链接、敏感字符串扫描、12 条计数和 `git diff --check` 通过。

## Verification

```powershell
py -3.11 .agents\skills\content-iteration-controller\scripts\validate_controller_state.py
git diff --check
```

另人工检查 12 个视频 ID、日期、时长、播放、现代对照计数、缩略图、来源包装与前后 3 分组。

## Handoff

完成 Pastly 后，下一轮只比较 Oddlyhuman 与 Pastly 两张已完成频道卡：固定题型、标题、视觉、来源、
时长和异常值口径，判断“纯古人类生存”与“现代对照”是否真的构成两个可实验包装变量。

## Outcome

- YouTube 官方 RSS 与 12 个公开视频页共同覆盖当前 12/12 条；ID 唯一、字段完整、均非直播，12 张
  官方缩略图均为 1280×720，只在临时目录观察。
- 6/12 标题和缩略图形成明确现代对照。该组当前中位数 678，其他组 466；但视频年龄、题材和画风混杂，
  只保留为待验证变量，不写成表现原因。
- 12 条当前播放合计 11,004，中位数 466；最高单条 3,340、占 30.4%，没有 Oddlyhuman 式单条占
  96.5% 的极端异常。最新三条恰为后 3，频道阶段混淆明显。
- 12/12 有来源栏、8/12 有章节、5/12 有不确定性声明，但只有 2/12 提供外部来源直链。下一轮固定为
  Oddlyhuman / Pastly 同口径横向比较。
