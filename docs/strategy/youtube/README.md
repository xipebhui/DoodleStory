# YouTube 赛道验证包

这里集中存放 DoodleStory 面向 YouTube 新赛道的非开发性研究与设计资料。它不替代
`docs/architecture/` 的运行架构说明，也不混入抖音的市场样本或实验结论。

## 推荐阅读顺序

1. [赛道比较与首轮验证建议](2026-08-youtube-niche-validation.md)
2. [候选历史题来源账本](candidate-topic-source-ledgers.md)
3. [历史机制六题研究矩阵](six-topic-experiment-matrix.md)
4. [第三方趋势源评估：LuluJAI](third-party-trend-source-assessment.md)
5. [古代日常生活题型扩样](ancient-everyday-life-sample-study.md)
6. [古典期玛雅 Paynes Creek 盐获取来源账本](ancient-salt-access-source-ledger.md)
7. [Paynes Creek 样片视觉来源与授权清单](paynes-creek-visual-source-rights-ledger.md)
8. [Paynes Creek 12 镜证据板与 16:9 视觉规格](paynes-creek-shot-evidence-board.md)（[HTML 阅读板](paynes-creek-shot-board.html)）
9. [LuluJAI 会员长视频榜跨榜一致性研究](lulujai-member-ranking-cross-list-study.md)
10. [LuluJAI 定向历史筛选跨榜研究](lulujai-filtered-history-cross-surface-study.md)
11. [LuluJAI 定向历史列表第 21–60 条饱和研究](lulujai-history-list-saturation-study.md)
12. [LuluJAI 新增频道族同质性比较](lulujai-new-channel-family-comparison.md)
13. [YouTube 单频道拆解卡](channel-teardowns/README.md)
14. [前五频道横向审计](channel-teardowns/five-channel-cross-audit.md)
15. [多语言与获利路径边界](language-and-monetization-boundaries.md)
16. [格式观察、平台分流与相邻赛道压力测试](format-and-adjacent-lane-review.md)
17. [新赛道 Agent 流程设计模板](agent-flow-design-template.md)
18. [外部依赖准备清单](external-dependency-readiness.md)
19. [Paynes Creek S03 单镜真实媒体 Gate 记录](paynes-creek-s03-media-gate.md)
20. [Paynes Creek 首片生产控制室](paynes-creek-production-control-room.md)（[HTML 控制台](paynes-creek-production-control-room.html)）
21. [Paynes Creek 16:9 Style 状态审计](paynes-creek-style-state-audit.md)
22. [Paynes Creek 本地样片生产验证章程](paynes-creek-local-pilot-charter.md)（[空白成片验收模板](paynes-creek-local-pilot-acceptance-template.json)）
23. [Paynes Creek S03 单镜重试协议](paynes-creek-s03-retry-protocol.md)（[空白 Gate 证据模板](paynes-creek-s03-gate-evidence-template.json)）
24. [Paynes Creek G5 串行视觉锚点协议](paynes-creek-g5-serial-anchor-protocol.md)（[Profile](paynes-creek-g5-anchor-profiles.json)；[空白 attempt](paynes-creek-g5-anchor-attempt-template.json)）
25. [Paynes Creek G6 九镜串行生产协议](paynes-creek-g6-serial-production-protocol.md)（[Profile](paynes-creek-g6-scene-profiles.json)；[空白 attempt](paynes-creek-g6-scene-attempt-template.json)）
26. [Paynes Creek G7 中文语音与字幕协议](paynes-creek-g7-audio-subtitle-protocol.md)（[Profile](paynes-creek-g7-scene-profiles.json)；[空白 attempt](paynes-creek-g7-scene-attempt-template.json)）
27. [G7-0 同会话跨 Run 媒体 Lineage 蓝图](../../architecture/native-agent-cross-run-media-lineage-blueprint.md)
28. [Sprint 187 / G7-0 开发合同](../../contracts/sprint-187-native-agent-cross-run-media-lineage.md)
29. [G8-A YouTube 1080p 固定渲染 Profile 蓝图](../../architecture/native-agent-youtube-1080p-render-profile-blueprint.md)
30. [Sprint 188 / G8-A 开发合同](../../contracts/sprint-188-native-agent-youtube-1080p-render-profile.md)
31. [G8-B 冻结 Render Manifest Run 蓝图](../../architecture/native-agent-frozen-render-manifest-run-blueprint.md)
32. [Sprint 189 / G8-B 开发合同](../../contracts/sprint-189-native-agent-frozen-render-manifest-run.md)
33. [Paynes Creek G8 Render Manifest 与单次成片协议](paynes-creek-g8-render-manifest-protocol.md)（[Manifest 模板](paynes-creek-g8-render-manifest-template.json)；[空白 attempt](paynes-creek-g8-render-attempt-template.json)）
34. [G8-C 成片逐镜帧证据包蓝图](../../architecture/native-agent-video-frame-evidence-pack-blueprint.md)
35. [Sprint 190 / G8-C 开发合同](../../contracts/sprint-190-native-agent-video-frame-evidence-pack.md)
36. [Paynes Creek G8-C 帧证据与完整观看交接协议](paynes-creek-g8-frame-evidence-protocol.md)（[空白请求模板](paynes-creek-g8-frame-evidence-request-template.json)）
37. [G8 不可变人工验收与发布登记交接蓝图](../../architecture/native-agent-local-pilot-acceptance-handoff-blueprint.md)
38. [Sprint 191 / G8 人工验收门禁合同](../../contracts/sprint-191-native-agent-immutable-local-pilot-acceptance.md)
39. [Paynes Creek G8 人工完整观看协议](paynes-creek-g8-human-acceptance-protocol.md)（[空白请求模板](paynes-creek-g8-human-acceptance-request-template.json)）
40. [Sprint 181 / G2-A 路由快照基础合同](../../contracts/sprint-181-native-agent-run-route-snapshot-foundation.md)
41. [SiliconFlow G3 零媒体 Gate 协议](../../testing/siliconflow-native-agent-zero-media-gate-protocol.md)（[空白证据模板](../../testing/siliconflow-native-agent-zero-media-gate-evidence-template.json)）
42. [SiliconFlow Native Agent 兼容性决策](../../integrations/siliconflow-native-agent-compatibility-decision.md)
43. [持续研究日志](research-log.md)

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

