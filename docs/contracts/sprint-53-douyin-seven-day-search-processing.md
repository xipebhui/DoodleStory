# Sprint 53 合同：抖音最近 7 天搜索结果处理流程

## 目标

把“最近 7 天搜索结果”从单条候选排序升级为一套可执行的决策流程：先横向比较搜索结果里的类目热度，再筛选值得深入分析的账号，最后把真人/实景结尾转化为可原创复刻的真实感生成策略。

## 范围内

- 增加最近 7 天搜索处理策略文档，明确类目横向对比、账号模仿度初筛、实景真实感复刻三条线。
- 更新 Skill 主流程，把“搜索结果横向处理”放在账号深度分析之前。
- 扩展样本字段，记录类目、类目热度、账号探查优先级、账号模仿度和真实感生成策略。
- 增强 `analyze_search_results.py`，为每条搜索结果输出内容类目、账号探查优先级和可选账号模仿度，并生成 `category_summary.csv/json`。
- 更新 `docs/progress.md`。

## 范围外

- 不在本 sprint 内实现自动打开账号主页并采够 N 条后停止。
- 不在本 sprint 内实现自动生成 image-2 实景图。
- 不修改 DoodleStory 生图链路或内容提取后端。
- 不默认把真人照片直接作为复刻素材。

## 交付物

- `.agents/skills/douyin-hot-sample-research/scripts/analyze_search_results.py`
- `.agents/skills/douyin-hot-sample-research/references/seven-day-search-processing.md`
- `.agents/skills/douyin-hot-sample-research/references/research-fields.md`
- `.agents/skills/douyin-hot-sample-research/SKILL.md`
- `docs/progress.md`

## 完成标准

- 运行搜索分析脚本后，除了候选表，还能得到类目横向对比表。
- 每条候选都能看到内容类目、账号探查优先级；如果传入 creator profile，还能看到账号作品数、粉丝数和模仿度判断。
- Skill 文档明确“作品少但流量高”的账号优先分析，也明确真人/实景结尾应转成 image-2 真实场景生成策略。

## 验证

```bash
python3 .agents/skills/douyin-hot-sample-research/scripts/analyze_search_results.py --contents /Users/pengfei.shi/workspace/tmp-project/MediaCrawler/data_test/huayigegushi_week/douyin/jsonl/search_contents_2026-06-15.jsonl --creators /Users/pengfei.shi/workspace/tmp-project/MediaCrawler/data_test/account_probe_yierbubu/douyin/jsonl/creator_creators_2026-06-15.jsonl --out-dir output/douyin-hot-sample-analysis/huayigegushi-week-seven-day-processing
python3 -m py_compile .agents/skills/douyin-hot-sample-research/scripts/analyze_search_results.py
git diff --check
```

Manual or QA checks:

- 人工查看 `category_summary.csv/json` 和 `analysis_report.md`，确认类目横向对比、账号探查优先级和模仿度字段可用于下一步决策。

## 风险 / 说明

- 类目分类当前是启发式规则，作用是先做横向观察，不替代人工或后续 LLM 分类。
- 账号模仿度只有在传入 creator profile 时才会计算；仅搜索结果不足以知道作者作品数。
- “真实感结尾”不是复制真人照片，而是用原创、授权或 image-2 生成的真实场景图替代。

## Handoff

- 下一步：把账号主页采集封成独立脚本，采够 N 条作品后主动停止，并把账号流量稳定性回填到搜索候选表。
