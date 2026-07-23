# Agent 漫画 V1 新窗口实施交接

> 状态更新（2026-07-23）：Sprint 105–108、110 已 Complete；Sprint 109 Draft 已 Superseded。当前唯一 Active 合同是 Sprint 111。后续 Sprint 112–117 已规划，但必须逐个完成、验收并由用户确认后再激活。

## 1. 仓库与分支

```bash
cd /Users/pengfei.shi/workspace/tmp-project/DoodleStory
git branch --show-current
git status --short
```

预期分支：

```text
codex/agent-feature
```

以下未跟踪内容属于用户或其它工作，不得删除、覆盖或加入 Agent Sprint 提交：

- `.agents/skills/koubo/`
- `content-lab/self-media-scripts/`
- `docs/api_v3.md`
- `docs/api_v4.md`
- `logs/`
- `output/`

如出现其它已跟踪修改，先确认来源，不得覆盖用户改动。

## 2. 全局必读顺序

每个新窗口的主 Agent 必须自己完整阅读：

1. `AGENTS.md`
2. `README.md`
3. `docs/spec.md`
4. `docs/progress.md`
5. `docs/implementation/agent-v1-implementation-roadmap.md`
6. 当前唯一 Active Sprint 合同
7. 合同直接引用的设计与标准

常用标准：

- 前端：`docs/standards/frontend.md`
- UI：`docs/standards/ui-interaction.md`
- Python：`docs/standards/python.md`
- 数据库：`docs/standards/database.md`
- 后台任务：`docs/standards/backend-workflows.md`

Agent 设计基线：

- `docs/design/agent-runtime-architecture.md`
- `docs/design/agent-tool-contracts.md`
- `docs/design/agent-creative-workspace-frontend-brief.md`
- `docs/design/agent-conversation-demo/README.md`

## 3. 不能沿用的旧决策

Sprint 107/108 的实现记录仍然真实，但以下产品决策已被最新路线替代：

- `/agent` 不再嵌在旧工作台 Shell。
- Agent 页面不再显示 `传统构建 / AI 构建` 分段切换。
- Agent 左侧只承担会话导航，不常驻旧任务、内容提取、风格、角色等后台导航。
- Agent 任务不再以旧 `/tasks/{task_id}` 详情作为主要检查界面。

仍然保留：

- 同一个用户与积分账户。
- 同一个 Style/Character 资源库。
- 同一个 `generation_tasks/task_panels/generated_images/file_assets` 数据事实。
- 传统 `/tasks` 页面和旧创建流程继续独立可用。

## 4. Sprint 顺序

| 顺序 | 合同 | 激活条件 |
| --- | --- | --- |
| 1 | `sprint-111-agent-independent-shell-readonly-inspector.md` | 当前 Active |
| 2 | `sprint-112-agent-mlflow-observability-baseline.md` | 111 Complete |
| 3 | `sprint-113-agent-skill-tool-runtime-foundation.md` | 112 Complete |
| 4 | `sprint-114-idea-to-comic-skill-hitl-event-stream.md` | 113 Complete |
| 5 | `sprint-115-agent-structured-resource-context.md` | 114 Complete |
| 6 | `sprint-116-agent-panel-version-vl-loop.md` | 115 Complete |
| 7 | `sprint-117-agent-evaluation-internal-release-gate.md` | 116 Complete |

不要并行实施相邻 Sprint。后一个 Sprint 的 schema/API 假设必须建立在前一个 Sprint 的完成实现上。

## 5. 当前 Sprint 111 启动提示词

把下面整段复制到新的 Codex 窗口：