同日跨榜复查进一步抽样 4 个会员长视频榜面、40 个当前头部位置，没有发现严格古代日常或事实历史
解释。重复信号主要是直播回放、长循环、音乐 / IP、AI 虚构和单条带飞；唯一事实型系统解释来自成熟的
Morning Brew 频道且只在月度榜出现。因此会员榜能验证内容波次是否跨“视频、频道、搜索”扩散，
但当前不能把古代日常写成 LuluJAI 跨榜趋势。完整分类与 5 条原页复核见
[会员长视频榜跨榜一致性研究](lulujai-member-ranking-cross-list-study.md)。

进一步核验页面筛选能力后，确认三个长视频榜面不能做同口径历史交叉：蓝海榜支持
`长视频 + 英语 + 历史悬疑`，月度榜缺少历史垂类，低粉增长榜同时缺少语言和历史垂类。蓝海筛选当前
显示 231 条，前 20 条人工分类中只有 2 条严格事实历史、1 条严格古代日常，且古代日常仍是已知的
Venn Stories，没有新增频道族。因此停止使用“LuluJAI 历史跨榜趋势”表述，只保留单榜人工发现。
筛选矩阵与 20 条样本见 [定向历史筛选跨榜研究](lulujai-filtered-history-cross-surface-study.md)。

后续扩样首轮保留 9 条“具体日常限制”视频。继续检查同一会员榜第 21–60 条后，新增 Oddlyhuman 与
Pastly 两个经 YouTube 官方页和频道 RSS 验证的连续频道，当前候选池达到 11 个频道；但 40 个新增位置
只有 5 个严格位置、净增 2 个频道，且全部继续落入 `How / Why / Did Ancient Humans...` 问句家族。
预设饱和条件因第二批出现新频道而未满足，下一步先做频道同质性比较，不继续无边界翻页。完整证据见
[定向历史列表第 21–60 条饱和研究](lulujai-history-list-saturation-study.md)。

