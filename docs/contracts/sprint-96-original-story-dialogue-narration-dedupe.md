# Sprint Contract: 完整故事对白旁白去重

## Sprint Name

`sprint-96-original-story-dialogue-narration-dedupe`

## Goal

修复完整故事模式中同一句用户说话内容同时以旁白和对白气泡入图的问题，让最终生图 prompt 在进入图片模型前确定性去重，避免用户看到重复文字。

## In Scope

- 完整故事模式最终 prompt 编译前，从旁白文字计划中移除已经在 `visual_prompt` 绑定为人物对白的重复台词。
- 短促且不完整的残留说话引导语不再生成旁白框。
- 保持故事方案、提取分镜和知识方案既有文字结构不变。
- 增加回归测试覆盖线上 panel 15 的句式。

## Out of Scope

- 不修改故事切分逻辑。
- 不重写 panel prompt 生成模型提示词。
- 不改变图片 Provider、生图模型、积分或取消流程。
- 不对历史已生成图片做批量重生。

## Deliverables

- 后端最终 prompt payload 组装时应用完整故事对白/旁白去重。
- 最终生图 prompt 编译提示词同步说明后端已去重的语义。
- 产品规格和进度记录同步更新。
- 单元测试覆盖重复对白、保留有效剩余旁白和非说话旁白不误删。

## Done Means

- 线上 panel 15 这类 `直到他说 + 台词` 的原文不会在最终 prompt 中同时要求旁白框和对白气泡重复出现。
- 有有效场景信息的剩余旁白继续保留。
- 普通叙述句即使被 `visual_prompt` 错误写成对白，也不会因为缺少原文说话提示而被旁白去重误删。

## Verification

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_task_worker_prompt
backend/.venv/bin/python -m compileall backend/app
git diff --check
./scripts/check.sh
```

Manual or QA checks:

- 用线上 panel 15 数据手动验证去重函数输出 `narration=None`。

## Risks / Notes

- 本次只在最终 prompt 编译前处理文字计划，不回写历史 `task_panels.image_text_json`，避免改变任务原始追踪数据。

## Handoff

- Next likely step: 如发现更多非标准说话句式，再基于真实样本扩展确定性识别规则。
