# Agent MLflow 兼容性 Spike

## 结论

执行时间：2026-07-24。

锁定组合：

- `openai-agents==0.18.3`
- `openai==2.45.0`
- `mlflow==3.14.0`
- Responses API
- 自定义 `AsyncOpenAI` client 与火苗/LIO OpenAI-compatible base URL

官方 `mlflow.openai.autolog()` 可以捕获当前 Agents SDK 经自定义 client 发出的异步 Responses 调用。LIO 真实成功调用保留 Agent/Chat Model 层级、模型名、token usage 与 provider request ID。当前生产代码保留 `RunConfig(tracing_disabled=True)` 时，MLflow 的补丁捕获仍然生效；该开关只关闭 Agents SDK 自带 tracing，不会关闭 MLflow 自动观测。

自动集成会捕获 Agent 输入、输出、instructions 与 OpenAI 请求字段，因此不能直接按默认配置用于 DoodleStory。生产接入必须在客户端导出前注册 MLflow span processor；`MLFLOW_TRACE_CONTENT=false` 时覆盖所有 span inputs/outputs，并清除 Prompt、消息、URL、文件路径、Authorization 和已配置密钥。业务 Run、model attempt、Tool、等待与 finalize 仍使用显式 span，以稳定记录数据库 Step ID、Provider 路由和业务状态。

## Spike 矩阵

| 项目 | 结果 |
| --- | --- |
| Agents SDK 自动捕获 | 通过；产生 Agent 与 Async Responses 模型 span |
| 自定义 `AsyncOpenAI` / base URL | 通过 |
| LIO 真实成功 | 通过；model、usage、request ID 均存在 |
| `RunConfig(tracing_disabled=True)` | 不阻断 MLflow 捕获 |
| Tool Call / Tool Output | 当前业务 Tool 不由 Agents SDK function tool 执行，必须在现有 `AgentStep` 边界显式建 span |
| `agent_run_id` 检索 | 通过；根 trace tag 可唯一检索，不需要新增数据库列 |
| 火苗真实调用 | 2026-07-24 首轮被 `auth_unavailable` 阻塞；最终复测返回 403 `Personal access token owner is inactive`。失败调用和错误分类可观测 |

## 依赖选择

先验证了官方推荐的轻量包：

- `mlflow-tracing==3.14.0` 缺少本地 file/SQL 查询所需依赖，不能独立完成合同要求的本地 smoke。
- `mlflow-skinny==3.14.0` 加上项目已有 SQLAlchemy/Alembic 后能初始化 SQLite tracking store，但导入 `mlflow.openai` 时因缺少完整 MLflow model API 报 `ImportError: ModelInputExample`。
- `mlflow==3.14.0` 同时通过 OpenAI autolog、本地 SQLite trace 写入与查询，因此生产依赖锁定完整包，不引入另一套 APM。

干净虚拟环境测量：

- skinny 基础环境约 `188 MiB`；
- 安装完整 MLflow 后约 `725 MiB`；
- 完整包增加约 `537 MiB`；
- 暖启动 `import mlflow; import mlflow.openai` 约 `1.37s`；
- 首次安装后的冷启动样本约 `10.04s`。

MLflow 默认关闭时 DoodleStory 不导入 MLflow，也不连接 Tracking URI；只有显式启用后才承担上述初始化成本。

当前基线显式使用同步 trace export：Tracking backend 在运行期间失联时，span 结束异常可以被当前 `agent_run_id` 捕获并写成结构化 `observability_error`，而不会在无 Run 上下文的后台 exporter 中延迟失败。该选择不改变业务状态；后续只有在增加可关联的异步 exporter 故障回调后才能改为异步上报。

## 安全检查

三条生产式 smoke trace 的完整序列化内容已扫描，下列受控标记均未出现：

- 用户测试正文与模型最终回复；
- smoke 用户邮箱；
- `Authorization` / `Bearer`；
- API key 环境变量名；
- 完整资源 URL。

## 当前阻塞

火苗 `gpt-5.5` 在 2026-07-24 首轮两次真实请求返回：

```text
auth_unavailable: no auth available (providers=codex, model=gpt-5.5)
```

最终复测进一步返回 HTTP 403：

```text
Personal access token owner is inactive.
```

最新证据表明阻塞是火苗侧凭据 owner 状态，而不是 MLflow 或 Agent Runtime 兼容性。未更换模型、未把 LIO 冒充火苗成功，也未引入备用观测平台。Sprint 112 在火苗凭据恢复并补齐直接成功证据前保持 Active。