该包装仍只可进入后续单变量实验候选。育儿及古人类问句已出现明显跨频道模板聚集，说明需求信号与
拥挤同时存在；不复制固定问句，不改变现有六题排序或默认视频长度。

最终频道族复核读取 11 个官方频道 RSS 的 129 个近期标题。Oddlyhuman 9/9、Pastly 9/12 标题直接
使用 `Human(s)` 通用主体；两者出现的日常限制与人类起源 / 演化均是既有大类，严寒、移动、酒、工作、
体味、捕食者、儿童和物种等已形成跨频道重复簇。预设停止规则满足，当前在题型层面结束 LuluJAI 会员榜
研究。完整分类见 [新增频道族同质性比较](lulujai-new-channel-family-comparison.md)。

在停止继续翻榜后，研究改为逐频道拆解，而不是继续扩大频道数量。第一张
[Oddlyhuman 频道卡](channel-teardowns/oddlyhuman.md)覆盖其当前全部 9 条视频：播放高度集中于单条严寒
异常，不能当作稳定频道机制；可借鉴的是单一问题、稳定视觉系统和来源公开，不应复制通用古人类问句、
未核实的猎奇剖面或缩略图元数据错误。

第二张 [Pastly 频道卡](channel-teardowns/pastly.md)覆盖当前 12 条：6/12 稳定使用现代人 / 现代生活与古人
对照，当前中位数 678，高于其他组 466；但最新三条恰好也是播放最低三条，年龄、题材和画风混淆仍大，
只能把现代镜像保留为单变量实验候选。

[Oddlyhuman / Pastly 包装比较](channel-teardowns/oddlyhuman-vs-pastly-packaging-comparison.md)进一步收窄了
实验设计：同一 Paynes Creek 视频第一轮只改变标题是否加入现代便利缺失，缩略图保持完全相同；古今
分屏只能在后续第二轮单独测试。当前没有发布授权，未创建实验或媒体。

第三张 [Venn Stories 频道卡](channel-teardowns/venn-stories.md)覆盖当前 RSS 12 条并独立复核 LuluJAI
经期种子。12 条集中在 10.1 天、平均间隔 22.1 小时，但体毛单条占窗口播放 92.1%；经期种子与体毛
两条又约占频道总播放 88.7%，所以高频供给没有形成稳定公开基线。窗口 12/12 的缩略图都压成两个黄色
大词，0/12 标题含具体文明、地点或时期；11/12 有来源栏，但只有 1/12 提供外部直链。当前只保留“普遍
日常疑问 + 极短视觉钩子”为设计观察，私密身体猎奇、兽皮人设和日更节奏不升级为规则。下一频道为
ThinkMan。

第四张 [ThinkMan 频道卡](channel-teardowns/thinkman.md)覆盖当前 RSS 12 条，盐种子与窗口第 10 条重合。
严寒、盐、糖分别占窗口播放 33.5%、28.7%、21.7%，前三条合计 84.0%；盐不是单条带飞，但频道仍由
三个生存 / 资源问题高度集中。4/12 标题点名铁、奶、糖、盐，只有 1/12 出现宽泛时期，0/12 出现文明、
地点或遗址，因此只是对象更具体，不是历史主体更具体。12/12 缩略图仍为黄色短字与通用卡通古人类，
0/12 有正式来源栏或外部来源直链。当前只保留“熟悉基本物质 + 史前稀缺 / 生存后果 + 章节化解释”为
候选观察；无来源数字、巨型糖晶体、炼铁火堆和通用兽皮人设不迁移。下一频道为 Ink Explainer。

