# Sprint 56 抖音 Skill 独立运行与中文执行链路

## Sprint Name

`douyin-skill-independent-chinese-flow`

## Goal

让 `douyin-hot-sample-research` 从上一轮实战验证中沉淀为可在新对话独立运行的 Skill：搜索脚本调用不再依赖聊天上下文，用户可读说明改为中文优先，账号分析和全量 VL 生成前置规则与当前真实工作流一致。

## In Scope

- 增加当前项目内的 MediaCrawler 调用封装，支持通过 `MEDIACRAWLER_HOME` 配置外部采集底座。
- 将 Skill 主流程、分步协议、执行说明和关键引用文档改为中文优先。
- 修正搜索结果分析脚本：默认按作品 ID 去重，降低小分母高转发率误判，并把大号/多作品账号作为快速模仿度减弱项。
- 明确账号数据可以先全量抓取，再默认分析最近 N 条。
- 明确最终故事生成前必须先走 DoodleStory 全量 VL，提取完整原文后再分析、优化和原创改写。

## Out of Scope

- 不把完整 MediaCrawler 项目 vendoring 进 DoodleStory 仓库。
- 不修改 DoodleStory 产品 UI 或后端任务创建接口。
- 不新增平台规避、Mock 数据、静默兜底或绕过登录校验的采集方式。

## Deliverables

- `.agents/skills/douyin-hot-sample-research/scripts/run_mediacrawler.py`
- `.agents/skills/douyin-hot-sample-research/scripts/analyze_search_results.py`
- `.agents/skills/douyin-hot-sample-research/SKILL.md`
- `.agents/skills/douyin-hot-sample-research/references/*.md`
- `README.md`
- `docs/progress.md`

## Done Means

- 新对话可以只根据 Skill 文件和 `MEDIACRAWLER_HOME` 规则找到 MediaCrawler 调用入口。
- 构建环境时可以从 README 找到 Chrome CDP、`MEDIACRAWLER_HOME`、封装脚本和搜索结果分析命令。
- 用户看到的执行步骤、下一步提示和关键策略说明以中文为主。
- 搜索评分脚本默认去重，并在输出里记录原始候选数与去重状态。
- 账号模仿度判断把成熟账号积累作为减弱项。
- `generation_brief` 之前强制经过 `full_story_extract`，不再用首尾页预览直接生成最终故事。

## Verification

```bash
python3 -m py_compile .agents/skills/douyin-hot-sample-research/scripts/analyze_search_results.py .agents/skills/douyin-hot-sample-research/scripts/run_mediacrawler.py
python3 /Users/pengfei.shi/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/douyin-hot-sample-research
python3 .agents/skills/douyin-hot-sample-research/scripts/analyze_search_results.py --contents /Users/pengfei.shi/workspace/tmp-project/MediaCrawler/data_test/wenzimanhua_week_comprehensive/douyin/jsonl/search_contents_2026-06-15.jsonl --out-dir /tmp/wenzimanhua-analyzer-check
git diff --check
```

Manual or QA checks:

- 人工检查 Skill 主文件不再依赖本轮聊天上下文解释外部脚本路径。
- 人工检查账号分析与全量 VL 生成前置规则已经写入主流程和引用文档。

## Risks / Notes

- MediaCrawler 仍是外部 checkout；本次选择封装调用而不是移动源码，避免把外部项目和依赖维护责任混入 DoodleStory。迁移到新机器时需要设置 `MEDIACRAWLER_HOME` 或保持默认路径可用。
- 如果未来要把 MediaCrawler 源码放入当前仓库，需要单独评估许可证、依赖体积、升级方式和 Cookie/登录态边界。

## Handoff

- Next likely step: 用更新后的 Skill 从新对话重新执行一个关键词的 `lane_intake -> market_scan`，检查是否不需要聊天历史即可定位脚本和产物。
