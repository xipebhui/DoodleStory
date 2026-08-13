# Sprint 158：YouTube 古代日常生活题型扩样

## 状态

Complete

## Goal

在不进入 Agent 开发、脚本生成、媒体制作或发布的前提下，围绕“古代日常生活中的具体身体、家庭、
劳动与生存限制”补充一组可回 YouTube 原页复核的公开视频样本，判断该题型是否值得从单条观察提升为
后续实验候选，并明确仍然不能支持的结论。

## In Scope

- 使用 LuluJAI 会员页、YouTube 公开搜索和公开视频页发现候选；第三方站点只进入候选发现层。
- 保留至少 5 条严格符合题型的样本，覆盖至少 3 个独立频道；不足时如实记录，不用宽泛历史、真实犯罪、
  科幻、现代政治或 IP 内容凑数。
- 对保留样本记录视频 URL / ID、频道、标题、发布日期、时长、公开播放与订阅快照、具体日常限制、
  标题承诺和排除混淆。
- 使用 YouTube 原页或官方公开接口复核身份与公开指标，并将第三方快照、原页事实和研究推断分层记录。
- 比较题型是否跨越身体卫生、家庭角色、劳动技术与生存资源等子类，以及样本是否集中在单一敏感主题、
  单一频道或单一时长带。
- 更新 YouTube 研究索引、研究日志和项目进度。

## Out of Scope

- 不逆向或批量抓取 LuluJAI，不绕过会员权限，不保存账号、密码、Cookie、Token 或个人资料。
- 不把播放量 / 订阅量比、VPH、机会度或单条异常写成因果、收入预测或可复制增长结论。
- 不把 YouTube 视频当作历史事实来源，不编写可发布脚本，不生成图片、语音、字幕或视频。
- 不创建发布实验、定时研究任务、频道同步或外部发布，不调用收费模型或媒体 Provider。
- 不修改 `strategy_memory.md`、Skill、业务代码、数据库或前端。

## Deliverables

- 新增 `docs/strategy/youtube/ancient-everyday-life-sample-study.md`。
- 更新 `docs/strategy/youtube/README.md`。
- 更新 `docs/strategy/youtube/research-log.md`。
- 更新 `docs/strategy/youtube/third-party-trend-source-assessment.md`。
- 更新 `docs/progress.md`。

## Done Means

- 至少 5 条严格同机制样本来自至少 3 个频道，并有可打开的 YouTube 原链接与同日公开快照。
- 候选、保留和排除标准明确；分类噪声、频道集中、敏感题材、发布时间和视频长度等混淆没有被隐藏。
- 输出只允许三种决策之一：证据不足继续扩样、可进入后续单变量实验候选、或停止该题型研究。
- 即使形成实验候选，也不改变现有六题排序、90–180 秒默认假设或长期 Skill 规则。
- 仓库不包含登录凭据、会员会话、媒体产物、发布任务或自动采集脚本。
- 控制器校验、Markdown 本地链接、敏感字符串扫描和 `git diff --check` 通过。

## Verification

```powershell
py -3.11 .agents\skills\content-iteration-controller\scripts\validate_controller_state.py
git diff --check
```

另人工检查样本数量、独立频道数量、YouTube 原链接、观察日期、证据层级和每条样本的严格题型标签。

2026-08-12 验证结果：9 条严格样本来自 9 个频道，9 个 YouTube 原链接齐全，5 个频道观察时不足
2 万订阅；6 份相关 Markdown 本地链接全部可解析；凭据扫描无命中；`strategy_memory.md` 未变化；
控制器校验返回 `ok: true` 且无警告；`git diff --check` 通过。

## Handoff

如果至少 5 条样本跨 3 个频道重复出现同一“具体日常限制 → 历史解决机制”包装，可把该题型加入后续
实验候选，但下一轮仍只允许先完成一个来源账本与研究 brief；视频长度必须留作之后的独立变量。如果
样本集中在单一频道或敏感身体主题，则继续扩样或停止，不据此开发 Agent。
