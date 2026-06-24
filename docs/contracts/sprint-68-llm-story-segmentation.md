# Sprint 68 合同：完整故事 LLM 语义切割

## 目标

完整故事模式恢复使用 LLM 做语义切割，让 panel 文本按故事节奏更顺滑，同时用代码硬校验保证每个 panel 原文不超过 50 字，并继续逐字覆盖用户原文。

## 范围内

- `segment_story` 主路径改为调用 `segment_story_v1.md` 的 LLM JSON 输出。
- LLM 切割结果必须满足 panel 顺序连续、固定数量模式数量一致、所有 panel 拼接后逐字等于原文。
- 每个完整故事 panel 的 `text` 长度不得超过 50 字。
- 固定数量模式下，如果用户指定图片数不足以满足 50 字上限，直接返回明确配置错误，不调用 LLM。
- 更新切割 prompt 和回归测试。

## 范围外

- 不改变故事方案模式和提取分镜模式。
- 不改变 panel prompt 生成、最终生图 prompt、人物参考图或图片 Provider 调用逻辑。
- 不为 LLM 切割失败增加确定性兜底切割。

## 交付物

- `backend/app/services/llm.py`
- `backend/app/prompts/segment_story_v1.md`
- `backend/tests/test_story_segmentation.py`
- `docs/spec.md`
- `docs/progress.md`

## 完成标准

- 完整故事模式切割会真实调用 LLM。
- 任意单个完整故事 panel 原文超过 50 字时任务明确失败。
- LLM 输出未逐字覆盖原文、panel_order 不连续或固定数量不一致时任务明确失败。
- 相关测试和全量检查通过。

## 验证

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_story_segmentation
backend/.venv/bin/python -m compileall backend/app
git diff --check
./scripts/check.sh
```

## 风险 / 说明

- 这次不添加本地确定性兜底；如果上游 LLM 返回不合规切割，任务会失败并显示明确错误，避免静默生成不符合 50 字约束的 panel。
