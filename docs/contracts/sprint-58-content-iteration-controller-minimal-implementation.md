# Sprint 58 合同：内容迭代控制器最小实现

## 目标

把 Sprint 57 设计的“迷宫控制器”落成最小可调用版本：新增独立 Skill 入口，建立文件化状态目录，提供初始化、实验目录创建、状态校验和预测误差写入脚本，让新对话可以直接围绕 `prediction.json -> post_results -> prediction_errors.jsonl -> deviation_review.md -> strategy_update.json` 运转。

## 范围内

- 新增 `.agents/skills/content-iteration-controller/`，作为控制器 Agent 的独立调用入口。
- 新增 `content-lab/strategy_state/` 初始状态文件。
- 新增 `content-lab/experiments/`、`content-lab/market_scans/`、`content-lab/content_library/items/` 目录占位。
- 新增确定性脚本：
  - 初始化控制器状态。
  - 创建实验工作区。
  - 校验控制器状态和实验状态。
  - 追加预测误差 JSONL。
- 更新产品文档、README、`douyin-hot-sample-research` 协作说明和进度记录。

## 范围外

- 不新增 API、数据库表或前端页面。
- 不自动发布内容。
- 不自动读取抖音后台数据。
- 不自动修改现有 Skill；规则升级仍需用户确认。
- 不写入任何伪造实验结果、Mock 发布数据或预测误差。

## 交付物

- `.agents/skills/content-iteration-controller/SKILL.md`
- `.agents/skills/content-iteration-controller/agents/openai.yaml`
- `.agents/skills/content-iteration-controller/scripts/*.py`
- `content-lab/strategy_state/*`
- `content-lab/experiments/.gitkeep`
- `content-lab/market_scans/.gitkeep`
- `content-lab/content_library/items/.gitkeep`
- `docs/product/content-iteration-controller-agent.md`
- `docs/product/content-iteration-system.md`
- `.agents/skills/douyin-hot-sample-research/SKILL.md`
- `README.md`
- `docs/progress.md`

## 完成标准

- 可以通过 `content-iteration-controller` Skill 直接启动控制器流程。
- 可以用脚本初始化 `content-lab/strategy_state/`。
- 可以用脚本创建一轮实验目录和空白 `prediction.json`。
- 可以校验状态文件和实验文件是否齐全。
- 可以把人工确认后的预测误差追加到 `prediction_errors.jsonl`。
- 校验通过，且没有引入 Mock 数据或静默兜底。

## 验证

```bash
python3 -m py_compile .agents/skills/content-iteration-controller/scripts/*.py
backend/.venv/bin/python /Users/pengfei.shi/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/content-iteration-controller
python3 .agents/skills/content-iteration-controller/scripts/validate_controller_state.py
python3 .agents/skills/content-iteration-controller/scripts/create_experiment.py --experiment-id smoke-controller-check --title "控制器脚本冒烟检查" --root /tmp/doodlestory-controller-smoke
python3 .agents/skills/content-iteration-controller/scripts/init_controller_state.py --root /tmp/doodlestory-controller-smoke
python3 .agents/skills/content-iteration-controller/scripts/validate_controller_state.py --root /tmp/doodlestory-controller-smoke --experiment-id smoke-controller-check
python3 .agents/skills/content-iteration-controller/scripts/append_prediction_error.py --root /tmp/doodlestory-controller-smoke --json '{"experiment_id":"smoke-controller-check","post_id":"dy-smoke-001","prediction":"测试预测","expected_metric":"collect_rate > baseline","actual_metric":"collect_rate < baseline","error_type":"metric_mismatch","diagnosis":"冒烟测试诊断","rule_update_candidate":"冒烟测试候选规则，不进入真实仓库"}'
git diff --check
```

Manual or QA checks:

- 人工确认 `content-lab/strategy_state/` 只包含空白状态和规则模板，不包含伪造实验结果。
- 人工确认控制器 Skill 与 `douyin-hot-sample-research` 的职责边界清楚。

## 风险 / 说明

- 这是文件化最小实现，不是产品 UI 或后台服务。
- `prediction.json` 是否真实有效仍需要人工或后续控制器推理填写；脚本只提供结构和校验，不替用户编造预测。
- 预测误差写入必须来自真实发布数据和人工/Agent 复盘，不允许为了满足升级门槛而补空数据。

## Handoff

- 下一步：用 `content-iteration-controller` 创建第一轮真实实验目录，再让 `douyin-hot-sample-research` 的市场扫描产物填入 `prediction.json` 的 `market_evidence`。
