# Sprint 31 合同：最终生图 Prompt 拼接风格提示词

## 目标

增强每个 panel 的生图风格控制。最终发送给图片模型的 prompt 不再只依赖上游 LLM 吸收风格，而是显式拼接任务创建或重试时保存的 `style_prompt_snapshot`。

## 范围内

- 正式任务 panel 生图最终 prompt 加入风格提示词段。
- 单 panel 修改、重试或重新生成图片时，最终 prompt 同样加入风格提示词段。
- 风格提示词放在参考图说明之后、画面比例之前，作为图片模型直接执行的风格规则。
- 补充单元测试，确认最终 prompt 包含风格提示词且位置靠前。
- 更新产品规格和进度记录，说明当前最终生图 prompt 会直接拼接风格提示词。

## 范围外

- 不改变风格参考图策略；参考图仍只作为样张展示，不作为风格参考图传入 panel 生图。
- 不改变 LLM storyboard、panel prompt 或单 panel 修改 prompt 的 system prompt 风格注入方式。
- 不改写用户已有风格提示词内容。
- 不迁移历史任务已保存的 final prompt。

## 完成标准

- 新生成的 panel 图片 final prompt 包含 `style_prompt_snapshot`。
- 单 panel 修改生成的 final prompt 也包含 `style_prompt_snapshot`。
- `backend/.venv/bin/python -m unittest discover -s backend/tests`、`backend/.venv/bin/python -m compileall backend/app`、`npm run build --prefix frontend`、`git diff --check` 和 `./scripts/check.sh` 通过。
