# Sprint 70 合同：完整故事切割目标长度优化

## 目标

修正完整故事自动切割过碎的问题。LLM 切割不要求逐字覆盖原文，但应尽量保留原文，并优先把相邻短句合并为 30-50 字的连续语义块，而不是把十几个字的短句默认拆成独立 panel。

## 范围内

- 完整故事 `segment_story` 调用传入目标长度范围 `target_panel_text_chars=30-50`。
- 切割 prompt 明确要求自动数量模式优先合并相邻短句，只有自然段、强转折、时间地点切换、动作变化或结尾余句无法合并时才允许少于 30 字。
- 50 字上限继续作为硬校验，30 字下限只作为生成目标，不作为失败条件。
- 更新回归测试、产品规格和进度记录。

## 范围外

- 不恢复逐字覆盖校验。
- 不改变故事方案模式和提取分镜模式。
- 不改变最终生图 prompt、人物参考图、图片 Provider 调用或积分逻辑。
- 不增加本地确定性兜底切割。

## 交付物

- `backend/app/services/llm.py`
- `backend/app/prompts/segment_story_v1.md`
- `backend/tests/test_story_segmentation.py`
- `docs/spec.md`
- `docs/progress.md`
- `docs/contracts/sprint-70-story-segmentation-target-length.md`

## 完成标准

- LLM 切割输入中包含目标长度范围 30-50。
- Prompt 明确优先合并相邻短句，避免十几个字一段的碎切。
- 单个 panel 超过 50 字仍明确失败。
- 相关测试和全量检查通过。

## 验证

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_story_segmentation
backend/.venv/bin/python -m compileall backend/app
git diff --check
./scripts/check.sh
```

## 风险 / 说明

- 30 字是软目标，不是硬校验；少数自然短句、强转折或结尾余句仍可保留短 panel。
