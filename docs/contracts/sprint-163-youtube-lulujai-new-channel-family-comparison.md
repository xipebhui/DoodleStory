# Sprint 163：LuluJAI 新增频道族同质性比较

## 状态

Completed

## Goal

比较 LuluJAI 定向历史列表第 41–60 条新增的 Oddlyhuman、Pastly 与既有 9 个严格古代日常频道，
判断新增证据带来新的问题类别、历史具体性或内容结构，还是只扩大同一 `Ancient Humans` 问句模板的
频道供给；据此决定是否在题型层面停止 LuluJAI 会员榜研究。

## In Scope

- 以 11 条已验证代表视频为入口，从 YouTube 官方公开视频页解析频道 ID。
- 每个频道只读取 YouTube 官方 RSS 当前最多 12 条标题、发布日期和视频 ID；记录实际可见条数，不用
  搜索结果或推荐排序补齐。
- 对近期标题统一标记：具体日常限制类别、宽泛人类起源 / 演化、战争 / 政治、考古 / 文明史、其他；
  以及 `Ancient Humans` 通用主体、明确文明 / 地点 / 时期、现代对照三种具体性。
- 分别计算两个新增频道和既有 9 个频道的标题家族集中度、题型覆盖、明确历史边界比例与更新连续性。
- 只依据标题与公开发布时间判断包装结构，不把 YouTube 视频作为史实来源，不使用播放量推断因果。
- 更新古代日常样本研究、LuluJAI 饱和研究、第三方来源评估、YouTube 索引、研究日志和项目进度。

## Out of Scope

- 不继续读取 LuluJAI 第 61 条以后，不改变筛选、榜面、日期或排序，不检查其他趋势网站。
- 不观看、下载、转录或复刻视频，不读取评论、缩略图、字幕、频道后台、收入、留存或流量来源。
- 不读取 Cookie、Token、浏览器存储或会员私有响应，不保存账号凭据。
- 不使用 YouTube 搜索或第三方频道分析服务，不批量抓取频道全部历史视频。
- 不编写脚本、分镜、媒体或发布实验，不修改六题排序、默认视频长度、`strategy_memory.md`、Skill、
  业务代码、数据库或前端。

## Deliverables

- 新增 `docs/strategy/youtube/lulujai-new-channel-family-comparison.md`。
- 更新 `docs/strategy/youtube/lulujai-history-list-saturation-study.md`。
- 更新 `docs/strategy/youtube/ancient-everyday-life-sample-study.md`。
- 更新 `docs/strategy/youtube/third-party-trend-source-assessment.md`。
- 更新 `docs/strategy/youtube/README.md`。
- 更新 `docs/strategy/youtube/research-log.md`。
- 更新 `docs/progress.md`。

## Done Means

- 11 个频道均有可审计的官方频道 ID、实际 RSS 条目数和观察窗口；缺失条目如实记录，不补样。
- 所有 RSS 标题完成同一套题型与具体性分类；新增频道与既有频道分开汇总。
- 题型层面停止判断使用固定规则：如果两个新增频道近期标题均有至少 60% 使用宽泛
  `Ancient Humans / Humans` 主体，且没有一个新问题类别在至少 2 个频道各出现 2 次，则判定只增加同质
  供给，在题型层面停止 LuluJAI 研究。否则只保留满足条件的结构增量，不继续分页。
- 结论明确区分“榜单还能发现更多频道”和“题型研究是否还有结构增量”，不把两者混为一谈。
- 文档不包含凭据、会话、私有响应、媒体、发布任务或自动采集实现。
- 控制器校验、本地 Markdown 链接、敏感字符串扫描、频道 / 标题计数和 `git diff --check` 通过。

## Verification

```powershell
py -3.11 .agents\skills\content-iteration-controller\scripts\validate_controller_state.py
git diff --check
```

另人工检查频道 ID、RSS 条目边界、分类一致性、聚合计数与停止规则。

## Handoff

若满足题型层面停止规则，结束当前 LuluJAI 会员榜研究，把后续工作转回来源账本、视觉授权或真实发布
实验；只有榜单刷新或研究问题改变时重开。若不满足，只记录具体结构增量并设计一个窄研究问题，不继续
无边界分页。

## Outcome

- 从 11 条已验证代表视频解析 11 个官方频道 ID，读取 10 个频道各 12 条、Oddlyhuman 9 条官方 RSS，
  共对 129 个近期标题完成统一题型与具体性分类。
- Oddlyhuman 9/9、Pastly 9/12 标题直接使用 `Human(s)` 通用主体，均超过预设 60% 阈值。
- 两个新增频道只有既有 `D/E/O` 类别；严寒、迁徙、酒、工作、体味、捕食者、儿童和物种等主题均可
  回指既有频道，没有新类别在两个新增频道中各出现至少 2 次。
- 预设停止规则满足：LuluJAI 在“古代日常限制题型”问题上达到题型层面饱和，停止继续翻页和扩同类频道。
