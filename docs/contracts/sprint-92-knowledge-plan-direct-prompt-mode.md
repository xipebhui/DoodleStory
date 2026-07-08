# Sprint 92 合同：知识方案直通生图模式

## Goal

为知识卡片、图鉴、清单、方法论等非故事内容新增开放度更高的生成流程：用户提交完整知识图文方案后，系统形成可直通生图的单页提示词，并拼接风格、比例和参考图说明，不做故事改写、人物提取或最终 prompt 总结。

> 2026-07-08 修正：本合同最初把知识方案设计成必须显式页标的确定性拆分，这一实现已被 Sprint 97 修正为 LLM 自动拆页；显式页标可用但不是必填。

## In Scope

- 新增 `story_input_mode=knowledge_plan`。
- 前端创建任务弹窗新增 `知识方案` 模式。
- 知识方案使用 LLM 按知识结构自动拆页；显式 `第1页` / `图1` / `P1` 页标可被识别，但不是必填。
- 后端把拆页后的每页完整提示词直接作为该 panel 的 `generated_prompt`。
- 知识方案默认关闭人物参考；即使请求里传 `use_character_references=true`，创建出的任务也不走人物提取和人物参考图步骤。
- 知识方案不主动拆 `image_text`，不强行生成 `text_layout`。
- 知识方案生成图片前跳过最终 prompt LLM 编译，只直接拼接用户单页提示词、风格提示词、画面比例、风格参考图说明和去文字最高指令。
- 固定图片数量必须由 LLM 输出对应数量；数量不一致时明确失败。

## Out of Scope

- 不支持只输入一个主题后自动生成知识卡片内容。
- 不自动策划“男人 25 岁前必须做的 5 件事”这类选题的逐页内容。
- 不从知识方案里提取固定角色或生成任务临时人物参考图。
- 不修改现有完整故事、故事方案、提取分镜和 DY 爆款复刻流程。

## Deliverables

- 后端枚举、任务创建和 worker 流程接入。
- 知识方案 LLM 自动拆页与直通 final prompt。
- 前端创建任务模式入口与文案。
- 单元测试覆盖拆页、数量不一致、关闭人物参考和跳过 final prompt LLM。
- 规格与进度记录更新。

## Done Means

- 用户选择知识方案并输入多页知识图文 prompt 后，系统按页生成图片。
- 每页最终生图 prompt 保留用户原始单页提示词，不经过 LLM 总结压缩。
- 知识方案任务步骤只包含 `adapt_story` 和 `generate_images`。
- 没有显式页标时任务仍可按知识结构自动拆页。

## Verification

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_llm_storyboard_planning backend.tests.test_task_worker_prompt backend.tests.test_user_characters
backend/.venv/bin/python -m compileall backend/app
npm run build --prefix frontend
git diff --check
./scripts/check.sh
```
