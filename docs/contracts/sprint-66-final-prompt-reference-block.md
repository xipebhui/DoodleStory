# Sprint 66 合同：最终生图 Prompt 任务参考块稳定化

## 目标

修复参考图风格模式下最终生图 prompt 把 `风格参考（参考图X）` 改写成“参考图X的某某风格”的问题，让最终发送给图片模型的提示词固定使用任务参考块表达参考图编号。

## 范围内

- `image` 风格参考模式下，最终 prompt 最前面追加标准 `任务参考` 块。
- 标准块把角色参考规范为 `角色外观参考图1（角色名）`，把风格参考规范为 `风格参考（图2）`。
- 清理 LLM 输出中类似 `整体风格：参考图2的极简黑白风格` 和 `整体色调/风格：室内，温暖与疲惫的对比` 的风格总结行。
- 收紧最终 prompt 编译系统提示，禁止 LLM 自行把参考图编号扩写成风格总结。
- 增加回归测试覆盖标准任务参考块。

## 范围外

- 不改变参考图传给图片 Provider 的顺序。
- 不改变 panel 生图、人物参考图或单图修改的 Provider 调用参数。
- 不重新生成历史图片。

## 交付物

- `backend/app/prompts/compose_final_image_prompts_v1.md`
- `backend/app/services/task_worker.py`
- `backend/tests/test_task_worker_prompt.py`
- `docs/progress.md`

## 完成标准

- 参考图风格模式最终 prompt 不再出现 `参考图2的极简黑白风格` 这类改写。
- 最终 prompt 最前面包含稳定的 `任务参考` 块。
- 相关测试、编译和全量检查通过。

## 验证

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_task_worker_prompt
backend/.venv/bin/python -m compileall backend/app
git diff --check
./scripts/check.sh
```

## 风险 / 说明

- 已经生成或已经保存的旧图片 prompt 不会自动改写；新生成、重试或单图修改时会使用新的最终 prompt 结构。
