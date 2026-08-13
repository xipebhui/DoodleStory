# Sprint 181：Native Agent Run 路由快照基础（G2-A）

状态：Ready for user approval（未实施、未激活）

## Goal

先完成 G2 的第一块离线基础：把当前唯一可执行的 `huomiao_responses` 路由在 Run 创建时固化为
`route / provider / api_shape / model` 四字段快照，并让普通执行、文章工作流、重试、恢复、Follow-up、
API 读取和追踪都只使用该快照。这个 Sprint 只消除现有模型配置漂移，不接入 SiliconFlow Chat。

## In scope

- 新增独立 Native Agent 配置：
  - `NATIVE_AGENT_DEFAULT_ROUTE=huomiao_responses`
  - `NATIVE_AGENT_HUOMIAO_MODEL=gpt-5.5`
- 保留 `AGENT_MODEL` 给既有 `AgentModelRouter`；Native Agent 不再从该字段读取或隐式回退。
- 新增只认识 `huomiao_responses` 的 route resolver / Provider factory：
  - `provider=huomiao`
  - `api_shape=responses`
  - `use_responses=True`
  - client / Runner retry 继续为 0。
- Run 创建前验证默认 route、Native 模型、当前 route 凭据和 Base URL；配置错误返回安全的 HTTP 503，
  不创建 Run、Workflow 或队列消息。
- `native_agent_runs` 新增三个非空字段：
  - `model_route_snapshot`
  - `model_provider_snapshot`
  - `model_api_shape_snapshot`
  - 现有 `model_snapshot` 保留并成为真实执行模型来源。
- 新增 Alembic revision `v3w4x5y6z7a8`，从当前 `u2v3w4x5y6z7` 升级：
  - 历史 Run 固定回填为 `huomiao_responses / huomiao / responses`；
  - 历史 `model_snapshot` 原值不改；
  - 回填后字段设为非空，不保留会掩盖应用漏写的 server default；
  - 当前没有 route 查询路径，不新增索引。
- 新 Run 原子写入四字段；Follow-up 原样继承父 Run 四字段；同 Run 重试 / 恢复不重算快照。
- `execute_native_agent_run()`、Workflow Compiler、Director / Writer / Reviewer、Agent、MLflow span 和
  Model Settings 全部使用 `run.model_snapshot`；Provider 由 Run 的 route / provider / shape 快照选择。
- `NativeAgentRunRead` 增加 `model_route`、`model_provider`、`model_api_shape`，保留 `model`。
- 更新 `.env.example`、`docs/spec.md`、SiliconFlow 蓝图、出站端点文档和项目进度。
- 新增聚焦测试并运行完整仓库检查。

## Out of scope

- 不新增或接受 `siliconflow_chat_v1`，不读取 `SILICONFLOW_*` 构建 Native Provider。
- 不给 `NativeAgentRunCreate` 增加 `model_route`，不做 Admin 路由选择、前端选择器或默认路由切换。
- 不实现 Chat Event Adapter、应用侧 `model_call_id`、Provider response ID 补写或 Tool 参数完成合成。
- 不修改 Chat Tool Output、S03 capability profile、10 条消息 wrapper 或 G3 兼容性脚本。
- 不修改 Native Step 表、Session Item 结构、完整输入重放、最大回合数或工具并发。
- 不调用火苗、SiliconFlow、图片、VL、TTS、字幕、视频、发布或账单接口。
- 不重试 S03，不生成媒体，不修改 YouTube 选题、Prompt、策略记忆或 Skill。
- 不增加 fallback、旧字段兼容回退、自动模型切换、Mock、占位结果、截断、摘要或静默错误处理。

## Deliverables

- `backend/app/services/native_agent_model_routes.py`
- `backend/app/core/config.py` 与 `.env.example`
- `backend/app/models/entities.py`
- `backend/alembic/versions/v3w4x5y6z7a8_add_native_agent_model_route_snapshot.py`
- `backend/app/schemas/native_agent.py`
- `backend/app/api/native_agent.py`
- `backend/app/services/native_agent_follow_up.py`
- `backend/app/services/native_agent_loop.py`
- `backend/tests/test_native_agent_model_routes.py`
- 对现有 Native Loop / Follow-up 测试的最小必要更新。
- `docs/spec.md`、`docs/integrations/llm-agent-endpoints.md`、架构蓝图与 `docs/progress.md`。

## Done means

### 配置与创建

