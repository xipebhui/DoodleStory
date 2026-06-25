# Sprint 72 合同：完整故事标点兜底切割

## 目标

完整故事模式继续优先使用 LIO/Google 做语义切割；当 LLM 切割结果结构、顺序或长度不合格时，后端按用户明确指定的标点规则做确定性兜底切割，避免任务因为模型反复输出超长 panel 卡死。

## 范围内

- 在 `segment_story` 中捕获 LLM 切割结果不合格类错误，并退回本地标点切割。
- 标点兜底规则：当前片段超过 20 字后，遇到下一个标点符号即截断。
- 标点集合覆盖句号、问号、叹号、分号、省略号、换行、逗号、顿号和冒号等常见中文/英文标点。
- 如果连续 50 字没有标点，则在 50 字处硬切，保证后端 50 字硬上限仍成立。
- 自动图片数量模式直接使用标点兜底结果。
- 固定图片数量模式仍必须满足用户指定数量和 50 字硬校验。
- 增加回归测试覆盖 LLM 反复超长后的标点兜底，以及无标点长文本的 50 字硬切。
- 更新规格和进度记录。

## 范围外

- 不在 LLM Provider 调用失败、配置缺失、鉴权失败时静默兜底。
- 不改变故事方案模式和提取分镜模式。
- 不改变最终生图 prompt、人物参考图或图片 Provider 调用逻辑。
- 不重新生成历史任务。

## 交付物

- `backend/app/services/llm.py`
- `backend/tests/test_story_segmentation.py`
- `docs/spec.md`
- `docs/progress.md`

## 完成标准

- LLM 首轮和修复轮仍返回超长 panel 时，完整故事自动数量模式可以退回标点切割并生成不超过 50 字的 panels。
- 标点兜底遵守“超过 20 字后，在下一个标点截断”。
- 无标点长文本不会超过 50 字硬上限。
- 配置错误和 Provider 调用异常不会被兜底吞掉。
- 相关测试和全量检查通过。

## 验证

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_story_segmentation
backend/.venv/bin/python -m compileall backend/app
git diff --check
./scripts/check.sh
```

## 风险 / 说明

- 标点兜底比 LLM 语义切割更机械，可能在语义节奏上不如 LLM 自然；它只在 LLM 输出不合格时启用，用来保证任务可继续执行。
- 没有标点的长文本会在 50 字处硬切，这是为了满足后端硬上限，切割自然度取决于用户原文。
