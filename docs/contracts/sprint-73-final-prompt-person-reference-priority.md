# Sprint 73 合同：最终生图 Prompt 人物参考优先级

## 目标

修正最终生图 prompt 中参考图语义混用的问题：人物参考必须作为第一优先级独立表达；风格参考只控制画风，不代表人物身份或外观。

## 范围内

- 将最终生图 prompt 外层参考说明拆为 `人物参考` 和 `风格参考` 两个独立块。
- 人物参考块使用 `人物参考（第一优先级，必须严格执行）` 和 `人物外观参考图N（角色名）` 映射。
- 风格参考块只在存在风格参考图时出现，使用 `风格参考（仅控制画风，不代表人物身份）`。
- `prompt` 和 `image` 风格参考模式下，只要 panel 携带人物参考图，都必须拼接人物参考块。
- 最后一张真人图片模式继续不携带漫画风格参考图或人物参考图。
- 更新 prompt 相关单测、产品规格和进度记录。

## 范围外

- 不改变参考图实际提交顺序。
- 不重新生成历史任务。
- 不改变人物参考图生成模型、风格模型或 Provider 路由。
- 不改变完整故事语义切割逻辑。

## 交付物

- `backend/app/services/task_worker.py`
- `backend/tests/test_task_worker_prompt.py`
- `docs/spec.md`
- `docs/progress.md`

## 完成标准

- prompt 风格模式下，人物参考映射出现在风格提示词之前。
- image 风格模式下，人物参考块和风格参考块分离，人物块排在风格块之前。
- 仅有风格参考图时，不生成空的人物参考块。
- 最后一张真人图片模式不拼接人物参考、风格参考或漫画风格提示词。
- 相关测试和全量检查通过。

## 验证

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_task_worker_prompt
backend/.venv/bin/python -m compileall backend/app
git diff --check
./scripts/check.sh
```

## 风险 / 说明

- 该修改只影响新生成或重新生成图片时发送给图片 Provider 的最终 prompt，不会自动修复已经生成的历史图片。
- 保留 `task_reference_block` 兼容旧内部调用，但其内容已由人物参考块和风格参考块组合而成。
