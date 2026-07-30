# Sprint 140：YouTube 账号绑定风格

Status: Complete（Closed）

## Goal

让正式频道账号拥有唯一的当前创作风格；管理员在账号管理中绑定或更换风格，Native Agent
选择创作账号后由后端唯一推导风格并保存不可变 Run 快照，不再允许账号与风格自由组合。

## In Scope

- `YoutubeChannel` 保存当前绑定的启用 Style 与绑定时间，已有频道允许处于“尚未绑定”的待配置状态。
- 频道列表、详情和 API 返回轻量绑定风格摘要。
- 频道详情提供绑定/更换风格入口；只允许绑定启用且未删除的 Style。
- Native Agent 增加独立的“创作账号”上下文，与现有真实 YouTube 发布上下文分离。
- 选择创作账号时，后端要求账号已绑定可用风格，并以账号绑定为唯一来源保存 Run 风格快照。
- 客户端同时传入与账号不一致的 `style_id` 时明确拒绝；未选择创作账号的实验性 Run 继续允许直接选择 Style。
- 被频道账号绑定的 Style 不允许删除；停用后账号保留绑定事实，但新 Run 明确失败并要求更换。
- 增加迁移、后端约束测试、前端类型与生产构建验证。

## Out of Scope

- 不把当前 YouTube 频道表重构成跨平台通用账号表。
- 不迁移 `content-lab/strategy_state/account_style_bindings.json` 中仅以名称表示的抖音账号。
- 不自动为已有频道选择默认风格，不批量回填，不静默改绑。
- 不增加风格绑定历史表；历史生成事实继续由任务和 Native Agent Run 的既有风格快照保存。
- 不改变真实 YouTube 发布确认、审核视频或异步发布语义。

## Done Means

- 管理员可以在频道详情绑定或更换一个启用 Style，刷新页面后绑定仍存在。
- 频道列表和详情能区分“已绑定风格”和“尚未绑定”。
- Native Agent 选择已绑定的创作账号后，Style 控件显示账号风格且不可独立编辑。
- 后端从账号读取 Style；未绑定、风格停用/删除或显式 `style_id` 不一致均返回明确错误。
- 新 Run 保存 `creation_channel_id` 以及当前 Style 的名称、Prompt、模型、比例和参考图快照。
- 未选择创作账号时，现有直接选择 Style 的流程保持不变。
- 被账号绑定的 Style 删除请求返回冲突提示，不发生自动解绑。

## Verification

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest \
  backend.tests.test_youtube_channels \
  backend.tests.test_native_agent_loop
backend/.venv/bin/alembic -c alembic.ini upgrade head
npm --prefix frontend run build
./scripts/check.sh
git diff --check
```

Manual check:

- 在频道详情绑定一个启用风格，确认列表和详情同步展示。
- 在 Native Agent 选择该创作账号，确认 Style 自动锁定并成功创建 Run。
- 使用未绑定账号与停用风格账号，确认页面提示及后端错误清晰。

## Risks / Notes

- `default_style_id` 在数据库中可空只用于已有账号平滑进入“待配置”状态；业务层不会把空值替换为默认风格。
- `creation_channel_id` 与现有 `youtube_channel_id` 分开：前者决定创作上下文和风格，后者仍只表示已确认的真实发布目标。
- Sprint 139 的账号创作上下文 Tool 正在同一工作区开发；本 Sprint 保留其未提交改动，不修改其 Tool 语义。

## Handoff

- 后续若正式接入抖音账号管理，再把相同绑定规则提升到跨平台账号实体，并迁移本地 JSON。
