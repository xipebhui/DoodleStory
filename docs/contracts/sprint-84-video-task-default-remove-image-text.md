# Sprint 84 合同：视频任务默认无文字画面

## 目标

视频任务创建上游图片任务时，默认启用 `remove_image_text`，让视频素材图默认不包含画面文字。

## 范围内

- 视频任务创建接口内部构造上游 `TaskCreate` 时固定 `remove_image_text=True`。
- 保持视频任务前端创建表单不新增额外开关。
- 回归测试确认视频任务关联的上游 `GenerationTask.remove_image_text` 为 `True`。
- 更新规格和进度记录。

## 范围外

- 不改变普通图片任务默认值，普通图片任务仍默认不去掉文字。
- 不改变已有视频任务或已有上游图片任务。
- 不新增视频任务级别的 UI 开关。

## 完成标准

- 新建视频任务时，上游图片任务默认开启无文字画面。
- 相关后端测试和全量检查通过，或未运行项有明确说明。

## 验证

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_video_audio_tasks
backend/.venv/bin/python -m compileall backend/app
git diff --check
./scripts/check.sh
```
