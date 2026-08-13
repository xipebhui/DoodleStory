# Sprint 175：YouTube Paynes Creek S03 单镜真实媒体 Gate

状态：Complete（`stop_before_batch`）

## 背景

Sprint 174 已定稿 Paynes Creek 中文旁白、12 段完整图片 Prompt 和无媒体 ID 的生产草案。继续进入
实际制作时，最强不确定性不是选题，而是当前图片 Provider 能否把 S03 的卤水浓缩重建画准确，并返回
适合统一 Remotion 合成的真实宽高。当前本地服务未运行，仓库没有本地数据库；Windows 系统 Python
3.11 已安装，但尚未安装项目依赖。本 Sprint 继续使用 Windows 本地运行，不切换到 WSL。

## Goal

用现有 DoodleStory Native Agent 链路完成一次受控、可回查的 S03 真实图片生成与检查：建立专用
16:9 Style 和只授权 `generate_image`、`inspect_image` 的本地 Skill，准确生成一张候选图，记录实际
Provider、模型、尺寸与检查结果，并据此决定是否允许继续 S01 和其余镜头。

## 实际结果

Windows 后端、MLflow、专用 Style 与最小 Skill 均已建立并通过启动检查。唯一一次 Native Run 在
首轮 Agent 文本规划请求中由 `gpt-5.5` / 火苗兼容地址返回 HTTP 429 `usage_limit_reached`，终态
`failed`；`model_call_count=1`、`image_call_count=0`，没有 Tool Step、图片、资产或视觉检查。
Gate 结论为 `stop_before_batch`，没有重试或切换 Provider。完整记录见
`docs/strategy/youtube/paynes-creek-s03-media-gate.md`。

## In scope

- 在 `backend/.venv` 建立被 Git 忽略的 Windows Python 3.11 环境并安装项目锁定依赖。
- 修复后端单实例运行锁对 Windows 的导入阻塞：Windows 使用系统文件区间锁，POSIX 保持现有
  `flock`，两端都必须维持跨进程非阻塞互斥和释放后可重获语义。
- 初始化仓库本地 `.env` 指向的 SQLite 数据库和本地 Storage；不连接远端数据库。
- 注册一个只用于本次验证的本地测试用户；凭据不写入仓库、日志或文档。
- 创建并启用专用 Style：`Paynes Creek Evidence Desk 16:9`、`Qwen/Qwen-Image`、`16:9`、Prompt
  模式、无参考图、无频道绑定。
- 创建并发布一个本地用户 Skill，只授权 `generate_image` 与 `inspect_image`；正文要求只调用一次
  `generate_image`，随后检查同一图片，任何失败或拒绝都立即停止。
- 使用 Sprint 174 的 S03 完整 Prompt 创建一个 Native Agent Conversation / Run，Provider 参数固定
  `default`，实际解析应为 `.env` 当前主路径 `qy`。
- 轮询 Run 到终态，核对模型调用、图片调用、检查调用、事件、资产和积分事实；下载候选图做本地人工
  视觉复核。
- 若自动检查与人工复核都通过，保存 `PC-S03-approved.png` 和审核记录；任一不通过则只保存失败记录，
  不伪装批准图。

## Out of scope

- 不生成 S01、S02 或其余 11 镜，不生成第二张 S03 候选。
- 不调用 TTS、Whisper、Remotion 或 YouTube 发布，不创建市场实验、频道或账号绑定。
- 不修改图片、Native Agent、Style、Storage 或 Remotion 业务代码；不重构 startup、队列或恢复流程。
- 不自动切换到 Grok、xgapi、其他模型或其他尺寸，不裁切、补边、放大或重绘失败图片。
- 不把 Style / Skill 的本地 ID 写入策略记忆，也不把单镜结果升级成赛道或市场规则。

## Done means

- Windows 本地后端可以从隔离虚拟环境启动，健康检查通过；SQLite 和 Storage 均位于本地忽略路径。
- 指向同一数据库的第二个 Windows 后端进程在 startup 恢复前明确失败，首实例释放后可重新获取锁；
  POSIX 原有行为不变。
- Style 快照为 `Qwen/Qwen-Image`、`16:9`、无参考图；Skill Version 只包含
  `generate_image`、`inspect_image`。
- Native Run 的用户输入与 Sprint 174 S03 Prompt 可追溯，`image_call_count` 不得超过 `1`；成功进入
  生图时必须等于 `1`，前置请求失败时必须等于 `0`。不得出现 speech、subtitle、video 或 publish Tool Call。
- 若图片调用成功，候选图片必须记录真实 `provider`、`image_model`、`aspect_ratio`、`width`、`height`、
  asset ID 和 Provider request ID；若前置请求失败，必须记录 0 次图片调用，并把所有媒体字段标为不适用。
- 只有图片实际返回后才执行 `inspect_image` 与人工复核；没有图片时不得伪造检查结果或批准图。
- Gate 结论只能是 `pass_for_S01_anchor` 或 `stop_before_batch`；即使通过，也只允许下一步验证 S01
  地图锚点，不允许直接批量生成 10 张。

## Verification

- 运行单实例锁聚焦测试（含真实子进程竞争）、数据库迁移与后端健康检查。
- 读取 API 返回与 SQLite 持久化记录，交叉核对 Style、Skill Version、Run、Step、Event、Image、Asset
  和积分流水。
- 若图片实际返回，下载并检查原图真实宽高、文件类型、非空内容和宽高比。
- 若图片实际返回，使用本地视觉检查核对 S03 硬约束，不以 `inspect_image` 单一结果替代人工复核。
- 运行内容迭代控制器状态校验、敏感新增扫描、`git diff --check` 和最终工作区检查。

## Handoff

若 Gate 为 `pass_for_S01_anchor`，下一 Sprint 仍只生成 S01 一张地图锚点，验证地图与机制图是否属于同一
视觉系统；S01 通过后才允许制定剩余 10 镜批量计划。若 Gate 为 `stop_before_batch`，记录具体失败项，
等待用户在“修改主 Prompt / Style”与“单独开发图片标准化”之间确认主路径，不自动实施替代方案。

本轮实际失败发生在图片 Tool 前，后续主路径应先在“恢复当前 Agent 模型额度”与“单独批准并验证新的
Agent 模型路由”之间决定；Prompt / Style 和图片标准化尚未进入可判断阶段。

验证结果：单实例锁 6 项聚焦测试、真实双 Uvicorn 竞争、compileall、Alembic head 和控制器状态校验
通过。全量后端 380 项在 Windows 上有 8 个临时 SQLite / MLflow 文件句柄清理 error 和 1 个写死 POSIX
路径的 Whisper assertion failure；这些与本 Sprint 变更无直接重叠，已在 Gate 记录中完整披露，未扩项修复。