第五张 [Ink Explainer 频道卡](channel-teardowns/ink-explainer.md)覆盖当前 RSS 12 条；连续降雨与环球旅行
两个 LuluJAI 锚点分别排第 1 和第 4、合计占窗口 42.8%，但 05-11 至 07-16 的连续 8 条全部超过
13.7 万播放，因此榜单只命中了连续高位带的一部分。最近 9 条连续提供外部来源链接，8/12 至少有 DOI、
学术出版物或机构来源；来源流程明显成熟。与此同时，0/12 标题点名文明、地点、遗址或时期，缩略图仍有
猛犸尸体住房、暴力天性、全天醉态和错误内嵌时长等问题。当前不再立即扩到第六个频道，先对前五张频道卡
做横向审计，判断剩余名单是否还会带来结构增量。

[前五频道横向审计](channel-teardowns/five-channel-cross-audit.md)进一步确认：Oddlyhuman 与 Venn Stories
由单条异常支撑，ThinkMan 由严寒、盐、糖三条集中，Pastly 较分散，Ink Explainer 才出现连续 8 条
高位带；这种窗口内分布差异不能转成跨频道绝对排名。五个窗口 57 条标题中 47 条直接使用 `Human(s)`，
只有 3 条有明确文明、地点或时期。可迁移方向因此收敛为“普遍限制 → 具体历史边界 → 真实机制物件 →
主张 / 来源 / 未知项”，而不是黄色字、兽皮人物、私密身体、暴力或高频发布。剩余六频道只优先拆
Buried Empires，用它检验具体文明叙事能否提供脱离暴力题材的结构增量；其他五个先暂缓。

第六张、也是本轮最后一张 [Buried Empires 频道卡](channel-teardowns/buried-empires.md)验证了这个强对照：
0/12 标题使用通用 `Human(s)`，11/12 点名文明、人物或群体，12/12 有章节和命名来源；但 10/12 是战争 /
惩罚，0/12 有来源直链，最高一条 Sparta 懦夫占窗口 86.1%。写实伤害缩略图与具体文明、24 分钟长度、
清单和视频年龄同时变化，不能拆出可复制因果。当前停止剩余频道卡；研究阶段收敛到 Paynes Creek 的
“限制—具体边界—机制物件—来源审计”，下一步先做视觉来源与授权清单，再进入单条本地样片。

首个必需资源案例已收窄为公元 600–900 年伯利兹南部 Paynes Creek 盐场群。水下木构、煮卤陶器、
船桨和沿海—内陆物质联系支持“卤水 → 制盐 → 可能的盐饼 → 水路交换”解释链；具体目的地、路线、
价格和“盐是否是货币”仍未知。后续视觉授权核查已给出有条件通过：Natural Earth 公共领域底图与两篇
`CC BY 4.0` 原始研究足以支持原创机制示意，PNAS 船桨照片、AIA / LSU 网页照及 `CC BY-NC-ND`
论文图不直接使用；具象市场戏被替换为不指定路线和买家的抽象网络图。后续 12 镜证据板已将它固定为
138 秒中文本地生产验证片：每镜只绑定一个主张、证据等级、来源、画面边界和合法运动预设。

[最终中文旁白与逐镜 Prompt 包](paynes-creek-chinese-script-prompt-pack.md)进一步定稿 536 个汉字、约
134 秒计划配速和 12 段自包含图片 Prompt；[机器可读生产草案](paynes-creek-production-draft.json)保存
Scene、来源、运动与预期文件名，但不伪造任何媒体 ID。代码复核同时确认统一 Gateway 对 `16:9` 当前
请求 `1792×1024`，Native Remotion 又直接跟随首图真实宽高，不能把交付目标 1920×1080 当作已有
保证。专用 16:9 Style 与只含 `generate_image`、`inspect_image` 的最小 Skill 已在本地验证库建立，
但 [S03 单镜真实媒体 Gate](paynes-creek-s03-media-gate.md) 在 Agent 前置规划阶段停止：`gpt-5.5`
经当前火苗兼容地址返回 429 `usage_limit_reached`，图片调用、资产和视觉检查均为 0。当前结论固定为
`stop_before_batch`；先恢复同一路径额度，或另行批准并验证 Agent 模型路由，之后仍从一张 S03 重做，
不得直接生成 S01 或其余镜头。

