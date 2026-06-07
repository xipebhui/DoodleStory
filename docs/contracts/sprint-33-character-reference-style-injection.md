# Sprint 33 合同：人物参考图拼接风格提示词

## 目标

增强人物参考图生成阶段的风格控制。人物参考图最终提交给生图模型的 prompt 必须显式拼接任务保存的 `style_prompt_snapshot`，而不是只在一句话中概括为“保持某种风格”。

## 范围内

- 调整人物参考图 prompt 模板，把风格提示词作为独立段落放在人物设定之前。
- 保留现有人物参考图生成流程、模型选择、参考图输入规则和日志链路。
- 增加单元测试，确认人物参考图 prompt 包含独立风格提示词段，并且该段位于画面比例和人物外观设定之前。
- 更新产品规格和进度记录。

## 范围外

- 不改变 panel 生图 prompt 结构。
- 不改变人物识别 LLM prompt。
- 不引入风格参考图作为人物参考图输入。
- 不改变统一生图平台、模型白名单或 Provider 重试规则。

## 完成标准

- 新生成的人物参考图 prompt 包含完整 `style_prompt_snapshot`。
- 风格提示词在 prompt 中以独立段落出现，位置早于人物比例和人物外观设定。
- `backend/.venv/bin/python -m unittest discover -s backend/tests`、`backend/.venv/bin/python -m compileall backend/app`、`git diff --check` 和 `./scripts/check.sh` 通过。
