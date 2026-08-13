# Sprint 170：YouTube 前五频道横向审计

## 状态

Completed

## Goal

把 Oddlyhuman、Pastly、Venn Stories、ThinkMan 与 Ink Explainer 五张已完成频道卡放进同一审计口径，
比较各自窗口内的播放集中结构、标题具体性、视觉机制和来源成熟度；识别真正可迁移到 DoodleStory 的
机制，并依据既有 129 条标题证据决定剩余六个频道中谁还能提供结构增量。

## In Scope

- 只复用五张已完成频道卡中的官方公开事实与统一人工分类，不刷新当前播放，不跨频道比较绝对播放量。
- 统一比较各频道当前窗口的发布节奏、时长、最高单条占比、前三条占比和异常值结构。
- 汇总 `Human(s)` 通用主体、明确文明 / 地点 / 时期、现代镜像、材料 / 场景约束等标题结构。
- 比较缩略图中的短字、通用兽皮人物、古今分屏、机制物件和视觉证据错位。
- 比较来源栏、直接链接、学术 / 机构来源、章节和不确定性语言的公开可审计程度。
- 依据既有 129 条近期标题分类，评估 Basically Primitive、History Alive Animated、Explain In Paint、
  Axen、Zenn 与 Buried Empires 的结构增量，只指定一个下一拆解对象。
- 更新频道拆解索引、YouTube 索引、研究日志和项目进度。

## Out of Scope

- 不新增第六张频道事实卡，不重新抓取 YouTube、LuluJAI 或其他第三方网站。
- 不使用频道间绝对播放、订阅或总量判定频道优劣，不推断 CTR、留存、收入、流量来源或增长因果。
- 不把暴力、私密身体、羞辱式画面或高频更新直接写成可复制策略。
- 不创建实验、预测、脚本、分镜、媒体或发布任务，不修改六题排序、默认时长、生产流程或业务代码。
- 不更新 `strategy_memory.md`、Skill、数据库或前端；本轮仍是公开市场研究证据。

## Deliverables

- 新增 `docs/strategy/youtube/channel-teardowns/five-channel-cross-audit.md`。
- 更新 `docs/strategy/youtube/channel-teardowns/README.md`。
- 更新 `docs/strategy/youtube/README.md`。
- 更新 `docs/strategy/youtube/research-log.md`。
- 更新 `docs/progress.md`。

## Done Means

- 五个频道在同一张表中完成分布、标题、视觉和来源字段对齐，并明确数据窗口与不可比边界。
- 区分单条异常、前三条集中、宽分布低基线和连续高位带，不用绝对播放给频道排名。
- 给出跨频道共有模板、不可复制风险和至少 3 个可迁移机制，且可迁移机制不依赖某个频道角色或画风。
- 对剩余六频道逐一给出结构增量判断，标明暂缓、次级候选或下一对象，不为完成名单机械拆解。
- 只指定一个下一频道，并写明选择理由与完成该频道后的停止规则。
- 控制器状态校验、本地 Markdown 链接、敏感字符串扫描和 `git diff --check` 通过。

## Verification

```powershell
py -3.11 .agents\skills\content-iteration-controller\scripts\validate_controller_state.py
git diff --check
```

另人工复核五张频道卡的窗口计数、集中度、标题具体性、来源链接计数，以及 129 条标题表中的剩余频道分类。

## Handoff

若某个剩余频道能提供此前未覆盖的标题具体性、叙事边界或视觉机制，只拆解该一个频道；若其完整卡仍只
依赖暴力敏感题或重复通用模板，则停止扩频道，把研究转回来源账本、视觉授权或等待真实发布数据。

## Outcome

- 五个频道按各自窗口分成单条异常、前三条主题簇集中、宽分布低基线和连续高位带四类，没有进行绝对
  播放排名，也没有把公开分布写成增长因果。
- 57 条标题有 47 条直接使用 `Human(s)`，只有 3 条包含明确历史边界；黄色短字、兽皮人物和通用古人类
  问句被确认为拥挤供给模板，而不是可直接复制的策略。
- 可迁移方向收敛为“普遍限制—具体历史边界—真实机制物件—主张 / 来源 / 未知项”，并保留语法、数字、
  内嵌时长和视觉证据一致性作为发布前 QA。
- 剩余六频道只有 Buried Empires 提供强结构对照：0/12 使用通用人类主体、11/12 有明确历史边界；
  下一张只拆该频道，同时明确不复制其战争、惩罚和酷刑题材。
- 控制器状态、本地 Markdown 链接、敏感字符串与 `git diff --check` 均通过；没有修改策略记忆或 Skill。
