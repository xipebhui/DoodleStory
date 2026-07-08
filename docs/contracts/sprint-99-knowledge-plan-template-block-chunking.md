# Sprint 99 合同：知识方案按条目块自动拆页

## Goal

修正知识方案自动拆页对“正向提示词 + 多个知识条目 + 负向提示词”结构的误判：正向提示词里的页眉、纸张、边框、作者栏和版式是全局模板，不应让模型把后续多个知识条目塞成一张图。

## In Scope

- 收紧 `parse_knowledge_plan_v1.md`：
  - 自动模式下，页数优先由知识条目、空行块、`主文字 + 副文字 + 画面` 组合、清单项目、章节小标题、方法步骤、误区条目和收尾金句块决定。
  - `正向提示词 / 负向提示词` 里的视觉风格、页眉、作者栏、边框和禁止项作为每页继承的全局模板。
  - 不因“正文使用2条横向内容条+1条收尾金句栏”等模板描述把所有条目合并成一页。
  - 只有用户明确写“单页 / 一张图 / 全部内容放同一页”时，自动模式才允许多条合并为一页。
- 前端知识方案提示文案同步说明自动模式按条目、空行块和收尾金句拆页。
- 规格、进度记录同步。
- 单元测试覆盖煤气/舍财/收尾金句这类结构应拆成 3 页。

## Out of Scope

- 不把知识方案改成正则硬拆页；最终 panels 仍由 LLM 输出。
- 不新增知识点、不补写用户没有提供的标题、金句或作者栏。
- 不改变固定图片数量模式的严格数量要求。
- 不改变知识方案直通生图、不走人物提取和不走最终 prompt LLM 编译的流程。

## Deliverables

- 更新知识方案拆页 prompt。
- 更新前端提示。
- 更新测试和项目文档。

## Done Means

- 用户输入“正向提示词：生成连续知识图鉴内容页... 家里忘记关煤气... 遇到不好的情况... 收尾金句... 负向提示词...”时，自动模式应拆成至少 3 个 panels，而不是 1 个 panel。
- 每个 panel 继承统一页眉《煤气与舍财》、复古手绘风、作者栏和负向约束。

## Verification

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_llm_storyboard_planning
backend/.venv/bin/python -m compileall backend/app
npm run build --prefix frontend
git diff --check
./scripts/check.sh
```

## Risks / Notes

- 如果用户真实想把多个条目压成一张图，需要在提示词里明确写“单页 / 一张图 / 全部内容放同一页”。
