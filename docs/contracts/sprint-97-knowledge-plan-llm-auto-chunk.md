# Sprint 97 合同：知识方案 LLM 自动拆页

## Goal

修正知识方案模式的拆页方式：用户可以输入连续知识图文方案，不必强制写“第1页 / 图1”。系统用 LLM 根据知识点、章节、条目、空行、标题、正文结构和固定图片数量自动拆成可独立生图的内容页，同时保持每页最终 prompt 直通生图。

## In Scope

- `knowledge_plan` 的拆页从正则页标硬解析改为 LLM JSON 拆页。
- 已写显式页标时，LLM 必须按页标顺序保留，不合并、不重排、不插入封面。
- 没有页标时，LLM 按知识结构和内容密度自动拆页。
- 固定图片数量时，LLM 必须输出对应数量；数量不一致继续明确失败。
- 每个 panel 的 `generated_prompt` 保留为单页完整生图提示词。
- 知识方案仍默认关闭人物参考，仍跳过最终 prompt LLM 编译。
- 前端创建弹窗文案改为“自动拆页”，不再要求页标。

## Out of Scope

- 不自动创造用户没有提供的新知识主题、标题、金句或作者栏。
- 不把知识方案改成故事方案，不走人物提取、对白/旁白拆解或角色参考图流程。
- 不改变完整故事、故事方案、提取分镜和 DY 爆款复刻流程。
- 不对已失败的历史任务自动重跑。

## Deliverables

- 新增知识方案拆页 prompt。
- 后端 `parse_knowledge_plan` 改为 LLM 拆页，并清空 `image_text` / `text_layout`，确保每页提示词直通。
- 前端知识方案模式说明、placeholder 和图片数量提示更新。
- 规格、API 设计和进度记录同步。
- 单元测试覆盖无页标自动拆页、显式页标拆页、数量不一致和跳过最终 prompt 编译。

## Done Means

- 用户输入类似“正向提示词：生成连续知识图鉴内容页... 家里忘记关煤气... 遇到不好的情况...”时，任务不会因缺少页标失败。
- 自动数量模式下，系统可以按知识模块拆成多张内容页。
- 固定数量模式下，系统按用户设置数量拆页，数量不一致明确失败。
- 生成图片前仍然直接拼接拆页后的单页提示词、风格和比例，不再额外让最终 prompt LLM 总结。

## Verification

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_llm_storyboard_planning backend.tests.test_task_worker_prompt backend.tests.test_user_characters
backend/.venv/bin/python -m compileall backend/app
npm run build --prefix frontend
git diff --check
./scripts/check.sh
```

Manual or QA checks:

- 用截图中的煤气/舍财保命连续知识方案创建 `knowledge_plan` 任务，不应再提示必须使用页标。

## Risks / Notes

- 知识方案拆页现在依赖文本模型配置；模型调用失败时任务应明确失败，不做正则或本地兜底。

## Handoff

- Next likely step: 针对线上失败任务手动重试或重新创建任务，确认 LLM 自动拆页效果。
