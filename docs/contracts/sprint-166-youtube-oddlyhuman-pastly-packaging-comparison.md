# Sprint 166：Oddlyhuman / Pastly 包装变量比较

## 状态

Completed

## Goal

基于两张已完成的同口径频道卡，比较 Oddlyhuman 的“纯古人类问题 / 机制场景”与 Pastly 的“现代镜像 /
古今分屏”；判断两者能否收敛为一个只改变内容入口的包装实验变量，并为 Paynes Creek 盐候选写出非生产
实验设计，不用跨频道绝对播放证明优劣。

## In Scope

- 对齐两个频道的窗口、视频数、时长、播放分布、标题主体、现代对照、视觉一致性、来源和不确定性字段。
- 明确哪些字段可以同口径比较，哪些受频道规模、视频年龄、单条异常、题材和视觉风格混淆。
- 对 Paynes Creek 同一来源账本设计 A / B 标题：A 为纯历史机制，B 为现代便利缺失。
- 固定事实范围、机制链、时长、画幅、画风、缩略图、旁白、来源、发布时间和账号，只允许改变标题入口。
  古今分屏缩略图保留为后续第二个独立变量，不与标题同轮改变。
- 写出发布前需要记录的预测、指标、停止条件和不允许解释的结果；只形成设计，不创建实验目录或发布。
- 更新频道拆解索引、YouTube 索引、研究日志和项目进度。

## Out of Scope

- 不重新采集频道、不进入 Venn Stories、不继续翻 LuluJAI，不新增第三方样本。
- 不把跨频道播放、均值或中位数做胜负比较，不推断 CTR、留存、流量来源、收入或可复制增长。
- 不编写最终脚本、缩略图或分镜，不调用模型、媒体、生成、发布或定时任务。
- 不创建正式内容实验；用户尚未进入开发 / 发布阶段，本轮只有发布前设计草案。
- 不修改六题排序、默认视频长度、`strategy_memory.md`、Skill、业务代码、数据库或前端。

## Deliverables

- 新增 `docs/strategy/youtube/channel-teardowns/oddlyhuman-vs-pastly-packaging-comparison.md`。
- 更新 `docs/strategy/youtube/channel-teardowns/README.md`。
- 更新 `docs/strategy/youtube/README.md`。
- 更新 `docs/strategy/youtube/research-log.md`。
- 更新 `docs/progress.md`。

## Done Means

- 两个频道的事实字段与不可比字段分开列表，所有数字可回两张频道卡核对。
- 明确判断现代镜像是否是可隔离的包装变量，以及最小变更范围。
- A / B 设计只改变一个主要变量，并列出至少 8 个固定变量、1 个主指标、2 个辅助指标和停止条件。
- 不使用跨频道绝对播放支持 A 或 B 更优，不生成内容或创建发布计划。
- 给出进入下一频道前的决策：继续拆 Venn Stories、先补来源 / 视觉授权，或等待真实实验授权，三者只选一。
- 控制器校验、本地 Markdown 链接、敏感字符串扫描和 `git diff --check` 通过。

## Verification

```powershell
py -3.11 .agents\skills\content-iteration-controller\scripts\validate_controller_state.py
git diff --check
```

另人工核对双频道指标、固定变量、唯一改变变量、预测指标、停止条件和不可解释项。

## Handoff

若现代镜像可隔离，保留为未来单变量实验设计，但当前继续逐频道研究 Venn Stories，以检查更成熟的
LuluJAI 头部严格样本是否仍重复同一包装；若不可隔离，则先停止频道拆解，回到来源 / 视觉授权。

## Outcome

- 对齐两张频道卡后，确认跨频道绝对播放不可比较：Oddlyhuman 最高单条占 96.5%，Pastly 为 30.4%，
  频道阶段、年龄、题材与视觉风格不同。
- Pastly 的现代镜像在 6/12 标题与缩略图中重复，属于可隔离包装结构；但第一轮只能改标题入口，缩略图
  古今分屏必须留给第二个独立变量。
- 为 Paynes Creek 同一事实内容设计纯历史机制 / 现代便利缺失两个标题版本，固定 12 项其他变量，以
  CTR 为主指标、30 秒留存和平均观看比例为辅助指标；当前不创建或执行实验。
- 下一频道选择 Venn Stories，继续使用统一拆解卡，不修改策略记忆、Skill 或生产流程。
