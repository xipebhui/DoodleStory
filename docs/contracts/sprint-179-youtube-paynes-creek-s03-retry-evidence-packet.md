# Sprint 179：Paynes Creek S03 单镜重试证据包

状态：Complete（文档与空白证据模板；未执行 G2、模型、媒体或发布）

## Goal

把未来 G4 的一张 S03 重试从口头步骤收敛为可审计协议：固定前置 Gate、授权范围、输入版本、Native
`generate_image → inspect_image` 工具链、真实资产字段、机器检查、双人人工复核和终态决策，避免把
“已准备”误写成“已运行”，也避免一次授权扩张为重试、换 Provider 或批量生图。

## In scope

- 对照当前 Native Runtime 源码，记录 `inspect_image` 的真实请求与返回字段。
- 固定 S03 的旁白、事实 / 来源 / 权利编号、完整 Prompt 哈希、候选文件名、运动和构图边界。
- 定义 G2、G3、G4 独立通过与授权证据，缺少任一项时不得建立媒体 Run。
- 定义一次 Run 最多一张候选、一次视觉检查，失败即停且不自动重试或切换 Provider。
- 输出人工事实审核与视觉审核清单，以及不伪造未观测结果的 JSON 空白模板。
- 把新证据包接入生产控制室、YouTube 索引、研究日志、根 README 和项目进度。

## Out of scope

- 不批准或实施 G2，不修改 Native Agent、Agents SDK、Provider、配置、迁移、数据库或测试代码。
- 不执行 G3 或 G4，不调用 SiliconFlow、火苗、图片、VL、TTS、字幕、Remotion 或发布接口。
- 不恢复或重试 Sprint 175 的失败 Run，不创建 Style、Skill、Run、Conversation、资产或实验记录。
- 不指定尚未确认的成本上限、授权人、事实审核人或视觉审核人，不用示例值冒充真实记录。
- 不改变 S03 Prompt、首片题目、赛道排序、市场结论、`strategy_memory.md` 或内容 Skill。
- 不增加自动重试、模型 / Provider 切换、上下文截断、摘要、Mock、占位资产或静默继续。

## Deliverables

- `docs/strategy/youtube/paynes-creek-s03-retry-protocol.md`
- `docs/strategy/youtube/paynes-creek-s03-gate-evidence-template.json`
- 生产控制室、YouTube 索引、研究日志、根 README 与 `docs/progress.md` 更新。

## Done means

- 操作者能从协议判断何时可以创建 G4 Run，缺少什么时必须停止。
- JSON 中所有未观测字段保持 `null` 或明确的 `not_run / not_reviewed`，不含伪造 ID、尺寸、成本或 verdict。
- `inspect_image` 请求字段、允许 verdict 与持久化返回字段和当前 Native Runtime 一致。
- 只有机器 `accept`、事实审核 `pass`、视觉审核 `pass` 同时成立，才允许写入批准文件名并开放 G5。
- 任一失败都保留候选与证据并结束本次授权；第二张候选必须另建记录并重新授权。
- 文档明确本 Sprint 只提高制作准备度，不代表 G2 / G3 / G4 已通过，也不代表视频已开始生成。

## Verification

```powershell
Get-Content docs/strategy/youtube/paynes-creek-s03-gate-evidence-template.json -Raw |
  ConvertFrom-Json | Out-Null
rg -n "inspect_image|verdict|image_id|latency_ms" backend/app/services/native_agent_loop.py
git diff --check
```

Manual or QA checks:

- 对照 S03 Prompt 包、生产草案、逐镜证据板和首次 Gate 记录复核固定输入。
- 对照 `backend/app/services/native_agent_loop.py` 与 `backend/app/services/agent_vision.py` 复核机器检查契约。
- 检查文档链接、空白字段语义、停止条件、敏感信息与内容控制器状态。
- 确认没有修改运行时代码、配置、数据库、策略记忆或 Skill。

## Risks / notes

- 当前视觉检查器的系统角色仍称“漫画成图质量检查器”，可接收本 Gate 的自定义 checks，但机器分数只能
  作为视觉证据之一，不能证明历史事实或版权清白。
- `required_text=[]` 只表示画面不要求出现文字；“无文字 / Logo / 水印”必须通过专门 check 与人工复核。
- 1920×1080 是交付目标，不是当前 Provider 的已验证返回；模板必须记录文件真实宽高。
- Prompt 哈希以 UTF-8、无末尾换行的 S03 完整代码块正文计算；执行前必须再次按同一规则核对。

## Handoff

- 下一步仍是由用户明确批准或拒绝 G2 离线适配。G2 通过后另行批准 G3；只有 G3 真实结果为
  `pass_for_s03_single_image_review`，才填写本模板的授权字段并执行一张 S03。
