# Sprint 117：Agent Evaluation、稳定性与内部开放门槛

## Status

Planned。只有 Sprint 116 Complete 后才能激活。

## Goal

冻结 Agent 漫画 V1 的功能范围，用版本化 Evaluation、真实 Provider smoke、故障注入和浏览器回归验证质量、可靠性、权限、成本和可恢复性，并给出明确的“允许内部使用”或“阻止开放”结论。本 Sprint 不增加新创作能力。

## Release candidate scope

候选版本只包括：

- 独立 Agent Shell 与会话。
- `idea-to-comic` Skill。
- `generate_image` 和 `inspect_image` Tools。
- 方案 Artifact 与 Human-in-the-loop。
- SSE 用户安全事件。
- Style、Character、Task、Panel、Image Version 引用。
- 同一任务 Panel 新版本、接受、恢复。
- Run pause/resume。
- 火苗主平台、LIO 备用平台。
- MLflow 观测。

明确不把 TTS、Remotion、抠图、视频、用户自定义 Skill 或旧 Pipeline 迁移纳入 V1 发布条件。

## In scope

### 1. Evaluation dataset

在现有 `evals/agent_v1/cases.jsonl` 基础上版本化，例如：

```text
evals/agent_v1/v1/cases.jsonl
evals/agent_v1/v1/README.md
evals/agent_v1/v1/expected/
```

至少覆盖：

- Idea 补齐和故事自洽。
- 2、4、6 Panel 规划。
- 用户明确约束优先。
- 方案确认前无生图副作用。
- 请求修改方案后版本变化。
- 风格与角色引用。
- 历史 Task/Panel/Image Version 解析。
- 修改目标局部性。
- VL 检查四种 verdict。
- 接受/恢复。
- pause/resume。
- 长对话上下文。
- 跨用户资源攻击。
- 重复 Tool Call。
- Provider 临时错误 fallback。
- 永久错误不 fallback。
- 服务重启和 SSE 重连。
- 取消与 Provider 晚到。

### 2. Three evaluation layers

#### Deterministic

必须 100% 通过：

- schema；
- 权限；
- 状态机；
- 幂等；
- Panel 局部性；
- 积分；
- 事件顺序；
- fallback 分类；
- 恢复；
- 不泄露敏感数据。

#### Quality

使用固定 Judge 配置并记录版本：

- 故事完整性；
- Panel 连续性；
- 画面可生成性；
- Prompt 简洁度；
- 用户约束遵守；
- 风格一致性；
- 修改指令局部性；
- VL 结论可解释性。

Judge 不能覆盖 deterministic 失败。质量分达标也不能掩盖越权、重复扣费或状态错误。

#### Operational

统计：

- Run 完成率；
- 平均与 P50/P95 延迟；
- 火苗重试和 LIO fallback 率；
- 模型调用次数；
- Tool 调用次数；
- token usage；
- 每任务图片数与积分；
- waiting_for_input 停留；
- SSE 重连；
- 失败错误类别；
- 重启恢复成功率。

### 3. Eval runner

提供一个可重复执行的命令，支持：

- 选择 case ID 或 tag。
- 固定模型、Skill 版本/hash、Judge 版本和数据集版本。
- dry run 只做静态/确定性检查。
- real run 使用真实 Provider，并明确预计图片成本。
- 输出 JSON 报告和人读摘要。
- 将 agent_run_id 与 MLflow trace 关联。
- 不把 API key 或完整敏感内容写入报告。

本 Sprint 不构建 Web Evaluation 平台。

### 4. Fault injection matrix

至少覆盖：

- 火苗连接错误、timeout、429、允许的 5xx。
- 火苗 401/403、schema、model_not_found、能力不支持。
- LIO 失败。
- 图片 Provider timeout/失败。
- VL Provider 失败。
- Tool Result 写入前进程中断。
- Tool Result 写入后模型恢复前中断。
- approval 等待时重启。
- 图片生成中取消/暂停。
- Provider 晚到结果。
- SSE 连接断开和 cursor 重连。
- 同一请求重复提交。

每个场景必须说明预期数据库状态、MLflow trace、用户事件和积分结果。

### 5. Browser release regression

在 1440×900、1280×800 完成：

- 新建/恢复会话。
- 方案生成、修改、批准。
- 真实多 Panel 生成。
- 资源引用。
- 任务检查器。
- Panel 新版本、VL、接受、恢复。
- 暂停/继续。
- 刷新、前进/后退、SSE 断开重连。
- 传统工作台无回归。
- 键盘、焦点、错误恢复和控制台。