后续 [SiliconFlow Native Agent 兼容性审计](../../integrations/siliconflow-native-agent-compatibility-decision.md)
已经排除“直接改地址”：当前 Agent 用 Responses，SiliconFlow 官方工具调用用 Chat Completions。已安装
Agents SDK 有可复用的 Runner 和部分事件转换，但固定 `__fake_id__`、缺失 arguments done、图片 Tool
Output 过滤和 10 条消息文档边界阻止直接接入。新的
[适配实施蓝图](../../architecture/siliconflow-native-agent-adapter-blueprint.md)已把 Run 级路由快照、应用侧
模型调用 ID、Function 参数映射、Chat 工具输出 policy、离线测试和三阶段 Gate 固定下来；这仍是设计，
不是“已经接入”。在用户批准离线实现和之后的一次小额兼容性调用前，S03 继续停止。

[首片生产控制室](paynes-creek-production-control-room.md)与配套
[HTML 控制台](paynes-creek-production-control-room.html)已把研究结果收敛为正式制作入口：首个赛道固定为
“考古证据驱动的古代技术与日常生活机制解释”，首片固定为 Paynes Creek 中文本地生产验证。控制台把
十二镜接触印样、唯一 429 故障、G0–G9、Owner 空位、产物导航和停止条件放在同一页面。当前只开放 G2
离线适配作为可授权下一步；它不包含真实 SiliconFlow、图片、媒体或发布调用，G2、G3 与 G4 必须分别
授权和验收。

[16:9 Style 状态审计](paynes-creek-style-state-audit.md)进一步确认：当前本地验证库已有一条
`active / prompt / Qwen/Qwen-Image / 16:9` 记录，无需重复创建；但 Style Test、图片与频道绑定均为 0，
所以这只是配置事实，不是视觉通过证据。未来 G4 必须重新解析 Style，不能直接沿用审计时的本地 ID。

[G5 串行视觉锚点协议](paynes-creek-g5-serial-anchor-protocol.md)把 S03 之后的锚点验证拆成两次独立停止：
G5-A 只验证一张 S01 抽象地图，G5-B 只验证一张 S04 陶器 / 火候机制；两张图分别授权、分别留证，
任何一张失败都不进入余图。当前 `zoom_in` 仅支持中心 8% 缩放，S01 的选择性焦点只能通过真实探针验证。

[G6 九镜串行生产协议](paynes-creek-g6-serial-production-protocol.md)进一步把“余下九镜”固定为
S02 → S08 → S11 → S05 → S09 → S07 → S06 → S10 → S12。这个顺序按依赖、视觉新颖度和事实漂移风险
安排，不是成片时间线；每镜独立授权、只生成一张、机器与两类人工检查完成后停止，首个失败阻断所有后继镜。
S08 的一米四三只由旁白 / 字幕承载，图片只使用无标签几何测量线，避免让生图模型生成错误数值。

[G7 中文语音与字幕协议](paynes-creek-g7-audio-subtitle-protocol.md)发现一个必须先解决的运行时边界：当前
字幕只接受本 Run 音频，视频也只读取本 Run 的音频 / 字幕，而 Follow-up 会创建新 Run；因此 12 镜逐镜
人工审核后不能直接在独立 G8 Run 合成。协议先设 G7-0 同会话跨 Run lineage，再按
S01 → S02 → S08 → S03 → S07 → S09 → S10 → S11 → S12 → S04 → S05 → S06 验证专名、年代、度量、
限定词和总时长。G7-0 未实现前，Profile 只供设计审核，不授权 TTS。

[G7-0 架构蓝图](../../architecture/native-agent-cross-run-media-lineage-blueprint.md)与
[Sprint 187 合同](../../contracts/sprint-187-native-agent-cross-run-media-lineage.md)已把这一阻塞收敛为单个
离线切片：Tool 输入不增加来源 Run ID，服务端只允许当前 Run 或同 Conversation、同 owner、已成功来源
Run 的 Audio / Subtitle，并把图片、音频、字幕来源写入 Scene 快照。设计已可评审但未实施；当前实际开发
入口仍是 Sprint 181 / G2-A。

