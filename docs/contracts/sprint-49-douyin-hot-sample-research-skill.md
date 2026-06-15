# Sprint 49 合同：抖音热门样本调研 Skill

## 目标

新增项目本地 skill，把 `douyin-downloader` 明确作为抖音热门图文样本库的采集底座，并沉淀第一步调研流程、样本筛选字段、下载后图片理解边界和本地证据汇总脚本。

## 范围内

- 新增 `.agents/skills/douyin-hot-sample-research/`。
- Skill 第一阶段必须从调研开始：关键词搜索、热榜快照、最近热门筛选、候选样本分层。
- 明确 `douyin-downloader` 能支持搜索、热榜、下载、评论和基础互动数据。
- 明确下载后的图片理解可以由 Codex 做低量抽检；批量、定时、结构化提取需要 VL 模型。
- 新增只读汇总脚本，从 `douyin-downloader` / 额外数据目录的 JSONL 与 `*_data.json` 中抽取候选样本字段。
- 更新 `docs/progress.md`。

## 范围外

- 不改 `douyin-downloader`。
- 不改 `douyin-import-service`。
- 不新增 API 包装层。
- 不实现定时任务、自动下载编排或 VL 模型接入。
- 不跑大规模抖音搜索或下载。

## 完成标准

- Skill frontmatter 合法，能被 Codex 发现。
- Skill 明确告诉后续 agent 如何做调研、筛选、下载和图片理解决策。
- 汇总脚本能在已有本地样本上输出 Markdown / JSON。
- 相关校验命令通过，或记录无法运行的原因。

## 验证

- 使用 `quick_validate.py` 校验 skill。
- 使用 `py_compile` 校验汇总脚本语法。
- 使用已有本地样本运行汇总脚本，确认输出包含日期、标题、作者、媒体类型、图片数和互动数据。
- 运行 `git diff --check`。
