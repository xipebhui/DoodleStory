# Sprint 65 合同：人物参考图携带风格参考图

## 目标

修复参考图风格模式下，任务生成“人物参考图”时只使用文字风格提示词、没有把风格参考图传给图片 Provider 的问题，让人物基准图和后续 panel 生图使用同一套任务风格参考图快照。

## 范围内

- 人物参考图 prompt 在参考图模式下写入 `风格参考（参考图X）` 说明，不再拼入风格提示词正文。
- 人物参考图图片 job 请求 Provider 时携带任务快照里的风格参考图。
- 已排队但仍使用旧 prompt 的人物参考图 job，在实际执行前按当前任务快照补齐风格参考说明。
- 增加回归测试覆盖 prompt 内容和人物参考图风格参考包。
- 更新进度记录。

## 范围外

- 不自动重生已经成功生成的人物参考图。
- 不修改 panel 生图参考图顺序和现有单图修改逻辑。
- 不改变图片 Provider、模型或参考图数量限制。

## 交付物

- `backend/app/prompts/character_reference_image_prompt_v1.md`
- `backend/app/services/character_references.py`
- `backend/app/services/task_worker.py`
- `backend/tests/test_character_reference_prompt.py`
- `backend/tests/test_task_worker_prompt.py`
- `docs/progress.md`

## 完成标准

- 参考图风格模式的人物参考图请求会携带风格参考图 URL。
- 人物参考图 prompt 中包含 `风格参考（参考图1）` 这类引用说明。
- prompt 模式的人物参考图仍使用原风格提示词文本。
- 相关测试、编译和全量检查通过。

## 验证

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_character_reference_prompt backend.tests.test_task_worker_prompt
backend/.venv/bin/python -m compileall backend/app
git diff --check
./scripts/check.sh
```

## 风险 / 说明

- 已经成功生成的人物参考图不会因为代码修复自动失效或重建；如果要让现有任务重新生成角色基准图，需要单独确认数据修复范围。
