# Sprint 91 合同：提取分镜数量不一致友好提示

## Goal

当提取分镜模式下，图片解析出的分镜页数和用户设置的固定图片数量不一致时，任务失败信息应直接说明数量不一致，而不是只显示泛化的结构化失败。

## In Scope

- 识别内容提取分镜结构化返回中的页数/分镜数与固定图片数量不一致错误。
- 对合法结构但 panel 数量与固定数量不一致的结果，使用同一类友好错误文案。
- 增加单元测试覆盖结构校验失败和合法结构数量不一致两种路径。
- 更新规格与进度记录。

## Out of Scope

- 不自动合并、删减、补页或改写分镜内容。
- 不改变图片数量选择逻辑。
- 不改变 LLM provider、重试策略或任务队列行为。

## Deliverables

- 后端 `parse_extracted_storyboard` 友好错误映射。
- 单元测试。
- 文档记录。

## Done Means

- 固定图片数量为 12、解析出 13 页时，用户看到类似“图片解析出的分镜数量（13）和你设置的图片数量（12）不一致”的提示。
- 该错误不再暴露 Pydantic 字段缺失、内部 schema 字段或泛化结构化失败文案。

## Verification

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_llm_storyboard_planning
backend/.venv/bin/python -m compileall backend/app
git diff --check
./scripts/check.sh
```
