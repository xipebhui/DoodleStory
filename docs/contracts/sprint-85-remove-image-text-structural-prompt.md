# Sprint 85 合同：无文字生图提示词结构化约束

## 目标

修复 `去掉画面文字` 只在最终提示词前加一句最高指令、但编译链路仍把旁白写入画面的冲突，让开启该选项的图片任务和视频任务上游图片任务在最终生图 prompt 中不再包含旁白、字幕、标题、对白气泡、内心 OS 或写入文字指令。

## 范围内

- 最终 prompt 编译输入携带 `remove_image_text`，并在开启时不把 `image_text` 中的文字字段作为画面文字传给编译器。
- 最终 prompt 编译系统规则明确：开启无文字模式时不得输出 `【文字】` 段或任何写入/绘制/呈现文字的指令。
- 后端最终拼接前清理编译输出里残留的图片文字绘制段落，继续保留画面、人物、场景、动作、构图和风格描述。
- 普通未开启 `remove_image_text` 的图片任务保持原有图片内文字流程。
- 更新规格、进度和回归测试。

## 范围外

- 不修改用户已处理的风格描述。
- 不改变图片 Provider、模型参数、参考图传递方式或宽高比请求参数。
- 不回写或自动重跑已有任务。
- 不改变任务分镜、旁白、音频或视频生成所需的结构化文本字段。

## 完成标准

- 开启 `remove_image_text` 时，最终生图 prompt 不再包含 `【文字】` 段、旁白写入、字幕框、对白气泡或留白文字区等绘制文字指令。
- 未开启 `remove_image_text` 时，既有文字呈现规则和测试保持通过。
- 相关后端测试、编译检查和仓库检查通过，或未运行项有明确说明。

## 验证

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_task_worker_prompt backend.tests.test_video_audio_tasks
backend/.venv/bin/python -m compileall backend/app
git diff --check
./scripts/check.sh
```