[G8-A 固定渲染 Profile 蓝图](../../architecture/native-agent-youtube-1080p-render-profile-blueprint.md)进一步发现：
图片 Gateway 的 `16:9` 请求目标是 1792×1024，当前 Remotion 又跟随首图尺寸，不能满足样片锁定的精确
1920×1080 交付。对应 [Sprint 188 合同](../../contracts/sprint-188-native-agent-youtube-1080p-render-profile.md)
保留旧 source 模板，并设计显式 `youtube_16_9_1080p` preset、每边最多 1% 的确定性中心裁切和最终 MP4
ffprobe 校验。该 Profile 尚未实施，不能把设计写成 G8 已开放。

[G8-B 冻结 Render Manifest Run 蓝图](../../architecture/native-agent-frozen-render-manifest-run-blueprint.md)继续补上
“人工审核结果如何原样进入一次渲染”的边界：当前参数化 Tool 只能证明模型最终传了什么，不能证明人事先
批准了什么。对应 [Sprint 189 合同](../../contracts/sprint-189-native-agent-frozen-render-manifest-run.md)设计
Run 创建时由服务端编译 canonical Manifest、保存 hash 与认证确认人，专用 Skill 只暴露零参数 Render，
运行时复验 lineage 和实际文件 hash。[Paynes Creek G8 协议](paynes-creek-g8-render-manifest-protocol.md)已固定
S01–S12 成片顺序、审核记录映射和一次渲染预算；所有真实 ID 和结果仍为空。

[G8-C 成片逐镜帧证据包蓝图](../../architecture/native-agent-video-frame-evidence-pack-blueprint.md)把“渲染成功”与
“可交给人完整观看”继续分开。对应 [Sprint 190 合同](../../contracts/sprint-190-native-agent-video-frame-evidence-pack.md)
设计独立数据库作业，对同一 Video hash 重做完整解码并按每镜固定五角色和限定词 cue 抽帧，最后保存一个
含 canonical manifest、离线 HTML 和 PNG 的 ZIP。[Paynes Creek G8-C 协议](paynes-creek-g8-frame-evidence-protocol.md)
固定 60 个核心角色与四组限定词定位；Pack success 只开放人工完整观看，不等于本地样片通过。

[G8 不可变人工验收与发布登记交接蓝图](../../architecture/native-agent-local-pilot-acceptance-handoff-blueprint.md)
继续补上“看完以后由什么事实允许登记”的边界。代码审计发现当前前端可直接提交
`review_status="approved"`，后端没有 Video / Manifest / Evidence exact hash 或四维 verdict；因此它只表示
管理员登记，不能表示 Manifest 成片已通过。对应
[Sprint 191 合同](../../contracts/sprint-191-native-agent-immutable-local-pilot-acceptance.md)设计 owner 对同一
Video 和 succeeded Pack 的两阶段 exact-hash 签署，终态只能是不可编辑的
`pass_local_pilot | needs_revision`。[Paynes Creek 人工完整观看协议](paynes-creek-g8-human-acceptance-protocol.md)
把四维检查、preview 与提交顺序固定下来；通过仍保存 `publication_authorized=false`，只允许进入严格发布
资料登记，不创建 YouTube 任务。当前实际开发入口仍是 Sprint 181 / G2-A。

## 边界

- 本目录不保存 API Key、频道登录信息、受版权保护的脚本、下载的视频或私有数据。
- 外部频道仅作为格式观察对象，不复制标题、脚本、画面、音乐或素材。
- 赛道结论不能直接写入 Skill；同一机制至少需要多轮真实发布证据后，才可以成为候选规则。
- 当前 LuluJAI 重开条件仅限榜单刷新后出现新的具体结构、研究问题改变、真实实验提出新假设，或站点
  提供有字段定义的授权 API / 导出；不再为增加同类频道数量而继续翻页。
