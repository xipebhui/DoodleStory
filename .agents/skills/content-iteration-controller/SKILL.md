---
name: content-iteration-controller
description: DoodleStory 内容迭代控制器 Agent。用于迷宫控制器、内容实验状态初始化、发布前预测、发布后数据回流、预测误差诊断、策略更新和 Skill 升级建议。用户提到内容迭代控制器、Maze Controller、迷宫控制器、预测误差、strategy_state、prediction.json、deviation_review 或下一轮只改哪个变量时使用。
---

# 内容迭代控制器

## 目标

这个 Skill 是 DoodleStory 内容实验系统的控制器入口，中文名“迷宫控制器”。它不直接生成内容，也不直接采集抖音数据；它负责控制实验方向、证据门槛和规则升级节奏。

执行器边界：

- `douyin-hot-sample-research`：负责市场扫描、样本评分、账号/评论/VL 探测、选题假设和实验计划。
- DoodleStory 生成链路：负责 `故事方案`、`提取分镜`、`DY爆款复刻` 等内容生成执行。
- `content-iteration-controller`：负责判断证据是否足够、是否允许复盘、是否允许升级规则，以及下一轮只改变哪个主要变量。

永久禁忌：

1. 没有真实证据，不输出市场结论。
2. 没有发布前预测，不做发布后复盘。
3. 没有连续证据，不升级 Skill 规则。
4. 同一轮实验不同时改变多个主要变量。
5. 不承诺爆款、变现、稳定万播或平台分发结果。

## 先读文件

1. 当前文件。
2. `docs/product/content-iteration-controller-agent.md`
3. `docs/product/content-iteration-system.md`
4. `docs/experiments/content-iteration-cycle-template.md`
5. `.agents/skills/douyin-hot-sample-research/SKILL.md`，只在需要市场扫描或账号复盘执行时读取。
6. `content-lab/strategy_state/controller_constitution.md`
7. `content-lab/strategy_state/strategy_memory.md`
8. 当前实验目录下的 `experiment.md`、`prediction.json`、`post_results/`、`deviation_review.md` 和 `strategy_update.json`。

如果 `content-lab/strategy_state/` 不存在，先执行 `init_state`，不要凭聊天历史假设状态已经存在。

## 工作流

默认每轮只执行一个最小 step。只有用户明确说 `一次执行到位`、`跑完整流程`、`连续执行` 时，才连续执行多个 step。

### 0. 判断入口

用户说“初始化控制器”“建立迷宫控制器”“创建状态文件”时，执行 `init_state`。

用户要开始一轮内容实验时，执行 `experiment_intake`，然后 `prediction_setup`。

用户给发布后数据或要求复盘时，先检查是否存在同一实验的 `prediction.json`。没有预测时，只能做“记录”，不能做复盘，也不能升级规则。

用户要求“更新 Skill”“沉淀规则”“让 Skill 自动进化”时，执行 `rule_upgrade_review`。只有满足规则升级门槛，才能提出升级建议；实际修改 Skill 仍必须等待用户确认。

### 1. `init_state`

创建文件化状态骨架：

```bash
python .agents/skills/content-iteration-controller/scripts/init_controller_state.py
```

产物：

- `content-lab/strategy_state/controller_constitution.md`
- `content-lab/strategy_state/strategy_memory.md`
- `content-lab/strategy_state/rubric.md`
- `content-lab/strategy_state/rejected_patterns.md`
- `content-lab/strategy_state/persona_wounds.md`
- `content-lab/strategy_state/keyword_weights.json`
- `content-lab/strategy_state/category_weights.json`
- `content-lab/strategy_state/account_fit_profile.json`
- `content-lab/strategy_state/successful_hypotheses.jsonl`
- `content-lab/strategy_state/failed_hypotheses.jsonl`
- `content-lab/strategy_state/prediction_errors.jsonl`

已有文件默认不覆盖。需要重建时必须由用户明确授权，再使用脚本的 `--force`。

### 2. `experiment_intake`

确认一轮实验的最小输入：

- 实验 ID 或自动生成 ID。
- 方向/关键词/账号。
- 本轮要验证的核心假设。
- 本轮固定变量。
- 本轮只改变的一个主要变量。
- 预期指标和复盘时间点。

创建实验目录：

```bash
python .agents/skills/content-iteration-controller/scripts/create_experiment.py \
  --experiment-id 2026-06-16-wenzimanhua-cycle-01 \
  --title "文字漫画第一轮真实感结尾实验"
```

