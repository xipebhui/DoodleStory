# Sprint 59 合同：内容叙事人格注入

## 目标

把“控制器人格统一、内容叙事人格分层配置、账号包装服务内容人格”的架构落入当前内容迭代 Skill。让每轮实验不只记录题材和指标，也记录叙事人格、人群欲望、情绪曲线、道德站位、风险边界和账号包装方向，便于后续复盘“这个题材用这种人格讲是否成立”。

## 范围内

- 在 `content-iteration-controller` 中加入人格注入规则。
- 新增 `content-lab/strategy_state/narrative_persona_profiles.json`。
- 更新控制器初始化脚本和状态校验脚本，使叙事人格库成为标准状态文件。
- 更新实验创建脚本，使 `prediction.json` 默认包含 `narrative_persona_profile`。
- 更新偏差诊断模板，加入叙事人格复盘。
- 更新 `douyin-hot-sample-research` 输出字段，要求选题假设和生成 brief 携带叙事人格。
- 更新产品文档、README 和进度记录。

## 范围外

- 不把叙事人格当作固定账号身份。
- 不引入自动生成账号头像、昵称或简介。
- 不引入越过合规边界的操控策略。
- 不用“乌合之众”作为无底线创作许可；只把大众心理转成可复盘的欲望、情绪曲线和评论触发字段。

## 交付物

- `.agents/skills/content-iteration-controller/SKILL.md`
- `.agents/skills/content-iteration-controller/scripts/*.py`
- `content-lab/strategy_state/narrative_persona_profiles.json`
- `content-lab/strategy_state/controller_constitution.md`
- `content-lab/strategy_state/rubric.md`
- `.agents/skills/douyin-hot-sample-research/SKILL.md`
- `.agents/skills/douyin-hot-sample-research/references/research-fields.md`
- `docs/product/content-iteration-controller-agent.md`
- `README.md`
- `docs/progress.md`

## 完成标准

- 控制器 Skill 明确区分统一控制器人格和可变内容叙事人格。
- `prediction.json` 新实验模板包含 `narrative_persona_profile`。
- 状态校验能发现缺失的叙事人格状态文件。
- 抖音热门样本 Skill 的选题假设/生成 brief 输出包含叙事人格字段。
- 文档明确账号包装服务内容人格，而不是内容服务当前头像、昵称或简介。

## 验证

```bash
python3 -m py_compile .agents/skills/content-iteration-controller/scripts/*.py
backend/.venv/bin/python /Users/pengfei.shi/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/content-iteration-controller
python3 .agents/skills/content-iteration-controller/scripts/validate_controller_state.py
rm -rf /tmp/doodlestory-persona-smoke
python3 .agents/skills/content-iteration-controller/scripts/init_controller_state.py --root /tmp/doodlestory-persona-smoke
python3 .agents/skills/content-iteration-controller/scripts/create_experiment.py --root /tmp/doodlestory-persona-smoke --experiment-id persona-smoke --title "叙事人格冒烟检查"
python3 .agents/skills/content-iteration-controller/scripts/validate_controller_state.py --root /tmp/doodlestory-persona-smoke --experiment-id persona-smoke
git diff --check
./scripts/check.sh
```

Manual or QA checks:

- 人工确认新增人格库是叙事策略模板，不包含真实用户或真实实验数据。
- 人工确认文档没有把“大众心理”写成无边界操控或违规内容建议。

## 风险 / 说明

- 叙事人格是内容机制的一部分，不是模型人格、账号人格或角色扮演。
- 家庭情感类内容可以理解大众欲望和禁忌边缘，但必须通过成年化、虚构化、匿名化和非露骨化控制风险。

## Handoff

- 下一步：创建第一轮真实实验时，在 `prediction.json` 中先填 `narrative_persona_profile`，再进入生成 brief。
