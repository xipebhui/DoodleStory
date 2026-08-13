# Sprint 161：LuluJAI 定向历史筛选跨榜研究

## 状态

Complete

## Goal

只使用 LuluJAI 会员长视频页面及候选 YouTube 原页，核验 `长视频 + 英语 + 历史悬疑` 是否是蓝海、
月度热门和低粉频道增长三个榜面共同支持的筛选范围，并判断同一个事实历史题型是否至少跨两个榜面、
多个频道出现；若页面不支持同口径筛选，明确记录筛选能力差异并停止把“跨榜”作为支持证据。

## In Scope

- 使用用户已授权的 LuluJAI 会员会话，只读检查长视频蓝海、月度热门和低粉频道增长三个页面。
- 对每个页面记录可见筛选控件、最终 URL、已生效筛选标签、结果数量和当前排序。
- 蓝海页尝试固定 `长视频 + 英语 + 历史悬疑`；月度与低粉页只使用页面真实提供的同名筛选，不推测
  或手工拼接未验证参数。
- 对每个成功应用同口径筛选的榜面按当前顺序保留前 10 条；只有一个榜面支持时，在该榜面扩到前 20
  条并把其余页面记为不可跨榜比较，不用外部搜索补足。
- 人工区分事实历史、古代日常限制、历史系统机制、地理 / 资源解释、AI 虚构、真实犯罪、政治、IP、
  教程、直播回放与其他噪声。
- 对所有疑似跨榜事实历史候选，以及至少 3 个最强单榜候选，回 YouTube 原页复核身份、发布日期、
  时长、是否直播回放和当前公开指标。
- 更新 LuluJAI 研究报告、第三方来源评估、YouTube 索引、研究日志和项目进度。

## Out of Scope

- 不读取 Cookie、Token、浏览器存储或账号资料，不保存邮箱、密码、会员会话或页面私有响应。
- 不逆向、抓取或批量调用 LuluJAI 接口，不猜测隐藏参数，不绕过会员权限。
- 不收藏、购买、修改设置、申请联盟、使用生图额度或触发发布。
- 不使用 YouTube 搜索、Google 搜索或其他趋势网站扩写站内样本；YouTube 只用于复核已发现候选。
- 不生成脚本、分镜、图片、语音或视频，不创建实验、每日任务或自动接入。
- 不修改六题排序、默认视频长度、`strategy_memory.md`、Skill、业务代码、数据库或前端。

## Deliverables

- 新增 `docs/strategy/youtube/lulujai-filtered-history-cross-surface-study.md`。
- 更新 `docs/strategy/youtube/lulujai-member-ranking-cross-list-study.md`。
- 更新 `docs/strategy/youtube/third-party-trend-source-assessment.md`。
- 更新 `docs/strategy/youtube/README.md`。
- 更新 `docs/strategy/youtube/research-log.md`。
- 更新 `docs/progress.md`。

## Done Means

- 三个会员榜面都有筛选能力矩阵，包含控件、实际生效状态、URL / 标签证据和是否可同口径比较。
- 若至少两个榜面支持同口径筛选，每榜至少 10 条人工分类；若只有一个支持，该榜至少 20 条并明确跨榜
  假设无法成立，不能用外部样本补齐。
- 疑似跨榜事实历史候选全部回原页复核；没有跨榜候选时，至少 3 个最强单榜候选完成原页复核。
- 直播回放、虚构、真实犯罪、政治、IP 与宽泛 `history / ancient` 关键词噪声不会混入事实历史结论。
- 输出只允许：存在可继续研究的跨榜题型、仅单榜信号、或停止跨榜假设；不升级长期策略规则。
- 控制器校验、本地 Markdown 链接、敏感字符串扫描、样本计数和 `git diff --check` 通过。

## Verification

```powershell
py -3.11 .agents\skills\content-iteration-controller\scripts\validate_controller_state.py
git diff --check
```

另人工检查三个榜面的筛选证据、样本数、人工分类、跨榜去重、YouTube 原页、直播状态和证据分层。

2026-08-12 验证结果：三个会员榜面的筛选能力矩阵已完成；只有蓝海榜支持完整组合，组合 URL、pressed
状态、已生效标签和 231 条结果相互一致。按合同分类蓝海榜前 20 条，报告包含 10 个 YouTube 原链接；
5 条代表候选已通过 YouTube 官方 oEmbed 与公开视频页面元数据核对身份、精确播放、发布日期、时长和
直播状态。7 份相关 Markdown 本地链接均可解析，凭据扫描无命中，`strategy_memory.md` 未变化；控制器
校验返回 `ok: true` 且无警告，`git diff --check` 通过。

## Handoff

如果至少两个榜面出现同一事实历史题型，下一轮只深挖一个重复题型的频道族与包装差异；如果只有蓝海
榜支持定向筛选或其他榜面没有事实历史候选，停止把“LuluJAI 跨榜”作为古代日常的支持证据，后续只把
站点用于单榜人工发现。