### 6. Release decision

输出：

```text
docs/testing/agent-v1-release-report.md
docs/testing/agent-v1-eval-report.json
```

报告必须给出：

- 测试环境与 commit。
- 模型、Skill、Judge、数据集版本。
- 自动化/真实/浏览器结果。
- 失败 case。
- 成本与延迟摘要。
- 已知风险。
- 明确结论：`GO_INTERNAL` 或 `NO_GO`。

## Blocking conditions

以下任一情况必须 `NO_GO`：

- 跨用户读取或操作资源。
- 修改错误 Panel。
- 重复生图、重复占用或重复扣费。
- 取消后保存不应保存的结果或复活 Run。
- 未批准方案就生图。
- 永久错误被无限重试或错误 fallback。
- 不能从数据库与 trace 解释失败。
- SSE 断线导致状态丢失或重复副作用。
- 正式 UI 出现 Mock、占位成功或假操作。

## Thresholds

激活 Sprint 117 时必须填写具体数值，至少包括：

- deterministic pass rate：固定为 100%。
- quality 平均分和单项最低分。
- 真实 Run 完成率。
- 恢复成功率。
- P95 延迟上限。
- 平均每任务模型调用和图片调用预算。
- 允许的 fallback 率告警线。

在没有跑第一轮 baseline 前，不凭空写质量或延迟数值；第一轮结果用于与用户确认最终阈值。

## Out of scope

- 新 Skill、新 Tool 或新资源类型。
- 旧 Pipeline 迁移/删除。
- 外部用户发布、计费策略改造。
- 全量性能压测或多实例部署。
- 用户 Memory、自定义 Skill。
- TTS、Remotion、视频。
- Evaluation Web UI。

## Deliverables

- 版本化 Eval 数据集与说明。
- 可重复 Eval runner。
- 故障注入套件。
- MLflow 对比记录。
- 浏览器发布回归证据。
- Release report 和 GO/NO-GO 结论。
- 已知问题与后续修复 Sprint 输入。

## Recommended implementation order

1. 冻结 RC commit、Skill 和模型版本。
2. 整理 deterministic case 并先跑纯测试。
3. 跑故障注入，先修所有 blocking defect。
4. 跑小批量真实质量 baseline。
5. 与用户确认质量/延迟/成本阈值。
6. 跑完整真实 Eval。
7. 完成浏览器回归和发布报告。

## Done means

1. 所有 deterministic case 100% 通过。
2. 所有 blocking fault injection 符合预期。
3. 质量、成本、延迟结果有固定版本且可复跑。
4. 每个真实 Run 可关联数据库 Step、Event 和 MLflow trace。
5. 浏览器完整创作与修改链路通过。
6. Release report 明确给出 GO_INTERNAL 或 NO_GO，不使用“基本可用”这类模糊结论。
7. 如果 NO_GO，按失败类别建立小型修复 Sprint，不在本合同中顺手扩 scope。

## Verification

```bash
backend/.venv/bin/python -m compileall backend/app
npm run build --prefix frontend
git diff --check
./scripts/check.sh
```

Eval 和 fault injection 的正式命令由本 Sprint 实现后写入此处及 `evals/agent_v1/v1/README.md`，不能在合同阶段伪造不存在的命令。

## Handoff

如果 `GO_INTERNAL`：

- 标记 Agent 漫画 V1 可供本地/内部使用。
- 下一阶段再讨论用户 Memory、参考漫画、抖音输入、旧 Pipeline 迁移，以及 TTS/Remotion 等新 Tools/Skills。

如果 `NO_GO`：

- 按 release report 的最高风险失败创建一个独立修复 Sprint。
- 保持功能冻结，不增加新 Tool 或 Skill。

## New-window start prompt

> 请实施 Sprint 117。先完整阅读项目基线、路线图、`docs/contracts/sprint-117-agent-evaluation-internal-release-gate.md`、现有 Eval 数据、MLflow、Skill/Tool/Artifact/Approval/Event/资源/版本实现和所有相关规范。此 Sprint 功能冻结，只做版本化 Evaluation、故障注入、真实 Provider/浏览器回归和 GO/NO-GO 报告。Deterministic 必须 100%；任何越权、错误 Panel、重复扣费、取消复活、未批准生图或不可解释失败都必须 NO_GO。不要顺手添加新 Skill、Tool、Memory、TTS 或 Remotion。完成报告、文档和中文详细 commit。
