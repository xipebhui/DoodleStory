# Sprint 61 合同：内容实验可画分镜设计步骤

## 目标

在 `generation_brief` 和 DoodleStory 任务提交之间加入 `render_storyboard_design` 步骤。让内容实验先生成面向图片模型的可画逐页分镜，再提交为 `提取分镜` 任务，避免把故事策划稿、人物说明或固定页数要求直接送入生图链路。

## 范围内

- 在 `content-iteration-controller` Skill 中新增 `render_storyboard_design` 步骤。
- 新增可画分镜模板 `.agents/skills/content-iteration-controller/templates/render_storyboard_template.md`。
- 初始化状态时创建 `content-lab/render_storyboards/` 目录。
- 修改 `submit_generation_task.py`，按实验 slot 提交时必须读取 `publish_plan.json` 中的 `render_storyboard.artifact`。
- 缺少 `render_storyboard.artifact` 时明确阻止提交，不再从 `generation_brief.artifact` 取正文。
- 更新 README、产品文档、进度记录和当前 Sprint 指针。

## 范围外

- 不自动调用 LLM 批量改写全部历史 generation brief。
- 不自动创建新的 DoodleStory 生成任务。
- 不新增前端页面。
- 不绕过现有 `/api/v1/tasks` 创建逻辑。

## 交付物

- `.agents/skills/content-iteration-controller/SKILL.md`
- `.agents/skills/content-iteration-controller/scripts/init_controller_state.py`
- `.agents/skills/content-iteration-controller/scripts/submit_generation_task.py`
- `.agents/skills/content-iteration-controller/templates/render_storyboard_template.md`
- `content-lab/render_storyboards/.gitkeep`
- `README.md`
- `docs/product/content-iteration-controller-agent.md`
- `docs/product/content-iteration-system.md`
- `docs/progress.md`

## 完成标准

- Skill 明确流程为 `generation_brief -> render_storyboard_design -> generation_task_submission`。
- `submit-slot` 缺少 `render_storyboard.artifact` 时失败，并提示先执行可画分镜设计。
- `submit-file --dry-run` 使用可画分镜模板能生成正确 payload；缺少 render storyboard 的真实 slot 会被阻止提交。
- 可画分镜模板明确要求从 `图1：` 开始，并包含分格、画面、人物锚点、图片文字和避免项。

## 验证

```bash
python3 -m py_compile .agents/skills/content-iteration-controller/scripts/*.py
backend/.venv/bin/python /Users/pengfei.shi/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/content-iteration-controller
python3 .agents/skills/content-iteration-controller/scripts/validate_controller_state.py
python3 .agents/skills/content-iteration-controller/scripts/submit_generation_task.py submit-slot --experiment-id 2026-06-16-huayigegushi-cycle-01 --slot-id P4-H2-duck-bear --dry-run
python3 .agents/skills/content-iteration-controller/scripts/submit_generation_task.py submit-file --account "行走的故事" --storyboard-file .agents/skills/content-iteration-controller/templates/render_storyboard_template.md --dry-run
git diff --check
./scripts/check.sh
```

Manual or QA checks:

- 人工确认缺少 `render_storyboard.artifact` 的真实实验 slot 会被阻止提交；因此上面的 P4 `submit-slot --dry-run` 当前应返回失败。
- 人工确认 `submit-file --dry-run` 的 `original_text` 从 `图1：` 开始。

## 风险 / 说明

- 这是流程门槛变更，现有未补 `render_storyboard` 的 slot 不能直接提交任务。
- 已经提交过的历史任务不受影响；本 Sprint 不回滚、不重建历史任务。

## Handoff

- 下一步：为 `P4-H2-duck-bear` 先产出 `content-lab/render_storyboards/...md`，再提交 DoodleStory 任务。
