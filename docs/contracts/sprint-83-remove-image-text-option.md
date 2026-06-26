# Sprint 83 合同：图片任务无文字选项

## 目标

在图片任务创建流程中增加“是否去掉画面中的文字”选项。默认关闭；开启后，任务最终发送给图片模型的每张图提示词最前面拼接最高指令，要求图片中不能包含任何文字。

## 范围内

- `generation_tasks` 新增 `remove_image_text` 布尔字段，默认 `false`。
- 普通图片任务创建接口接收并保存 `remove_image_text`。
- 任务列表和详情返回 `remove_image_text`。
- 前端图片任务创建弹窗增加勾选项，默认不勾选。
- 最终生图提示词最前面拼接：`最高指令，图片中不能包含任何文字。`
- 单 panel 修改重新生成沿用同一任务的 `remove_image_text` 配置。
- DY 爆款复刻提交任务时沿用创建弹窗中的该选项。

## 范围外

- 不修改 storyboard、panel prompt、图片内文字结构化字段或 LLM 编译 Prompt。
- 不删除数据库中已经保存的旁白、对白、内心 OS 或图片文字字段。
- 不对历史任务批量重写已有 `final_prompt`。
- 不处理已经生成成功的图片。
- 不增加单 panel 级别的无文字开关。

## 完成标准

- 新建图片任务时可以选择是否去掉画面文字。
- 默认关闭时，最终提示词行为保持不变。
- 开启后，最终提示词以 `最高指令，图片中不能包含任何文字。` 开头。
- 后端测试、迁移、前端构建和全量检查通过，或未运行项有明确说明。

## 验证

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_task_worker_prompt backend.tests.test_content_extraction_media_flow
backend/.venv/bin/python -m compileall backend/app
npm run build --prefix frontend
git diff --check
./scripts/check.sh
```