产物：

- `content-lab/experiments/<experiment_id>/experiment.md`
- `content-lab/experiments/<experiment_id>/prediction.json`
- `content-lab/experiments/<experiment_id>/publish_plan.json`
- `content-lab/experiments/<experiment_id>/post_results/.gitkeep`
- `content-lab/experiments/<experiment_id>/deviation_review.md`
- `content-lab/experiments/<experiment_id>/strategy_update.json`

### 3. `prediction_setup`

发布前必须完成 `prediction.json`。控制器检查它至少包含：

- `hypothesis`
- `expected_metric`
- `account_group`
- `fixed_variables`
- `changed_variable`
- `review_checkpoints`
- `market_evidence`
- `risk_notes`

如果没有这些字段，不允许进入发布复盘。

### 4. `post_result_intake`

发布后把后台数据写入：

```text
content-lab/experiments/<experiment_id>/post_results/
```

可以是 JSON、CSV 或 Markdown 摘要。最小字段应包含：

- 账号
- 作品 ID 或链接
- 发布时间
- 检查点，例如 2h、24h、72h
- 播放、点赞、评论、收藏、转发
- 可选：涨粉、私信、转化、违规/限流备注

### 5. `deviation_review`

只有同时存在 `prediction.json` 和真实 `post_results/`，才允许复盘。

复盘必须回答：

1. 当前最强证据是什么？
2. 当前最大误判风险是什么？
3. 预测和真实结果的差距是什么？
4. 偏差归因属于哪类：`market_misread`、`account_mismatch`、`hook_failure`、`title_failure`、`story_mechanism_failure`、`visual_execution_failure`、`timing_noise` 或 `metric_mismatch`。
5. 下一轮只允许改变哪个主要变量？
6. 哪些结论只能记录为观察，不能升级成规则？

如果预测失败，把结构化错误追加到：

```text
content-lab/strategy_state/prediction_errors.jsonl
```

确定性写入命令：

```bash
python .agents/skills/content-iteration-controller/scripts/append_prediction_error.py \
  --json-file /path/to/reviewed_prediction_error.json
```

不要把没有预测的发布数据写成“预测失败”。

### 6. `strategy_update`

输出当前实验的 `strategy_update.json`，但不要自动修改 Skill。

规则升级门槛：

- 单条异常：只记录观察。
- 同类成功 3 次：写入 `successful_hypotheses.jsonl`，成为候选规则。
- 同类失败 3 次：写入 `failed_hypotheses.jsonl` 或 `rejected_patterns.md`。
- 连续 10 条发布数据后：做一次批次复盘。
- 每周最多一次：提出 Skill 升级建议。
- Skill 文件修改必须人工确认。

### 7. `rule_upgrade_review`

当用户要求升级 Skill 时，检查：

- 原规则是什么。
- 新证据是什么。
- 成功或失败样本数量。
- 排除过哪些混淆变量。
- 新规则影响哪些步骤。
- 何时回滚或重新评估。

证据不足时，输出“不能升级”，并说明缺少哪些数据。

## 状态校验

任何新对话或重要复盘前，先校验控制器状态：

```bash
python .agents/skills/content-iteration-controller/scripts/validate_controller_state.py
```

校验某个实验：

```bash
python .agents/skills/content-iteration-controller/scripts/validate_controller_state.py \
  --experiment-id 2026-06-16-wenzimanhua-cycle-01
```

校验失败时先修状态文件，不要跳过。校验 warning 可以作为下一步补齐项，但不能伪造数据消除 warning。

## 输出格式

每轮输出保持短而硬：

- `input_used`：本轮用了哪些文件或用户输入。
- `artifact`：本轮写入或检查的文件。
- `decision`：本轮允许或禁止了什么。
- `blocked_by`：只有无法继续时写。
- `next_step`：用户回复 `继续` 后会执行的一个具体 step。

结尾必须写：

```text
本轮完成：<一句话>
下一步建议：<一个 step>
```

## 和抖音热门 Skill 的协作

需要市场证据时，不要自己发明采集流程；调用或切换到 `douyin-hot-sample-research`：

- 新关键词：先走 `new_lane_prediction`。
- 账号复盘：先走 `account_review`。
- 生成前：必须确认源样本已经完成 `full_story_extract`，不能只靠首尾页 preview。

控制器拿到执行器产物后，只做仲裁：

- 是否允许进入发布。
- 是否允许复盘。
- 是否允许沉淀规则。
- 下一轮只改哪个变量。
