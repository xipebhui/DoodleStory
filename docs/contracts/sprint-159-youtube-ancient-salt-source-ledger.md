# Sprint 159：YouTube 古代盐获取案例来源账本

## 状态

Complete

## Goal

在不进入脚本、媒体制作、Agent 开发或发布实验的前提下，把“古代人如何获得盐”收窄为一个时间、
地区和机制边界明确的案例；用权威机构资料或同行评议研究建立可审计的来源账本与 research brief，
判断它是否具备“具体需要 → 生产机制 → 运输 / 交换 → 证据限制”的可画解释链。

## In Scope

- 最多比较 3 个古代盐案例，按来源质量、时间 / 地区边界、机制链完整度、视觉可解释性和误述风险筛选。
- 只为最终选中的 1 个案例建立详细来源账本；优先使用同行评议论文、博物馆、大学或国际机构资料。
- 对每项事实标注“直接考古证据”“研究者解释 / 推断”或“仍未知”，并记录来源不能支持的说法。
- 编写 research brief：受众问题、一句话回答、事实主张表、机制顺序、可视化场景、标题承诺边界、
  未知项与停止条件。
- 更新 YouTube 研究索引、研究日志、上一轮研究交接和项目进度。

## Out of Scope

- 不把 YouTube 视频、第三方趋势榜或搜索摘要作为历史事实来源。
- 不编写可发布脚本、旁白、分镜或缩略图，不生成图片、语音、字幕、视频或发布任务。
- 不创建内容实验、`prediction.json`、定时研究任务或自动采集脚本。
- 不修改六题排序、90–180 秒默认研究假设、`strategy_memory.md`、Skill、业务代码、数据库或前端。
- 不把可画性、公开播放或单一案例解释为增长、收入或可复制性结论。

## Deliverables

- 新增 `docs/strategy/youtube/ancient-salt-access-source-ledger.md`。
- 更新 `docs/strategy/youtube/ancient-everyday-life-sample-study.md`。
- 更新 `docs/strategy/youtube/README.md`。
- 更新 `docs/strategy/youtube/research-log.md`。
- 更新 `docs/progress.md`。

## Done Means

- 候选比较不超过 3 个案例，并明确最终选择与排除理由。
- 选中案例至少有 3 个可直接打开的权威或同行评议来源，且不是同一媒体稿的重复转载。
- 每项关键主张可回溯到具体来源，并严格分开直接证据、支持性推断和未知项。
- research brief 的问题不超出时间与地区边界，视觉链每一段都有来源或明确标记为重建假设。
- 文档不包含登录凭据、会员会话、媒体产物、发布任务或未经来源支持的确定性表述。
- 控制器校验、Markdown 本地链接、敏感字符串扫描和 `git diff --check` 通过。

## Verification

```powershell
py -3.11 .agents\skills\content-iteration-controller\scripts\validate_controller_state.py
git diff --check
```

另人工检查来源独立性、链接可访问性、事实 / 推断 / 未知分层、时间与地区边界、标题承诺边界，以及
所有视觉场景是否能回到来源证据。

2026-08-12 验证结果：完成 3 个候选案例比较；选中案例账本包含 6 份同行评议来源、10 条事实主张和
7 个可视场景，事实 / 推断 / 未知均有显式边界；6 份相关 Markdown 的本地链接全部可解析，凭据扫描
无命中，`strategy_memory.md` 未变化；控制器校验返回 `ok: true` 且无警告，`git diff --check` 通过。

## Handoff

如果来源账本支持一条完整且低误述风险的机制链，下一轮仍只做一个相邻案例的对照账本或公共领域视觉
素材清单，不直接生成脚本。如果关键运输、交换或年代主张只能依赖二手概述，则收窄问题或停止该案例，
不以叙事完整性填补证据缺口。
