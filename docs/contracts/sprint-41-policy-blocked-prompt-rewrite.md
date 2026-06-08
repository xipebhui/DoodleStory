# Sprint 41 合同：Policy Blocked 后改写生图提示词

## 目标

替换 Sprint 40 的切换图片模型策略。当生图 Provider 明确返回 Google policy blocked 类错误时，不再切换到 `baidu/ERNIE-Image-Turbo`，而是先让 LLM 在不改变画面效果的前提下改写最终生图提示词中的敏感动作意图表达，然后使用原图片模型、原参考图重新提交一次。

## 范围内

- 识别 `Unable to show the generated image`、`Generative AI Prohibited Use policy`、`filtered out` 等明确 policy blocked 错误。
- 新增 policy blocked 专用提示词改写步骤。
- 改写要求保持主体、构图、场景、风格、图片内文字、参考图关系和画面效果不变。
- 图片内需要写入的文字必须逐字保留。
- 正式任务 panel 生图和单 panel 修改生图都使用该策略。
- 改写后继续使用原模型和原参考图，不切换图片模型。
- 记录改写后的 `final_prompt` 和 `prompt_change_summary`，便于排查。
- 增加单元测试覆盖 policy blocked 后同模型同参考图重试，以及普通 Provider 错误不触发改写。

## 范围外

- 不切换到百度模型。
- 不删除参考图。
- 不改写图片内文字。
- 不对普通 400、配置错误、timeout、下载错误或非 policy blocked 错误触发改写。

## 完成标准

- policy blocked 后第二次请求使用改写后的 prompt、原模型和原参考图。
- 改写步骤有 `prompt_trace` 日志可追踪。
- `./scripts/check.sh` 通过。

## 风险 / 说明

- 如果改写后仍被拦截，任务仍按失败处理并显示明确错误。
- 改写只调整敏感表达方式，不能保证所有上游策略拦截都能通过。
