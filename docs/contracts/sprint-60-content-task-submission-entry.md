# Sprint 60 合同：内容实验提交 DoodleStory 任务入口

## 目标

为内容迭代控制器补上“生成提交任务”的可调用入口。让 `content-lab` 中经过预测和发布前审核的故事 brief，可以通过 Skill 脚本提交为真实 DoodleStory 生成任务，并把返回的 `task_id` 回写到实验 `publish_plan.json`。

## 范围内

- 新增账号到 DoodleStory 画风的绑定状态文件。
- 新增 Skill 脚本，支持绑定账号画风、校验绑定、按实验 slot 提交任务、按单个故事文件提交任务。
- 提交任务固定使用现有 `/api/v1/tasks`，复用后端风格校验、积分、任务入队和风格快照。
- 提交任务固定为：
  - `story_input_mode=extracted_storyboard`
  - `image_count_mode=auto`
  - `requested_image_count=null`
  - `use_character_references=true`
  - `story_characters=[]`
- 提交成功后回写 `publish_plan.json` 并归档 `content-lab/task_submissions/*.json`。
- 更新 Skill 文档、README、进度记录和状态校验脚本。

## 范围外

- 不新增前端按钮。
- 不绕过后端 API 直接写任务表。
- 不自动选择默认画风。
- 不自动生成或保存 DoodleStory 登录凭据。
- 不自动发布到抖音。

## 交付物

- `.agents/skills/content-iteration-controller/scripts/submit_generation_task.py`
- `.agents/skills/content-iteration-controller/SKILL.md`
- `.agents/skills/content-iteration-controller/scripts/init_controller_state.py`
- `.agents/skills/content-iteration-controller/scripts/validate_controller_state.py`
- `content-lab/strategy_state/account_style_bindings.json`
- `README.md`
- `docs/progress.md`

## 完成标准

- 新对话中可以通过 `content-iteration-controller` 找到生成提交入口。
- 账号没有绑定 style_id 时，任务提交失败并明确提示。
- 任务提交 payload 不再沿用 generation brief 里的固定页数或固定角色配置。
- 任务提交正文只包含 `图1/图2...` 开始的逐页分镜块，不包含 brief 前置说明、人物列表或生成要求。
- `submit-slot --dry-run` 能从实验 `publish_plan.json` 和 generation brief 生成正确 payload。
- 状态校验包含 `account_style_bindings.json`。

## 验证

```bash
python3 -m py_compile .agents/skills/content-iteration-controller/scripts/*.py
backend/.venv/bin/python /Users/pengfei.shi/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/content-iteration-controller
python3 .agents/skills/content-iteration-controller/scripts/validate_controller_state.py
python3 .agents/skills/content-iteration-controller/scripts/submit_generation_task.py submit-slot --experiment-id 2026-06-16-huayigegushi-cycle-01 --slot-id P4-H2-duck-bear --dry-run
git diff --check
./scripts/check.sh
```

Manual or QA checks:

- 人工确认 dry-run 输出 payload 的任务类型为提取分镜，图片数量为 auto，`use_character_references=true`，且 `story_characters=[]`。
- 人工确认 dry-run 输出的 `original_text` 从 `图1：` 或 `第1页：` 开始。
- 人工确认未绑定账号不会真实提交任务。

## 风险 / 说明

- 真实提交任务需要 DoodleStory 后端运行，并提供 `DOODLESTORY_EMAIL/DOODLESTORY_PASSWORD` 或 `DOODLESTORY_SESSION_COOKIE`。
- 当前脚本只负责创建 DoodleStory 生成任务，不判断生成图质量，也不提交抖音发布。

## Handoff

- 下一步：用户为实验账号选择并绑定具体 DoodleStory 风格后，执行 `submit-slot` 创建真实任务。