> 请在 `/Users/pengfei.shi/workspace/tmp-project/DoodleStory` 的 `codex/agent-feature` 分支实施 Sprint 111。开始前完整阅读根目录 `AGENTS.md`、`README.md`、`docs/spec.md`、`docs/progress.md`、`docs/implementation/agent-v1-implementation-roadmap.md`、`docs/contracts/sprint-111-agent-independent-shell-readonly-inspector.md`、`docs/standards/frontend.md`、`docs/standards/ui-interaction.md`、`docs/standards/python.md` 和 `docs/standards/database.md`，再检查当前 `frontend/src/main.tsx`、样式、API client、Agent schema/API 和任务/Panel/图片模型。只实现 Sprint 111：把 `/agent` 拆成独立 Agent Shell；保留真实新建/搜索/恢复会话；实现紧凑真实任务卡；新增按 Conversation→Task 鉴权的最小只读 API；实现 `/agent/{conversation_id}/tasks/{task_id}` AI 专属只读检查器。不要实现或显示 Mock、旧 Task 详情跳转、资源引用、Panel 写操作、VL、Skill、MLflow、SSE、HITL、Memory、TTS 或 Remotion。不要修改用户未跟踪文件。完成合同中的自动化、1440×900 与 1280×800 真实浏览器验收，更新合同状态、`docs/progress.md` 和路线图，并创建中文详细 git commit。

## 6. 后续窗口如何开始

每个后续 Sprint 合同末尾都包含 `New-window start prompt`。正确流程：

1. 当前窗口完成合同全部 Done means。
2. 运行 Verification。
3. 保存测试/浏览器/Provider/MLflow 证据。
4. 更新合同为 Complete、进度和路线图。
5. 创建中文详细 commit。
6. 回到规划窗口或由用户确认是否激活下一 Sprint。
7. 将下一合同状态从 Planned 改为 Active。
8. 把下一合同末尾提示词复制到新的实现窗口。

不得因为代码“顺手能做”就提前实施下一个 Sprint。

## 7. 每阶段检查重点

### Sprint 111

- 独立 Agent Shell。
- 真实会话与共享 Task。
- 只读检查器。
- 无 Mock、无假按钮、无数据库 migration。

### Sprint 112

- 先做 MLflow 官方兼容性 spike。
- 观测不驱动业务状态。
- 默认内容脱敏。
- 火苗成功、fallback、永久错误三条真实证据。

### Sprint 113

- Runtime Skill 与 Codex Skill 目录分离。
- catalog + `load_skill` 渐进加载。
- Tool 副作用先持久化。
- 不做 Workflow DSL。

### Sprint 114

- 方案未批准前不能生图或占积分。
- Artifact hash 绑定 Approval。
- SSE 来自持久化安全事件。
- 不展示 chain-of-thought。

### Sprint 115

- 所有资源真实查询、鉴权和父子校验。
- 引用已有 Task 不创建新 Task。
- `@角色` 必须真实进入任务快照和生图参考。

### Sprint 116

- 只修改目标 Panel。
- 恢复不调用 Provider、不扣积分。
- 自动修订最多一次。
- pause/resume、取消、晚到和重启可解释。

### Sprint 117

- 功能冻结。
- deterministic 100%。
- 任何越权、错误 Panel、重复扣费、取消复活或未批准生图都 NO_GO。
- 最终必须给出明确 `GO_INTERNAL` 或 `NO_GO`。

## 8. Mock 与失败规则

- 正式 `/agent` 不使用 Mock。
- 真实 Provider 不可用时记录阻塞，不返回占位成功。
- 后端能力尚未完成时隐藏对应操作，不做前端假实现。
- 不静默切换未授权 Provider。
- 不用旧 Task API 冒充尚未定义的 Agent 写操作。
- 所有错误保留用户草稿并给出明确恢复路径。

## 9. 每个 Sprint 的收尾模板

完成后至少记录：

- 实际实现文件与行为。
- API/schema/migration 变化。
- 自动化命令与结果。
- 真实浏览器/Provider/MLflow 验收。
- 未验证内容与阻塞。
- 下一 Sprint 的输入，不直接开始下一 Sprint。

最后创建符合根目录 `AGENTS.md` 的中文详细 commit。