- 默认设置明确解析为 `huomiao_responses / huomiao / responses / gpt-5.5`。
- `AGENT_MODEL` 与 `NATIVE_AGENT_HUOMIAO_MODEL` 设置为不同值时：旧 Router 继续读取前者，新 Native Run
  只快照后者。
- 未知 `NATIVE_AGENT_DEFAULT_ROUTE`、空 Native 模型、缺 API Key 或非法 Base URL 在 Run 写库前返回
  HTTP 503；Run、Workflow、Item 和 enqueue 调用均为 0。
- API 创建成功时一次性写入四字段，响应能读取 route、provider、shape 和 model。

### 迁移与历史事实

- 空 SQLite 能从 base 升到 `v3w4x5y6z7a8 (head)`。
- 在 `u2v3w4x5y6z7` 建立的历史 Run 升级后得到固定三字段，原 `model_snapshot` 逐字不变。
- 三个新字段最终为非空且没有 server default；downgrade 能删除它们并回到 `u2v3w4x5y6z7`。
- 不新增 route 索引、额外表、凭据列、Prompt 或 Provider 原始响应字段。

### 执行、恢复与续作

- Run 排队后，即使 `NATIVE_AGENT_HUOMIAO_MODEL` 或 `AGENT_MODEL` 变化，普通 Agent、文章 Compiler、
  Director、Writer、Reviewer 和 trace 仍只使用原 `run.model_snapshot`。
- Provider factory 只接受与当前已知 route 完全一致的三字段；数据库被人为写成未知或矛盾组合时，Run
  明确失败，不改走默认 route。
- 重试与恢复继续使用同一 Run 四字段，不重新读取默认 route 或模型。
- Follow-up 的四字段与父 Run 逐项相同；环境配置变化不能改变子 Run。
- 当前 Responses Tool Loop、Session 完整重放、Tool 幂等、媒体计数与最终状态行为不变。

### 边界

- `siliconflow_chat_v1` 仍不可创建、不可执行；代码中没有 `use_responses=False` 的新 Native 路径。
- 没有模型或媒体真实调用，G2 总 Gate 仍为未通过，G3 / G4 继续关闭。
- 没有密钥、Authorization、Base URL 凭据、完整 Prompt 或本地绝对数据库路径进入 API、事件或测试报告。

## Verification

```powershell
& backend/.venv/Scripts/python.exe -m unittest `
  backend.tests.test_native_agent_model_routes `
  backend.tests.test_native_agent_follow_up `
  backend.tests.test_native_agent_loop

& backend/.venv/Scripts/python.exe -m compileall backend/app
./scripts/check.sh
git diff --check
```

Migration checks:

1. 新临时 SQLite 执行 `alembic upgrade head`，确认 head 为 `v3w4x5y6z7a8`。
2. 第二个临时 SQLite 先升级到 `u2v3w4x5y6z7`，插入一个自定义 `model_snapshot` 的合法历史 Run，
   再升级到 head，核对三字段回填与模型原值。
3. 对第二个临时库执行 `downgrade u2v3w4x5y6z7`，核对三个新字段被移除。

Focused assertions:

- 创建配置错误时数据库对象数与 enqueue 次数均不变。
- 排队后修改两个环境模型，Fake Provider / Runner 捕获到的仍是 Run 模型。
- 文章 Compiler 与三个角色的模型均来自同一快照。
- Follow-up、retry、startup recovery 的四字段不漂移。
- API 响应和默认脱敏 trace 不含凭据或 Prompt。

## Risks / notes

- 这是 G2 的第一块，不是完整 G2。完成后只解决路由事实与模型漂移；没有 Chat 事件适配，不能进入 G3。
- 新配置不从 `AGENT_MODEL` 回退。若某部署过去用 `AGENT_MODEL` 覆盖 Native 模型，升级前必须把同一值
  显式写入 `NATIVE_AGENT_HUOMIAO_MODEL`；否则将使用新字段的默认 `gpt-5.5`。
- 凭据和 Base URL 不写入 Run。它们可轮换，但执行时缺失或无效必须明确失败；模型、Provider 和 API
  shape 不允许随环境漂移。
- 历史三字段回填表达的是当时唯一存在的代码路径，不推断 Provider 真实响应是否成功。

## Handoff

- 用户明确回复“批准 Sprint 181”或“批准 G2-A”后才能实施本合同。
- Sprint 181 通过并提交后，再建立 G2-B 合同：加入 `siliconflow_chat_v1`、Admin 显式选择、Chat Event
  Adapter、Tool Output policy、capability profile 和 10 条消息 wrapper；G2-A 不自动激活 G2-B。
