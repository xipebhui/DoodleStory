# Sprint 70 合同：完整故事切割和单图页码清理

## 目标

修正完整故事自动切割过碎、过僵硬的问题。LLM 切割不要求逐字覆盖原文，但应尽量保留原文，并以画面单元、情绪转折和叙事节奏为首要标准，30-50 字只作为次级偏好。同时修复最终生图提示词中出现“第几页”页码，导致单张图片把页码角标画进画面的问题。

## 范围内

- 完整故事 `segment_story` 调用传入目标长度范围 `target_panel_text_chars=30-50`。
- 切割 prompt 明确要求自动数量模式以画面单元、情绪转折和叙事节奏为首要目标，不能为了凑 30-50 字硬合并两个本应分开的画面动作或情绪转折。
- 切割 prompt 明确要求“煮面”和“放鸡蛋”这类同一核心行动的补充信息不能拆开。
- 50 字上限继续作为硬校验，30 字下限只作为生成目标，不作为失败条件。
- 自动数量模式下，如果首轮 LLM 返回结果明显碎片化，触发一次 LLM 二次合并，让 LLM 重新按画面单元和情绪转折合并 panels；不使用本地确定性拼接兜底。
- 最终生图提示词编译 prompt 不再鼓励输出“第 X 页”，并明确禁止图片显示页码、编号或角标。
- 后端结构化分镜块不再写入 `第N页`，改为无编号的 `当前分镜`。
- 后端在最终发给图片模型前清理 LLM 输出中的页码标题和“在角落写入第 N 页”这类页码绘制指令。
- 更新回归测试、产品规格和进度记录。

## 范围外

- 不恢复逐字覆盖校验。
- 不改变故事方案模式和提取分镜模式。
- 不改变最终生图 prompt、人物参考图、图片 Provider 调用或积分逻辑。
- 不增加本地确定性兜底切割。
- 不删除用户原文中真实存在、且不是页码指令的正文内容。

## 交付物

- `backend/app/services/llm.py`
- `backend/app/services/task_worker.py`
- `backend/app/prompts/segment_story_v1.md`
- `backend/app/prompts/compose_final_image_prompts_v1.md`
- `backend/tests/test_story_segmentation.py`
- `backend/tests/test_task_worker_prompt.py`
- `docs/spec.md`
- `docs/progress.md`
- `docs/contracts/sprint-70-story-segmentation-target-length.md`

## 完成标准

- LLM 切割输入中包含目标长度范围 30-50。
- Prompt 明确语义和画面节奏优先于长度目标，避免硬凑 30-50 字。
- 首轮明显碎片化时会触发一次 LLM 二次合并。
- 单个 panel 超过 50 字仍明确失败。
- 最终 prompt 中不会再要求绘制“第几页”页码。
- 相关测试和全量检查通过。

## 验证

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_story_segmentation
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_task_worker_prompt
backend/.venv/bin/python -m compileall backend/app
git diff --check
./scripts/check.sh
```

## 风险 / 说明

- 30 字是软目标，不是硬校验；少数自然短句、强转折或结尾余句仍可保留短 panel。二次合并仍由 LLM 完成，不引入本地兜底切割。
